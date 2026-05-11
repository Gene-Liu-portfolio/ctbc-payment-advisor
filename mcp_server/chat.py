"""
chat.py
-------
React 前端 chat 端點：Anthropic Messages API + MCP Connector + SSE 串流。

Claude 透過 `mcp_servers` 參數直接以 MCP 協定連到本服務的 /mcp，不再經過
agent/mcp_bridge.py 的 function-calling 包裝層。

SSE 事件型別：
  - `text`       → 文字增量（assistant 回覆）
  - `tool_use`   → Claude 呼叫 MCP 工具（tool_name, input）
  - `tool_result`→ 工具執行結果（content 摘要）
  - `done`       → 串流結束（stop_reason）
  - `error`      → 錯誤（message）
"""

from __future__ import annotations

import json
import os
from typing import AsyncIterator

from anthropic import AsyncAnthropic
from starlette.requests import Request
from starlette.responses import StreamingResponse


DEFAULT_MODEL = os.getenv("CLAUDE_AGENT_MODEL", "claude-sonnet-4-6")
MCP_PUBLIC_URL = os.getenv(
    "MCP_PUBLIC_URL",
    "https://ctbc-payment-advisor.onrender.com/mcp",
)
MCP_BETA_HEADER = "mcp-client-2025-04-04"


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


async def _stream_chat(
    user_message: str,
    history: list[dict],
    cards_info: list[dict],
) -> AsyncIterator[bytes]:
    """呼叫 Anthropic Messages API（MCP Connector），逐塊 yield SSE。"""
    client = AsyncAnthropic()
    system_prompt = _build_system_prompt(cards_info)

    messages = list(history) + [{"role": "user", "content": user_message}]

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
                    btype = getattr(block, "type", None)
                    if btype == "mcp_tool_use":
                        yield _sse("tool_use", {
                            "tool_name": getattr(block, "name", ""),
                            "server_name": getattr(block, "server_name", ""),
                            "input": getattr(block, "input", {}),
                        })

                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    dtype = getattr(delta, "type", None)
                    if dtype == "text_delta":
                        yield _sse("text", {"text": getattr(delta, "text", "")})

                elif etype == "content_block_stop":
                    # MCP tool 結果在 stop 後可從 final message 取得，這裡先不發
                    pass

                elif etype == "message_stop":
                    final = await stream.get_final_message()
                    for block in final.content:
                        if getattr(block, "type", None) == "mcp_tool_result":
                            content = getattr(block, "content", [])
                            summary = ""
                            for c in content:
                                if getattr(c, "type", None) == "text":
                                    summary = getattr(c, "text", "")[:500]
                                    break
                            yield _sse("tool_result", {
                                "tool_use_id": getattr(block, "tool_use_id", ""),
                                "is_error": getattr(block, "is_error", False),
                                "summary": summary,
                            })
                    yield _sse("done", {"stop_reason": final.stop_reason})

    except Exception as e:
        yield _sse("error", {"message": str(e), "type": type(e).__name__})


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
    cards_info = body.get("cards_owned", [])
    history = body.get("history", [])

    if not message:
        return StreamingResponse(
            iter([_sse("error", {"message": "message is required"})]),
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
