from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server.chat import (
    _build_system_prompt,
    _extract_recommendation_data,
    chat_endpoint,
)
from mcp_server.utils.data_loader import validate_card_ids


class FakeJsonRequest:
    def __init__(self, body: dict[str, Any]):
        self._body = body

    async def json(self) -> dict[str, Any]:
        return self._body


def test_chat_endpoint_rejects_unknown_card_id_with_sse_error():
    events = asyncio.run(_call_chat_endpoint({
        "message": "全聯 1000 元用哪張卡？",
        "cards_owned": [{"card_id": "not_a_real_card", "card_name": "偽造卡"}],
        "history": [],
    }))

    assert events == [
        {
            "event": "error",
            "data": {
                "type": "api_invalid_request",
                "message": "找不到您持有的卡片資料：not_a_real_card",
            },
        }
    ]


def test_chat_endpoint_is_disabled_without_explicit_agent_flag():
    events = asyncio.run(_call_chat_endpoint({
        "message": "全聯 1000 元用哪張卡？",
        "cards_owned": [{"card_id": "ctbc_c_linepay", "card_name": "偽造名稱"}],
        "history": [],
    }))

    assert events == [
        {
            "event": "error",
            "data": {
                "type": "api_disabled",
                "message": (
                    "Agent chat is disabled on this backend. Use the public /mcp endpoint "
                    "from a remote MCP client, or enable ENABLE_AGENT_CHAT=true on a private backend."
                ),
            },
        }
    ]


def test_chat_system_prompt_uses_canonical_backend_card_names():
    cards_info, validation_error = validate_card_ids(["ctbc_c_linepay"])

    assert validation_error is None

    prompt = _build_system_prompt(cards_info)

    assert "LINE Pay信用卡（ID: ctbc_c_linepay）" in prompt
    assert "偽造 LINE Pay 名稱" not in prompt
    assert "cards_owned 參數【固定且只能使用】：['ctbc_c_linepay']" in prompt


def test_extract_recommendation_data_from_search_tool_result():
    parsed = {
        "channel_id": "supermarket",
        "channel_name": "超市／量販",
        "results": [
            {
                "card_id": "fubon_b_lifestyle",
                "card_name": "富邦富利生活卡",
                "estimated_cashback": 30,
            }
        ],
    }

    data = _extract_recommendation_data(
        "ctbc-payment-advisor__search_by_channel",
        parsed,
    )

    assert data == {
        "source_tool": "search_by_channel",
        "recommendations": [
            {
                "channel_name": "超市／量販",
                "channel_id": "supermarket",
                "best_options": parsed["results"],
            }
        ],
    }


def test_extract_recommendation_data_from_recommend_payment_tool_result():
    parsed = {
        "parsed": {"amount": 1500},
        "recommendations": [
            {
                "channel_name": "交通",
                "channel_id": "transport",
                "best_options": [{"card_id": "fubon_c_costco"}],
            }
        ],
    }

    data = _extract_recommendation_data("recommend_payment", parsed)

    assert data == {
        "source_tool": "recommend_payment",
        "parsed": {"amount": 1500},
        "recommendations": parsed["recommendations"],
    }


def test_extract_recommendation_data_from_compare_cards_tool_result_sorts_options():
    parsed = {
        "comparison": [
            {
                "channel_name": "交通",
                "channel_id": "transport",
                "card_rates": [
                    {
                        "card_id": "ctbc_c_linepay",
                        "estimated_cashback": None,
                        "cashback_rate": 0.03,
                    },
                    {
                        "card_id": "fubon_c_costco",
                        "estimated_cashback": 120,
                        "cashback_rate": 0.08,
                    },
                ],
            }
        ]
    }

    data = _extract_recommendation_data("compare_cards", parsed)

    assert data["source_tool"] == "compare_cards"
    best_options = data["recommendations"][0]["best_options"]
    assert [item["card_id"] for item in best_options] == [
        "fubon_c_costco",
        "ctbc_c_linepay",
    ]


async def _call_chat_endpoint(body: dict[str, Any]) -> list[dict[str, Any]]:
    response = await chat_endpoint(FakeJsonRequest(body))
    chunks = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        chunks.append(chunk)
    return _parse_named_sse("".join(chunks))


def _parse_named_sse(stream_text: str) -> list[dict[str, Any]]:
    events = []
    for block in stream_text.split("\n\n"):
        event_name = "message"
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        if data_lines:
            events.append({
                "event": event_name,
                "data": json.loads("\n".join(data_lines)),
            })
    return events
