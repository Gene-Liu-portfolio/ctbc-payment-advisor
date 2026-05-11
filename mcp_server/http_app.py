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

import os

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

from .chat import chat_endpoint
from .server import mcp as mcp_server
from .tools.compare import compare_cards as _compare_cards
from .tools.promotions import get_card_details as _get_card_details
from .tools.promotions import get_promotions as _get_promotions
from .tools.recommend import recommend_payment as _recommend_payment
from .tools.search import search_by_channel as _search_by_channel
from .utils.data_loader import get_cards_menu, get_data_summary


# ── Public routes ────────────────────────────────────────────────────────────

async def home(_: Request):
    return JSONResponse({
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

    result = _recommend_payment(scenario=scenario, cards_owned=cards_owned)
    return _json(result)


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
    Route("/api/compare", api_compare, methods=["POST"]),
    Route("/api/promotions", api_promotions, methods=["POST"]),
    Route("/api/card-details", api_card_details, methods=["POST"]),
    Route("/api/chat", chat_endpoint, methods=["POST"]),
    Mount("/mcp", app=mcp_app),
]

app = Starlette(routes=routes, lifespan=mcp_app.router.lifespan_context)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
