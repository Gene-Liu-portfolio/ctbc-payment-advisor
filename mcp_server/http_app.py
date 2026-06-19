"""
http_app.py
-----------
統一 ASGI 應用：同時提供
  - REST API（/api/*）— 給 React 前端直接呼叫
  - MCP Streamable HTTP（/mcp）— 給 Claude API 的 MCP Connector 連線
  - Chat 端點（/api/chat）— React 透過此端點與 Claude 多輪對話，Claude 再透過
    MCP Connector 自動呼叫 /mcp 上的工具（真 MCP 協定，非 function-calling 包裝）

啟動方式：
    python -m mcp_server.http_app

主要端點：
  - GET  /                → 服務資訊
  - GET  /health          → 健康檢查
  - GET  /api/cards       → 卡片清單
  - POST /api/search      → 通路最優卡查詢
  - POST /api/recommend   → 情境推薦（Claude Haiku 解析情境 / 產生理由；失敗時 regex fallback）
  - POST /api/compare     → 多卡比較
  - POST /api/promotions  → 優惠活動
  - POST /api/card-details → 單卡詳情
  - POST /api/chat        → Claude SSE 串流（透過 MCP Connector 呼叫工具）
  - *    /mcp/*           → MCP Streamable HTTP（給 Claude API 用）
"""

from __future__ import annotations

import json
import os
import re
import time

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.routing import Mount, Route

from .chat import chat_endpoint
from .http_utils import allowed_origins as _allowed_origins
from .http_utils import format_cashback_value as _format_cashback_value
from .http_utils import json_response as _json
from .server import mcp as mcp_server
from .tools.compare import compare_cards as _compare_cards
from .tools.promotions import get_card_details as _get_card_details
from .tools.promotions import get_promotions as _get_promotions
from .tools.recommend import OFF_TOPIC_MESSAGE
from .tools.recommend import deterministic_fallback_channels
from .tools.recommend import has_deterministic_consumption_intent
from .tools.recommend import recommend_payment as _recommend_payment
from .tools.search import _channel_display_name
from .tools.search import search_by_channel as _search_by_channel
from .tool_trace import tool_result_event as _tool_result_event
from .utils.channel_mapper import MERCHANT_TO_CHANNEL, normalize_merchant
from .utils.data_loader import get_cards_menu, get_data_summary
from .utils.data_loader import validate_card_ids
from .utils.llm_parser import parse_scenario

DEFAULT_JPY_TWD_RATE = float(os.getenv("JPY_TWD_RATE", "0.22"))


# ── Public routes ────────────────────────────────────────────────────────────

async def home(_: Request):
    return _json({
        "service": "CTBC Payment Advisor",
        "endpoints": {
            "health": "/health",
            "rest_api": "/api/cards",
            "chat": "/api/chat",
            "mcp": "/mcp",
        },
    })


async def health(_: Request):
    return PlainTextResponse("ok")


# ── REST API routes ──────────────────────────────────────────────────────────


def _extract_amount_fallback(text: str) -> dict:
    """Extract an amount for recommendation math; foreign currency is converted to TWD."""
    patterns = [
        (pattern, "JPY", DEFAULT_JPY_TWD_RATE)
        for pattern in [
            r"(?:JPY|日圓|日元|円)\s*([\d,]+)",
            r"([\d,]+)\s*(?:JPY|日圓|日元|円)",
        ]
    ]
    patterns.extend([
        (pattern, "TWD", 1.0)
        for pattern in [
            r"(?:NT\$|新台幣|台幣|TWD)\s*([\d,]+)",
            r"(?:花(?:了|費)?|消費|共|約|大概)\s*([\d,]+)\s*(?:元|塊)",
            r"([\d,]+)\s*(?:元|塊)",
        ]
    ])

    candidates = []
    for pattern, currency, rate in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            raw = match.group(1).replace(",", "")
            try:
                original_amount = float(raw)
            except ValueError:
                continue
            if not 1 <= original_amount <= 10_000_000:
                continue
            twd_amount = original_amount * rate
            candidates.append({
                "amount": twd_amount,
                "original_amount": original_amount,
                "currency": currency,
                "exchange_rate": rate,
                "amount_display": (
                    f"{int(original_amount):,} 日圓，約 NT$ {int(round(twd_amount)):,}"
                    if currency == "JPY"
                    else f"NT$ {int(original_amount):,}"
                ),
            })

    if not candidates:
        return {
            "amount": 0.0,
            "original_amount": 0.0,
            "currency": "TWD",
            "exchange_rate": 1.0,
            "amount_display": "未指定",
        }
    return max(candidates, key=lambda item: item["amount"])


