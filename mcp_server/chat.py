"""
chat.py
-------
React 前端 chat 端點：Anthropic Messages API + MCP Connector + SSE 串流。

Claude 透過 `mcp_servers` 參數直接以 MCP 協定連到本服務的 /mcp，不再經過
agent/mcp_bridge.py 的 function-calling 包裝層。

SSE 事件型別：
  - `text`       → 文字增量（assistant 回覆）
  - `tool_use`   → Claude 呼叫 MCP 工具（id, tool_name, server_name, input）
                  ※ input 已累積完整 JSON 才發出，便於前端顯示 Claude 實際傳入的參數
                  ※ id 可用於與 tool_result.tool_use_id 配對
  - `tool_result`→ 工具執行結果（tool_use_id, is_error, summary）
                  ※ 工具一執行完即發，不等到 message_stop，讓前端能即時對齊
  - `done`       → 串流結束（stop_reason）
  - `error`      → 錯誤（type, message, raw_type[, status_code]）
                  type 列舉：mcp_connection_failed / api_connection_failed /
                            api_rate_limit / api_invalid_request / api_error / unknown
"""

from __future__ import annotations

import json
import os
from typing import AsyncIterator

from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    BadRequestError,
    RateLimitError,
)
from starlette.requests import Request
from starlette.responses import StreamingResponse

from .utils.data_loader import validate_card_ids


DEFAULT_MODEL = os.getenv("CLAUDE_AGENT_MODEL", "claude-sonnet-4-6")
MCP_PUBLIC_URL = os.getenv(
    "MCP_PUBLIC_URL",
    "https://ctbc-payment-advisor.onrender.com/mcp",
)
MCP_BETA_HEADER = "mcp-client-2025-04-04"
RESULT_TRUNCATE_LIMIT = 2000  # tool_result.summary 字元上限，避免一次塞太大塊


def _parse_json_text(text: str):
    """Parse JSON-looking MCP text content; return None when it is plain text."""
    trimmed = text.strip()
    if not trimmed or trimmed[0] not in "[{":
        return None
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        return None


def _extract_recommendation_data(tool_name: str, parsed):
    """Normalize MCP tool JSON into data the frontend can render as recommendation cards."""
    if not isinstance(parsed, dict):
        return None

    normalized_tool = tool_name.split("__")[-1]

    if normalized_tool == "search_by_channel" and isinstance(parsed.get("results"), list):
        channel_name = parsed.get("channel_name") or parsed.get("query") or "查詢通路"
        return {
            "source_tool": normalized_tool,
            "recommendations": [
                {
                    "channel_name": channel_name,
                    "channel_id": parsed.get("channel_id"),
                    "best_options": parsed.get("results", []),
                }
            ],
        }

    if normalized_tool == "recommend_payment" and isinstance(parsed.get("recommendations"), list):
        return {
            "source_tool": normalized_tool,
            "parsed": parsed.get("parsed"),
            "recommendations": parsed.get("recommendations", []),
        }

    if normalized_tool == "compare_cards" and isinstance(parsed.get("comparison"), list):
        recommendations = []
        for comparison in parsed.get("comparison", []):
            results = comparison.get("card_rates") or []
            results = sorted(
                results,
                key=lambda item: (
                    item.get("estimated_cashback") or 0,
                    item.get("cashback_rate") or 0,
                ),
                reverse=True,
            )
            if results:
                recommendations.append({
                    "channel_name": comparison.get("channel_name") or comparison.get("channel") or "比較結果",
                    "channel_id": comparison.get("channel_id"),
                    "best_options": results,
                })
        if recommendations:
            return {
                "source_tool": normalized_tool,
                "recommendations": recommendations,
            }

    return None


