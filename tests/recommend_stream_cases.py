from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server import http_app
from mcp_server.tools.search import search_by_channel
from mcp_server.utils import llm_parser


@dataclass(frozen=True)
class RecommendStreamCase:
    case_id: str
    title: str
    scenario: str
    cards_owned: list[str]
    parsed_channel_id: str
    parsed_merchant: str
    expected_search_query: str
    expected_amount: float
    parsed_amount: float | None = None


CASES = [
    RecommendStreamCase(
        case_id="carrefour-line-points",
        title="家樂福消費，確認 LINE POINTS 不換算現金",
        scenario="去家樂福買菜 2000 元",
        cards_owned=["ctbc_c_linepay"],
        parsed_channel_id="supermarket",
        parsed_merchant="家樂福",
        expected_search_query="家樂福",
        expected_amount=2000.0,
    ),
    RecommendStreamCase(
        case_id="pxmart-supermarket-combo",
        title="全聯消費，多卡比較超市通路最佳卡",
        scenario="全聯買菜 1500 元",
        cards_owned=[
            "ctbc_c_hanshin",
            "ctbc_c_uniopen",
            "fubon_c_costco",
            "fubon_b_lifestyle",
            "fubon_c_j",
        ],
        parsed_channel_id="supermarket",
        parsed_merchant="全聯",
        expected_search_query="全聯",
        expected_amount=1500.0,
    ),
    RecommendStreamCase(
        case_id="seven-eleven-openpoint",
        title="7-ELEVEN 小額消費，確認 OPENPOINT 不換算現金",
        scenario="在7-ELEVEN買咖啡 350 元",
        cards_owned=["ctbc_c_uniopen"],
        parsed_channel_id="convenience_store",
        parsed_merchant="7-ELEVEN",
        expected_search_query="7-ELEVEN",
        expected_amount=350.0,
    ),
    RecommendStreamCase(
        case_id="japan-jpy-overseas",
        title="日本日圓消費，確認金額換算後走海外通路",
        scenario="日本藥妝店刷卡 JPY 10000",
        cards_owned=["fubon_c_j", "ctbc_c_uniopen", "ctbc_c_cal"],
        parsed_channel_id="overseas_general",
        parsed_merchant="海外消費",
        expected_search_query="overseas_general",
        expected_amount=2200.0,
        parsed_amount=0.0,
    ),
    RecommendStreamCase(
        case_id="high-speed-rail-transport",
        title="高鐵交通消費，多卡比較交通通路最佳卡",
        scenario="高鐵車票 1500 元",
        cards_owned=["fubon_c_costco", "fubon_c_momo", "ctbc_c_linepay"],
        parsed_channel_id="transport",
        parsed_merchant="高鐵",
        expected_search_query="高鐵",
        expected_amount=1500.0,
    ),
]

EXPECTED_PROCESS = [
    "thinking_start",
    "tool_call:parse_scenario:calling",
    "tool_call:parse_scenario:done",
    "tool_call:search_by_channel:calling",
    "tool_call:search_by_channel:done",
    "tool_result:search_by_channel:success",
    "mcp_calculation:search_by_channel",
    "tool_call:get_card_details:calling",
    "tool_call:get_card_details:done",
    "tool_result:get_card_details:success",
    "tool_call:get_promotions:calling",
    "tool_call:get_promotions:done",
    "tool_result:get_promotions:success",
    "tool_call:generate_reasons:calling",
    "tool_call:generate_reasons:done",
    "thinking_done",
    "result",
]


class FakeJsonRequest:
    def __init__(self, body: dict[str, Any]):
        self._body = body

    async def json(self) -> dict[str, Any]:
        return self._body


def run_case(case: RecommendStreamCase) -> dict[str, Any]:
    expected = _expected_summary(case)
    events = asyncio.run(_collect_stream_events(case))
    actual = _actual_summary(events)

    return {
        "case_id": case.case_id,
        "title": case.title,
        "input": {
            "scenario": case.scenario,
            "cards_owned": case.cards_owned,
        },
        "expected": expected,
        "actual": actual,
        "expected_process": EXPECTED_PROCESS,
        "actual_process": [_process_step(event) for event in events],
        "events": events,
    }


def run_all_cases() -> list[dict[str, Any]]:
    return [run_case(case) for case in CASES]