async def api_cards(_: Request):
    """GET /api/cards — 回傳所有卡片清單。"""
    summary = get_data_summary()
    return _json({
        "last_updated": summary.get("last_updated"),
        "card_count": summary.get("card_count"),
        "cards": get_cards_menu(),
    })


async def api_search(request: Request):
    """POST /api/search — 通路最優卡查詢。"""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)

    cards_owned = body.get("cards_owned", [])
    if not cards_owned:
        return _json({"error": "cards_owned is required"}, 400)
    _, validation_error = validate_card_ids(cards_owned)
    if validation_error:
        return _json({"error": validation_error}, 400)

    result = _search_by_channel(
        channel=body.get("channel", "general"),
        cards_owned=cards_owned,
        amount=float(body.get("amount", 0)),
        top_k=int(body.get("top_k", 3)),
    )
    return _json(result)


async def api_recommend(request: Request):
    """POST /api/recommend — 情境推薦（Haiku 輔助解析；失敗時 regex fallback）。"""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)

    cards_owned = body.get("cards_owned", [])
    scenario = body.get("scenario", "")
    if not cards_owned:
        return _json({"error": "cards_owned is required"}, 400)
    if not scenario:
        return _json({"error": "scenario is required"}, 400)
    _, validation_error = validate_card_ids(cards_owned)
    if validation_error:
        return _json({"error": validation_error}, 400)

    result = _recommend_payment(scenario=scenario, cards_owned=cards_owned)
    return _json(result)


