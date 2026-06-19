import asyncio

import pytest

from mcp_server import http_app
from tests.recommend_stream_cases import CASES, FakeJsonRequest, _parse_sse, run_case


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_recommend_stream_returns_expected_result_and_trace(case):
    report = run_case(case)

    assert report["actual"]["amount"] == pytest.approx(report["expected"]["amount"])
    assert report["actual"]["channel_id"] == report["expected"]["channel_id"]
    assert report["actual"]["top_card_id"] == report["expected"]["top_card_id"]
    assert report["actual"]["top_card_name"] == report["expected"]["top_card_name"]
    assert report["actual"]["cashback_type"] == report["expected"]["cashback_type"]
    assert report["actual"]["estimated_cashback"] == report["expected"]["estimated_cashback"]
    assert report["actual"]["calculation_formula"] == report["expected"]["calculation_formula"]
    assert report["actual"]["winner_card_id"] == report["expected"]["top_card_id"]

    start = 0
    for expected_step in report["expected_process"]:
        try:
            start = report["actual_process"].index(expected_step, start) + 1
        except ValueError:
            pytest.fail(
                f"missing process step in order: {expected_step}; "
                f"actual={report['actual_process']}"
            )


def test_recommend_stream_rejects_off_topic_without_search_tool(monkeypatch):
    monkeypatch.setattr(http_app, "parse_scenario", lambda _: None)

    events = asyncio.run(_collect_stream_events(
        scenario="今天天氣如何？",
        cards_owned=["ctbc_c_linepay"],
    ))

    result_events = [event for event in events if event.get("type") == "result"]
    assert len(result_events) == 1
    result_data = result_events[0]["data"]

    assert "信用卡消費建議助理" in result_data["off_topic_message"]
    assert result_data["recommendations"] == []
    assert not any(
        event.get("tool") == "search_by_channel"
        for event in events
    )


def test_recommend_stream_allows_strict_fallback_with_channel_or_payment_intent(monkeypatch):
    monkeypatch.setattr(http_app, "parse_scenario", lambda _: None)

    momo_events = asyncio.run(_collect_stream_events(
        scenario="momo 3000 元",
        cards_owned=["ctbc_c_linepay", "fubon_c_momo"],
    ))
    momo_result = [event for event in momo_events if event.get("type") == "result"][0]["data"]
    assert momo_result["parsed"]["channels"][0]["channel_id"] == "ecommerce"
    assert momo_result["recommendations"]

    general_events = asyncio.run(_collect_stream_events(
        scenario="刷卡 1000 元哪張划算",
        cards_owned=["ctbc_c_linepay", "fubon_c_j"],
    ))
    general_result = [event for event in general_events if event.get("type") == "result"][0]["data"]
    assert general_result["parsed"]["channels"][0]["channel_id"] == "general"
    assert general_result["recommendations"]


async def _collect_stream_events(scenario: str, cards_owned: list[str]) -> list[dict]:
    response = await http_app.api_recommend_stream(
        FakeJsonRequest({
            "scenario": scenario,
            "cards_owned": cards_owned,
        })
    )
    chunks = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        chunks.append(chunk)
    return _parse_sse("".join(chunks))
