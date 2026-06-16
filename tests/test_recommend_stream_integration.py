import pytest

from tests.recommend_stream_cases import CASES, run_case


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