async def api_recommend_stream(request: Request):
    """POST /api/recommend/stream — structured SSE recommendation flow for the card UI."""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)

    cards_owned = body.get("cards_owned", [])
    scenario = body.get("scenario", "")
    if not cards_owned:
        return _json({"error": "cards_owned is required"}, 400)
    if not scenario:
        return _json({"error": "scenario is required"}, 400)
    _, validation_error = validate_card_ids(cards_owned)
    if validation_error:
        return _json({"error": validation_error}, 400)

    async def event_generator():
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        def calculation_event(channel_name: str, result: dict) -> dict:
            candidates = []
            for item in result.get("results", [])[:4]:
                trace = item.get("calculation_trace") or {}
                candidates.append({
                    "card_id": item.get("card_id"),
                    "card_name": item.get("card_name"),
                    "cashback_rate": item.get("cashback_rate"),
                    "estimated_cashback": item.get("estimated_cashback"),
                    "formula": trace.get("formula", "未計算預估回饋"),
                    "data_source": item.get("data_source"),
                    "is_fallback": item.get("is_fallback", False),
                })

            winner = candidates[0] if candidates else None
            ranking_summary = "無候選卡"
            if candidates:
                ranking_summary = " > ".join(
                    f"{item['card_name']} {_format_cashback_value(item.get('estimated_cashback'))}"
                    for item in candidates
                )

            return {
                "type": "mcp_calculation",
                "tool": "search_by_channel",
                "channel": channel_name,
                "candidates": candidates,
                "winner": winner,
                "ranking_summary": ranking_summary,
            }

        start_time = time.time()
        yield sse({"type": "thinking_start"})

        yield sse({
            "type": "tool_call",
            "tool": "parse_scenario",
            "status": "calling",
            "label": "解析消費情境中...",
        })

        llm_parsed = parse_scenario(scenario)
        parsed_channels = []
        amount = 0.0
        amount_info = _extract_amount_fallback(scenario)

        if llm_parsed is not None and not llm_parsed.get("is_consumption_scenario", True):
            yield sse({
                "type": "tool_call",
                "tool": "parse_scenario",
                "status": "done",
                "label": "已識別為非信用卡相關問題",
            })
            yield sse({"type": "thinking_done", "elapsed_seconds": round(time.time() - start_time, 1)})
            yield sse({
                "type": "result",
                "data": {
                    "scenario": scenario,
                    "parsed": {"channels": [], "amount": 0},
                    "recommendations": [],
                    "off_topic_message": llm_parsed.get("off_topic_message", ""),
                    "error": None,
                },
            })
            return

        if llm_parsed is not None:
            amount = llm_parsed["amount"]
            seen_cids: set[str] = set()
            for ch in llm_parsed["channels"]:
                cid = ch["channel_id"]
                if cid in seen_cids:
                    continue
                seen_cids.add(cid)
                parsed_channels.append({
                    "name": ch["merchant_or_keyword"] or _channel_display_name(cid, cid),
                    "channel_id": cid,
                })
        else:
            amount = amount_info["amount"]
            if not has_deterministic_consumption_intent(scenario, amount):
                yield sse({
                    "type": "tool_call",
                    "tool": "parse_scenario",
                    "status": "done",
                    "label": "已識別為非信用卡相關問題",
                })
                yield sse({"type": "thinking_done", "elapsed_seconds": round(time.time() - start_time, 1)})
                yield sse({
                    "type": "result",
                    "data": {
                        "scenario": scenario,
                        "parsed": {"channels": [], "amount": 0},
                        "recommendations": [],
                        "off_topic_message": OFF_TOPIC_MESSAGE,
                        "error": None,
                    },
                })
                return
            parsed_channels = deterministic_fallback_channels(scenario)

        if amount_info["currency"] != "TWD" and amount_info["amount"] > 0:
            amount = amount_info["amount"]
        elif amount <= 0 and amount_info["amount"] > 0:
            amount = amount_info["amount"]
        elif amount > 0 and amount_info["amount"] <= 0:
            amount_info = {
                "amount": amount,
                "original_amount": amount,
                "currency": "TWD",
                "exchange_rate": 1.0,
                "amount_display": f"NT$ {int(amount):,}",
            }

        channels_display = [ch["name"] for ch in parsed_channels]
        amount_label = amount_info["amount_display"] if amount else "未指定"
        yield sse({
            "type": "tool_call",
            "tool": "parse_scenario",
            "status": "done",
            "label": f"識別通路：{' | '.join(channels_display)}，金額：{amount_label}",
            "channels": channels_display,
            "amount": amount,
        })

        recommendations = []
        for ch in parsed_channels:
            channel_name = _channel_display_name(ch["channel_id"], ch["name"])
            yield sse({
                "type": "tool_call",
                "tool": "search_by_channel",
                "status": "calling",
                "label": f"查詢「{channel_name}」通路最佳卡片...",
                "channel": channel_name,
            })

            query = ch["channel_id"]
            if ch["name"]:
                normalized = normalize_merchant(ch["name"])
                if normalized in MERCHANT_TO_CHANNEL:
                    query = ch["name"]

            result = _search_by_channel(
                channel=query,
                cards_owned=cards_owned,
                amount=amount,
                top_k=3,
            )

            if result.get("results"):
                top_card = result["results"][0]["card_name"]
                yield sse({
                    "type": "tool_call",
                    "tool": "search_by_channel",
                    "status": "done",
                    "label": f"「{channel_name}」找到 {len(result['results'])} 張卡，最高回饋：{top_card}",
                    "channel": channel_name,
                    "result_count": len(result["results"]),
                })
                yield sse(_tool_result_event(
                    tool="search_by_channel",
                    channel=channel_name,
                    status="success",
                    summary=f"回傳 {len(result['results'])} 張候選卡，最高回饋為 {top_card}",
                    data=result,
                ))
                yield sse(calculation_event(channel_name, result))
                recommendations.append({
                    "channel_name": channel_name,
                    "channel_id": ch["channel_id"],
                    "best_options": result["results"],
                })
            else:
                yield sse({
                    "type": "tool_call",
                    "tool": "search_by_channel",
                    "status": "done",
                    "label": f"「{channel_name}」無符合結果",
                    "channel": channel_name,
                    "result_count": 0,
                })
                yield sse(_tool_result_event(
                    tool="search_by_channel",
                    channel=channel_name,
                    status="success",
                    summary=f"「{channel_name}」沒有回傳符合條件的候選卡",
                    data=result,
                ))
                yield sse(calculation_event(channel_name, result))

        if recommendations:
            unique_card_ids = []
            for rec in recommendations:
                for result in rec["best_options"]:
                    card_id = result.get("card_id")
                    if card_id and card_id not in unique_card_ids:
                        unique_card_ids.append(card_id)
                    if len(unique_card_ids) >= 4:
                        break
                if len(unique_card_ids) >= 4:
                    break

            yield sse({
                "type": "tool_call",
                "tool": "get_card_details",
                "status": "calling",
                "label": f"查詢 {len(unique_card_ids)} 張候選卡片的限制條件...",
            })
            card_details = {
                card_id: _get_card_details(card_id)
                for card_id in unique_card_ids
            }
            for rec in recommendations:
                channel_id = rec["channel_id"]
                for result in rec["best_options"]:
                    detail = card_details.get(result.get("card_id"), {})
                    matching_channels = [
                        channel
                        for channel in detail.get("channels", [])
                        if channel.get("channel_id") == channel_id
                    ]
                    highlights = []
                    for channel in matching_channels[:2]:
                        description = channel.get("cashback_description")
                        conditions = channel.get("conditions")
                        valid_end = channel.get("valid_end")
                        if description and description not in highlights:
                            highlights.append(description)
                        if conditions and conditions not in highlights:
                            highlights.append(conditions)
                        if valid_end:
                            highlights.append(f"有效期限：{valid_end}")
                    if highlights:
                        result["detail_highlights"] = highlights[:3]
            yield sse({
                "type": "tool_call",
                "tool": "get_card_details",
                "status": "done",
                "label": "候選卡片限制條件已補充",
            })
            yield sse(_tool_result_event(
                tool="get_card_details",
                status="success",
                summary=f"回傳 {len(card_details)} 張候選卡片詳情與限制條件",
                data=card_details,
            ))

            yield sse({
                "type": "tool_call",
                "tool": "get_promotions",
                "status": "calling",
                "label": "查詢相關通路優惠活動...",
            })
            promotions_by_channel = {
                rec["channel_id"]: _get_promotions(
                    cards_owned=cards_owned,
                    category=rec["channel_id"],
                )
                for rec in recommendations
            }
            for rec in recommendations:
                promo_result = promotions_by_channel.get(rec["channel_id"], {})
                promo_alerts = [
                    promo["title"]
                    for promo in promo_result.get("promotions", [])[:2]
                    if promo.get("title")
                ]
                expiring_alerts = [
                    f"{item['card_name']}：{channel['channel_name']}優惠即將到期"
                    for item in promo_result.get("card_channels", [])[:2]
                    for channel in item.get("channels", [])[:1]
                ]
                alerts = [*promo_alerts, *expiring_alerts][:3]
                if alerts:
                    for result in rec["best_options"]:
                        result["promotion_alerts"] = alerts
            total_promos = sum(
                len(result.get("promotions", []))
                for result in promotions_by_channel.values()
            )
            yield sse({
                "type": "tool_call",
                "tool": "get_promotions",
                "status": "done",
                "label": f"已查詢相關活動，共找到 {total_promos} 筆通路優惠",
            })
            yield sse(_tool_result_event(
                tool="get_promotions",
                status="success",
                summary=f"回傳 {len(promotions_by_channel)} 個通路的活動資料，共 {total_promos} 筆優惠",
                data=promotions_by_channel,
            ))

            yield sse({
                "type": "tool_call",
                "tool": "generate_reasons",
                "status": "calling",
                "label": "產生推薦理由中...",
            })
            from .utils.llm_parser import generate_reasons

            for rec in recommendations:
                reasons = generate_reasons(
                    scenario=scenario,
                    channel_name=rec["channel_name"],
                    amount=amount,
                    recommendations=rec["best_options"],
                )
                for result in rec["best_options"]:
                    if reasons.get(result["card_id"]):
                        result["reason"] = reasons[result["card_id"]]
            yield sse({
                "type": "tool_call",
                "tool": "generate_reasons",
                "status": "done",
                "label": "推薦理由已產生",
            })

        yield sse({"type": "thinking_done", "elapsed_seconds": round(time.time() - start_time, 1)})
        yield sse({
            "type": "result",
            "data": {
                "scenario": scenario,
                "parsed": {"channels": parsed_channels, "amount": amount},
                "amount_info": amount_info,
                "recommendations": recommendations,
                "error": None,
            },
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def api_compare(request: Request):
    """POST /api/compare — 多卡比較。"""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)

    cards_owned = body.get("cards_owned", [])
    if not cards_owned:
        return _json({"error": "cards_owned is required"}, 400)
    _, validation_error = validate_card_ids(cards_owned)
    if validation_error:
        return _json({"error": validation_error}, 400)

    result = _compare_cards(
        cards_owned=cards_owned,
        channel=body.get("channel", ""),
        amount=float(body.get("amount", 1000)),
    )
    return _json(result)


async def api_promotions(request: Request):
    """POST /api/promotions — 優惠活動查詢。"""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)

    cards_owned = body.get("cards_owned", [])
    if not cards_owned:
        return _json({"error": "cards_owned is required"}, 400)
    _, validation_error = validate_card_ids(cards_owned)
    if validation_error:
        return _json({"error": validation_error}, 400)

    result = _get_promotions(
        cards_owned=cards_owned,
        category=body.get("category", ""),
    )
    return _json(result)