def format_report(reports: list[dict[str, Any]]) -> str:
    lines = ["# Recommend Stream System I/O Test Report", ""]
    for index, report in enumerate(reports, 1):
        expected = report["expected"]
        actual = report["actual"]
        lines.extend([
            f"## {index}. {report['title']}",
            f"- Input: {report['input']['scenario']}",
            f"- Cards: {', '.join(report['input']['cards_owned'])}",
            "- Expected result: "
            f"{expected['channel_name']} / {expected['top_card_name']} / "
            f"{_rate_text(expected['cashback_rate'])} / "
            f"estimated={_cashback_text(expected['estimated_cashback'])} / "
            f"formula={expected['calculation_formula']}",
            "- Actual result: "
            f"{actual['channel_name']} / {actual['top_card_name']} / "
            f"{_rate_text(actual['cashback_rate'])} / "
            f"estimated={_cashback_text(actual['estimated_cashback'])} / "
            f"formula={actual['calculation_formula']}",
            f"- Expected process: {' -> '.join(report['expected_process'])}",
            f"- Actual process: {' -> '.join(report['actual_process'])}",
            "",
        ])
    return "\n".join(lines)


async def _collect_stream_events(case: RecommendStreamCase) -> list[dict[str, Any]]:
    original_parse_scenario = http_app.parse_scenario
    original_generate_reasons = llm_parser.generate_reasons
    http_app.parse_scenario = lambda _: _parsed_scenario(case)
    llm_parser.generate_reasons = lambda **_: {}

    try:
        response = await http_app.api_recommend_stream(
            FakeJsonRequest({
                "scenario": case.scenario,
                "cards_owned": case.cards_owned,
            })
        )
        chunks = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")
            chunks.append(chunk)
        return _parse_sse("".join(chunks))
    finally:
        http_app.parse_scenario = original_parse_scenario
        llm_parser.generate_reasons = original_generate_reasons


def _parsed_scenario(case: RecommendStreamCase) -> dict[str, Any]:
    amount = case.expected_amount if case.parsed_amount is None else case.parsed_amount
    return {
        "is_consumption_scenario": True,
        "channels": [{
            "channel_id": case.parsed_channel_id,
            "merchant_or_keyword": case.parsed_merchant,
        }],
        "amount": amount,
    }


def _parse_sse(stream_text: str) -> list[dict[str, Any]]:
    events = []
    for block in stream_text.split("\n\n"):
        data_lines = [
            line.removeprefix("data:").strip()
            for line in block.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        events.append(json.loads("\n".join(data_lines)))
    return events


def _expected_summary(case: RecommendStreamCase) -> dict[str, Any]:
    result = search_by_channel(
        channel=case.expected_search_query,
        cards_owned=case.cards_owned,
        amount=case.expected_amount,
        top_k=3,
    )
    if result.get("error"):
        raise AssertionError(result["error"])
    if not result.get("results"):
        raise AssertionError(f"{case.case_id} did not produce expected candidates")

    top = result["results"][0]
    trace = top.get("calculation_trace") or {}
    return {
        "amount": result["amount"],
        "channel_id": result["channel_id"],
        "channel_name": result["channel_name"],
        "top_card_id": top["card_id"],
        "top_card_name": top["card_name"],
        "cashback_rate": top.get("cashback_rate"),
        "cashback_type": top.get("cashback_type"),
        "estimated_cashback": top.get("estimated_cashback"),
        "calculation_formula": trace.get("formula"),
    }


def _actual_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    result_event = _first_event(events, "result")
    data = result_event["data"]
    if data.get("error"):
        raise AssertionError(data["error"])
    if not data.get("recommendations"):
        raise AssertionError("stream did not produce recommendations")

    recommendation = data["recommendations"][0]
    top = recommendation["best_options"][0]
    calculation = _first_event(events, "mcp_calculation")
    winner = calculation.get("winner") or {}
    trace = top.get("calculation_trace") or {}

    return {
        "amount": data["parsed"]["amount"],
        "amount_display": data.get("amount_info", {}).get("amount_display"),
        "channel_id": recommendation["channel_id"],
        "channel_name": recommendation["channel_name"],
        "top_card_id": top["card_id"],
        "top_card_name": top["card_name"],
        "cashback_rate": top.get("cashback_rate"),
        "cashback_type": top.get("cashback_type"),
        "estimated_cashback": top.get("estimated_cashback"),
        "calculation_formula": trace.get("formula") or winner.get("formula"),
        "winner_card_id": winner.get("card_id"),
    }


def _first_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for event in events:
        if event.get("type") == event_type:
            return event
    raise AssertionError(f"missing event type: {event_type}")


def _process_step(event: dict[str, Any]) -> str:
    event_type = event.get("type")
    if event_type in {"tool_call", "tool_result"}:
        return f"{event_type}:{event.get('tool')}:{event.get('status')}"
    if event_type == "mcp_calculation":
        return f"mcp_calculation:{event.get('tool')}"
    return str(event_type)


def _rate_text(rate: float | None) -> str:
    if rate is None:
        return "rate=N/A"
    return f"rate={rate * 100:g}%"


def _cashback_text(value: float | None) -> str:
    if value is None:
        return "None"
    return f"NT$ {value:g}"


if __name__ == "__main__":
    print(format_report(run_all_cases()))