def _build_system_prompt(cards_info: list[dict]) -> str:
    """根據持卡資訊建立 System Prompt，嚴格限制 cards_owned 範圍。"""
    if not cards_info:
        card_list_text = "  （使用者未選擇任何卡片）"
    else:
        card_list_text = "\n".join(
            f"  - {c['card_name']}（ID: {c['card_id']}）"
            for c in cards_info
        )

    card_ids = [c["card_id"] for c in cards_info]

    return f"""你是中國信託銀行（CTBC）的信用卡支付建議助理。

【使用者目前持有的信用卡】
{card_list_text}

【你的職責】
1. 根據使用者描述的消費情境（通路、金額、需求），從持有卡中推薦最適合的卡片
2. 清楚說明推薦理由（回饋率、預估回饋金額）
3. 提醒優惠條件（回饋上限、截止日期、需登錄等注意事項）
4. 若有多個消費通路，分別針對每個通路給出建議

【工具使用規則】
- 呼叫任何工具時，cards_owned 參數【固定且只能使用】：{card_ids}
- 絕對禁止在 cards_owned 中加入使用者未持有的卡片
- 若使用者詢問某個通路，優先使用 search_by_channel 工具
- 若使用者詢問整體比較或「我的卡哪張最划算」，使用 compare_cards 工具
- 若使用者詢問優惠活動或即將到期的優惠，使用 get_promotions 工具
- 若使用者問到某張卡的詳細資料，使用 get_card_details 工具
- 若需要解析自然語言情境（多通路、金額抽取），使用 recommend_payment 工具

【嚴格限制】
- 只能推薦使用者「持有」的卡片，不得推薦清單以外的卡
- 若持有卡中無適合的優惠，誠實告知，不要強行推薦
- 資料可能有所更新，最終以中信官網為準
- 不得虛構優惠內容或工具未回傳的數字
- 若使用者問題與信用卡、消費、刷卡推薦無關（如天氣、新聞、技術問題、純粹閒聊等），禮貌說明你只能協助消費相關問題，並給出範例引導（如：「想知道去全聯買菜該用哪張卡嗎？」）；【不得】呼叫任何工具

【回覆格式】
- 使用繁體中文，語氣親切、專業、簡潔
- 推薦時必須包含：卡名稱、回饋率（或回饋描述）與預估金額
- **若工具回傳結果的 conditions 欄位有任何文字（特別是帶 ⚠️ 警告符號），必須一字不漏地向使用者說明該條件，絕不可省略**
- **若第一推薦順位的卡片帶有條件限制，必須從結果中挑選下一順位作為「備案卡片」推薦並比較差異**
- **若工具結果標示 `is_fallback: true`，代表該卡沒有針對此通路的專屬回饋，必須主動說明此事（如：此卡無專屬網購優惠，將以一般消費計算）**
- 回饋率請用百分比表示（如 5%）
- 若優惠即將到期（或 `expiring_soon: true`），主動提醒把握時機"""