async def api_card_details(request: Request):
    """POST /api/card-details — 單卡詳情。"""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "Invalid JSON body"}, 400)

    card_id = body.get("card_id", "")
    if not card_id:
        return _json({"error": "card_id is required"}, 400)

    result = _get_card_details(card_id=card_id)
    return _json(result)


# ── App setup ────────────────────────────────────────────────────────────────
# 同時掛載 REST + MCP Streamable HTTP：Claude API 的 mcp_servers 參數
# 會直接連到 /mcp/，由 FastMCP 處理 tools/list 與 tools/call。
#
# 重要：FastMCP 的 session_manager 需要 lifespan 啟動，因此外層 Starlette
# 必須繼承 streamable_http_app 的 lifespan。

mcp_app = mcp_server.streamable_http_app()

routes = [
    Route("/", home, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
    Route("/api/cards", api_cards, methods=["GET"]),
    Route("/api/search", api_search, methods=["POST"]),
    Route("/api/recommend", api_recommend, methods=["POST"]),
    Route("/api/recommend/stream", api_recommend_stream, methods=["POST"]),
    Route("/api/compare", api_compare, methods=["POST"]),
    Route("/api/promotions", api_promotions, methods=["POST"]),
    Route("/api/card-details", api_card_details, methods=["POST"]),
    Route("/api/chat", chat_endpoint, methods=["POST"]),
    Mount("/mcp", app=mcp_app),
]

app = Starlette(routes=routes, lifespan=mcp_app.router.lifespan_context)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


def main():
    """Run the unified server locally."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("mcp_server.http_app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
