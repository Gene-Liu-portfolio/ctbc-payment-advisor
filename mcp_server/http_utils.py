"""Small HTTP helpers shared by the unified ASGI app."""

from __future__ import annotations

import os

from starlette.responses import JSONResponse

DEFAULT_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def json_response(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or DEFAULT_ALLOWED_ORIGINS.split(",")


def format_cashback_value(value) -> str:
    if value is None:
        return "未計算"
    return f"{float(value):g}"