def _sse(event: str, data: dict) -> bytes:
    """格式化為 SSE event。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _extract_card_ids(raw_cards) -> list[str]:
    """Accept legacy chat card payloads and return card ids only."""
    card_ids = []
    for item in raw_cards or []:
        if isinstance(item, dict):
            card_id = item.get("card_id")
        else:
            card_id = str(item)
        if card_id:
            card_ids.append(card_id)
    return card_ids


def _classify_error(exc: Exception) -> dict:
    """把 Anthropic SDK 例外分類為前端可辨識的 error payload。"""
    msg = str(exc)
    raw_type = type(exc).__name__
    lowered = msg.lower()
    looks_like_mcp = "mcp" in lowered or "connector" in lowered

    if isinstance(exc, APIConnectionError):
        if looks_like_mcp:
            return {"type": "mcp_connection_failed", "message": f"MCP 工具伺服器連線失敗：{msg}", "raw_type": raw_type}
        return {"type": "api_connection_failed", "message": f"無法連線至 Claude API：{msg}", "raw_type": raw_type}

    if isinstance(exc, RateLimitError):
        return {"type": "api_rate_limit", "message": "Claude API 流量限制（429），請稍後再試", "raw_type": raw_type}

    if isinstance(exc, BadRequestError):
        return {"type": "api_invalid_request", "message": f"Claude API 參數錯誤：{msg}", "raw_type": raw_type}

    if isinstance(exc, APIStatusError):
        if looks_like_mcp:
            return {
                "type": "mcp_connection_failed",
                "message": f"MCP 工具伺服器錯誤（{exc.status_code}）：{msg}",
                "raw_type": raw_type,
                "status_code": exc.status_code,
            }
        return {
            "type": "api_error",
            "message": f"Claude API 錯誤（{exc.status_code}）：{msg}",
            "raw_type": raw_type,
            "status_code": exc.status_code,
        }

    return {"type": "unknown", "message": msg or "未知錯誤", "raw_type": raw_type}


async def _stream_chat(
    user_message: str,
    history: list[dict],
    cards_info: list[dict],
) -> AsyncIterator[bytes]:
    """呼叫 Anthropic Messages API（MCP Connector），逐塊 yield SSE。"""
    client = AsyncAnthropic()
    system_prompt = _build_system_prompt(cards_info)

    messages = list(history) + [{"role": "user", "content": user_message}]

    # 以 content block index 追蹤每個 mcp_tool_use 的 input 累積狀態
    pending_tool_uses: dict[int, dict] = {}
    emitted_tool_uses: dict[str, dict] = {}

    try:
        async with client.beta.messages.stream(
            model=DEFAULT_MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            mcp_servers=[
                {
                    "type": "url",
                    "url": MCP_PUBLIC_URL,
                    "name": "ctbc-payment-advisor",
                }
            ],
            betas=[MCP_BETA_HEADER],
        ) as stream:
            async for event in stream:
                etype = getattr(event, "type", None)

                if etype == "content_block_start":
                    block = getattr(event, "content_block", None)
                    idx = getattr(event, "index", None)
                    btype = getattr(block, "type", None)

                    if btype == "mcp_tool_use" and idx is not None:
                        # 暫存 tool_use 區塊，等 input JSON delta 累積完整再 emit
                        pending_tool_uses[idx] = {
                            "id": getattr(block, "id", ""),
                            "name": getattr(block, "name", ""),
                            "server_name": getattr(block, "server_name", ""),
                            "input_buffer": "",
                        }

                    elif btype == "mcp_tool_result":
                        # 工具結果為原子內容，抵達即立刻發給前端
                        content = getattr(block, "content", []) or []
                        summary = ""
                        full_text = ""
                        for c in content:
                            if getattr(c, "type", None) == "text":
                                full_text = getattr(c, "text", "")
                                summary = full_text[:RESULT_TRUNCATE_LIMIT]
                                break
                        tool_use_id = getattr(block, "tool_use_id", "")
                        tool_info = emitted_tool_uses.get(tool_use_id, {})
                        tool_name = tool_info.get("tool_name", "")
                        parsed = _parse_json_text(full_text)
                        yield _sse("tool_result", {
                            "tool_use_id": tool_use_id,
                            "tool_name": tool_name,
                            "input": tool_info.get("input"),
                            "is_error": getattr(block, "is_error", False),
                            "summary": summary,
                            "data": _extract_recommendation_data(tool_name, parsed),
                        })

                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    idx = getattr(event, "index", None)
                    dtype = getattr(delta, "type", None)

                    if dtype == "text_delta":
                        yield _sse("text", {"text": getattr(delta, "text", "")})

                    elif dtype == "input_json_delta" and idx in pending_tool_uses:
                        pending_tool_uses[idx]["input_buffer"] += getattr(delta, "partial_json", "")

                elif etype == "content_block_stop":
                    idx = getattr(event, "index", None)
                    if idx in pending_tool_uses:
                        info = pending_tool_uses.pop(idx)
                        buf = info["input_buffer"]
                        try:
                            input_data = json.loads(buf) if buf.strip() else {}
                        except json.JSONDecodeError:
                            input_data = {"_raw": buf}
                        yield _sse("tool_use", {
                            "id": info["id"],
                            "tool_name": info["name"],
                            "server_name": info["server_name"],
                            "input": input_data,
                        })
                        emitted_tool_uses[info["id"]] = {
                            "tool_name": info["name"],
                            "server_name": info["server_name"],
                            "input": input_data,
                        }

                elif etype == "message_stop":
                    final = await stream.get_final_message()
                    yield _sse("done", {"stop_reason": final.stop_reason})

    except Exception as exc:
        yield _sse("error", _classify_error(exc))


async def chat_endpoint(request: Request):
    """POST /api/chat — SSE 串流回應。

    Body: {
        "message": str,
        "cards_owned": list[{"card_id", "card_name"}],
        "history": list[{"role", "content"}]  # Claude messages 格式
    }
    """
    try:
        body = await request.json()
    except Exception:
        return StreamingResponse(
            iter([_sse("error", {"message": "Invalid JSON body"})]),
            media_type="text/event-stream",
        )

    message = body.get("message", "").strip()
    raw_cards_info = body.get("cards_owned", [])
    history = body.get("history", [])

    if not message:
        return StreamingResponse(
            iter([_sse("error", {"message": "message is required"})]),
            media_type="text/event-stream",
        )

    cards_info, validation_error = validate_card_ids(_extract_card_ids(raw_cards_info))
    if validation_error:
        return StreamingResponse(
            iter([_sse("error", {"type": "api_invalid_request", "message": validation_error})]),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        _stream_chat(message, history, cards_info),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
