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

import os

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from .tools.search import search_by_channel as _search_by_channel
from .tools.recommend import recommend_payment as _recommend_payment
from .tools.compare import compare_cards as _compare_cards
from .tools.promotions import get_promotions as _get_promotions
from .tools.promotions import get_card_details as _get_card_details
from .utils.data_loader import get_cards_menu, get_data_summary


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
