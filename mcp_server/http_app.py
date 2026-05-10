"""
http_app.py
-----------
獨立的 REST API 伺服器，供 React 前端串接。

不依賴 FastMCP 的 custom_route，改用純 Starlette 建立 ASGI app，
避免 FastMCP import 時的 event-loop 阻塞問題。

預設提供：
  - GET  /            → 服務資訊
  - GET  /health      → 健康檢查
  - GET  /api/cards   → REST: 卡片清單
  - POST /api/search  → REST: 通路最優卡查詢
  - POST /api/recommend → REST: 情境推薦
  - POST /api/compare → REST: 多卡比較
  - POST /api/promotions → REST: 優惠活動
  - POST /api/card-details → REST: 單卡詳情

啟動方式：
    python -m mcp_server.http_app
"""

from __future__ import annotations

import json
import os
import time

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, StreamingResponse
from starlette.routing import Route

from .tools.search import search_by_channel as _search_by_channel
from .tools.recommend import recommend_payment as _recommend_payment
from .tools.compare import compare_cards as _compare_cards
from .tools.promotions import get_promotions as _get_promotions
from .tools.promotions import get_card_details as _get_card_details
from .utils.data_loader import get_cards_menu, get_data_summary
from .utils.llm_parser import parse_scenario
from .utils.channel_mapper import MERCHANT_TO_CHANNEL, normalize_merchant
from .tools.search import _resolve_channel, _channel_display_name


# ── Public routes ────────────────────────────────────────────────────────────

async def home(_: Request):
    return JSONResponse({
        "service": "CTBC Payment Advisor REST API",
        "health": "/health",
        "rest_api": "/api/cards",
    })


async def health(_: Request):
    return PlainTextResponse("ok")


# ── REST API routes ──────────────────────────────────────────────────────────

def _json(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


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

    result = _search_by_channel(
        channel=body.get("channel", "general"),
        cards_owned=cards_owned,
        amount=float(body.get("amount", 0)),
        top_k=int(body.get("top_k", 3)),
    )
    return _json(result)


async def api_recommend(request: Request):
    """POST /api/recommend — 情境推薦。"""
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

    result = _recommend_payment(scenario=scenario, cards_owned=cards_owned)
    return _json(result)


async def api_recommend_stream(request: Request):
    """POST /api/recommend/stream — 情境推薦（SSE 串流，顯示思考過程）。"""
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

    async def event_generator():
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        start_time = time.time()
        yield sse({"type": "thinking_start"})

        # ── Step 1: 解析消費情境 ──────────────────────────────────────────
        yield sse({"type": "tool_call", "tool": "parse_scenario", "status": "calling",
                   "label": "解析消費情境中..."})

        llm_parsed = parse_scenario(scenario)

        parsed_channels = []
        amount = 0.0

        if llm_parsed is not None and not llm_parsed.get("is_consumption_scenario", True):
            # Off-topic: mark parse_scenario as done before stopping
            yield sse({"type": "tool_call", "tool": "parse_scenario", "status": "done",
                       "label": "已識別為非信用卡相關問題"})
            yield sse({"type": "thinking_done", "elapsed_seconds": round(time.time() - start_time, 1)})
            yield sse({
                "type": "result",
                "data": {
                    "scenario": scenario,
                    "parsed": {"channels": [], "amount": 0},
                    "recommendations": [],
                    "off_topic_message": llm_parsed.get("off_topic_message", ""),
                    "error": None,
                }
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
            # Fallback: regex
            import re
            amount_pattern = re.compile(
                r"(?:NT\$|新台幣|花(?:了|費)?|消費|共|約|大概)?\s*([\d,]+)\s*(?:元|塊|円)?"
            )
            candidates = []
            for m in amount_pattern.finditer(scenario):
                raw = m.group(1).replace(",", "")
                try:
                    val = float(raw)
                    if 1 <= val <= 10_000_000:
                        candidates.append(val)
                except ValueError:
                    pass
            amount = max(candidates) if candidates else 0.0
            parsed_channels = [{"name": "一般消費", "channel_id": "general"}]

        channels_display = [ch["name"] for ch in parsed_channels]
        yield sse({"type": "tool_call", "tool": "parse_scenario", "status": "done",
                   "label": f"識別通路：{' | '.join(channels_display)}，金額：NT$ {int(amount) if amount else '未指定'}",
                   "channels": channels_display, "amount": amount})

        # ── Step 2: 對每個通路查最佳卡片 ────────────────────────────────────
        recommendations = []
        for ch in parsed_channels:
            channel_name = _channel_display_name(ch["channel_id"], ch["name"])
            yield sse({"type": "tool_call", "tool": "search_by_channel", "status": "calling",
                       "label": f"查詢「{channel_name}」通路最佳卡片...",
                       "channel": channel_name})

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
                yield sse({"type": "tool_call", "tool": "search_by_channel", "status": "done",
                           "label": f"「{channel_name}」找到 {len(result['results'])} 張卡，最高回饋：{top_card}",
                           "channel": channel_name, "result_count": len(result["results"])})
                recommendations.append({
                    "channel_name": channel_name,
                    "channel_id": ch["channel_id"],
                    "best_options": result["results"],
                })
            else:
                yield sse({"type": "tool_call", "tool": "search_by_channel", "status": "done",
                           "label": f"「{channel_name}」無符合結果",
                           "channel": channel_name, "result_count": 0})

        # ── Step 3: 產生推薦理由 ─────────────────────────────────────────────
        if recommendations:
            yield sse({"type": "tool_call", "tool": "generate_reasons", "status": "calling",
                       "label": "產生推薦理由中..."})
            from .utils.llm_parser import generate_reasons
            for rec in recommendations:
                reasons = generate_reasons(
                    scenario=scenario,
                    channel_name=rec["channel_name"],
                    amount=amount,
                    recommendations=rec["best_options"],
                )
                for r in rec["best_options"]:
                    if reasons.get(r["card_id"]):
                        r["reason"] = reasons[r["card_id"]]
            yield sse({"type": "tool_call", "tool": "generate_reasons", "status": "done",
                       "label": "推薦理由已產生"})

        elapsed = round(time.time() - start_time, 1)
        yield sse({"type": "thinking_done", "elapsed_seconds": elapsed})

        yield sse({
            "type": "result",
            "data": {
                "scenario": scenario,
                "parsed": {"channels": parsed_channels, "amount": amount},
                "recommendations": recommendations,
                "error": None,
            }
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
]

app = Starlette(routes=routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def main():
    """Run the REST API server locally."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("mcp_server.http_app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
