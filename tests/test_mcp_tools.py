"""
tests/test_mcp_tools.py
-----------------------
MCP Tool 單元測試：直接呼叫 Python 函式，不經 LLM，確定性驗證。

執行方式：
    source venv/bin/activate
    python -m pytest tests/test_mcp_tools.py -v          # 全部
    python -m pytest tests/test_mcp_tools.py -v -k search  # 只跑 search
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import jsonschema

# 確保 project root 在 sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
SCHEMA_PATH = PROJECT_ROOT / "data" / "schemas" / "card_schema.json"
MERGED_CARDS_PATH = PROJECT_ROOT / "data" / "processed" / "merged_cards.json"

# ── 被測模組 ───────────────────────────────────────────────────────────────
from mcp_server.tools.search import _build_calculation_trace, search_by_channel
from mcp_server.tools.recommend import recommend_payment, _extract_amount, _extract_channels
from mcp_server.tools.compare import compare_cards
from mcp_server.tools.promotions import get_promotions, get_card_details
from mcp_server.tool_trace import compact_search_result, tool_result_event
from mcp_server.utils import llm_parser
from mcp_server.utils.llm_parser import _VALID_CHANNEL_IDS as LLM_VALID_CHANNEL_IDS
from mcp_server.utils.data_loader import (
    get_all_cards, get_card_by_id, get_cards_by_ids,
    get_cards_menu, get_best_channel_for_card, get_best_deal_for_card,
    get_data_summary,
)
from mcp_server.utils.calculator import calc_estimated_cashback, is_expiring_soon, is_expired

# ── 測試用常數 ─────────────────────────────────────────────────────────────

# 現有 13 張卡的 card_id
CTBC_CARDS = [
    "ctbc_c_hanshin", "ctbc_c_uniopen", "ctbc_c_cs",
    "ctbc_c_linepay", "ctbc_c_cal", "ctbc_c_cpc",
]
FUBON_CARDS = [
    "fubon_c_j", "fubon_c_guardians", "fubon_c_costco",
    "fubon_c_diamond", "fubon_c_momo", "fubon_b_lifestyle", "fubon_c_twm",
]
ALL_CARD_IDS = CTBC_CARDS + FUBON_CARDS

# 常用測試組合
COMBO_3 = ["ctbc_c_linepay", "fubon_c_j", "fubon_c_momo"]
COMBO_5 = ["ctbc_c_hanshin", "ctbc_c_uniopen", "fubon_c_costco", "fubon_b_lifestyle", "fubon_c_j"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. calculator.py 測試
# ═══════════════════════════════════════════════════════════════════════════

class TestCalculator:
    """calc_estimated_cashback / is_expiring_soon / is_expired"""

    def test_basic_cashback(self):
        assert calc_estimated_cashback(1000, 0.03, None) == 30.0

    def test_cashback_with_cap(self):
        assert calc_estimated_cashback(10000, 0.05, 300) == 300.0

    def test_cashback_below_cap(self):
        assert calc_estimated_cashback(1000, 0.05, 300) == 50.0

    def test_cashback_rate_none(self):
        assert calc_estimated_cashback(1000, None, None) is None

    def test_cashback_rate_zero(self):
        assert calc_estimated_cashback(1000, 0.0, None) is None

    def test_cashback_amount_zero(self):
        # 0 * 0.05 = 0.0（rate > 0 所以不回傳 None，而是 0.0）
        assert calc_estimated_cashback(0, 0.05, None) == 0.0

    def test_is_expiring_soon_none(self):
        assert is_expiring_soon(None) is False

    def test_is_expired_none(self):
        assert is_expired(None) is False

    def test_is_expired_past_date(self):
        assert is_expired("2020-01-01") is True

    def test_is_expired_future_date(self):
        assert is_expired("2099-12-31") is False

    def test_is_expiring_soon_far_future(self):
        assert is_expiring_soon("2099-12-31") is False

    def test_invalid_date_format(self):
        assert is_expired("not-a-date") is False
        assert is_expiring_soon("not-a-date") is False


# ═══════════════════════════════════════════════════════════════════════════
# 2. data_loader.py 測試
# ═══════════════════════════════════════════════════════════════════════════

class TestDataLoader:
    """merged_cards.json 資料載入與查詢"""

    def test_get_all_cards_count(self):
        cards = get_all_cards()
        assert len(cards) == 13

    def test_get_all_cards_has_required_fields(self):
        for card in get_all_cards():
            assert "card_id" in card
            assert "card_name" in card
            assert "channels" in card

    def test_get_card_by_id_exists(self):
        card = get_card_by_id("ctbc_c_linepay")
        assert card is not None
        assert card["card_name"] == "LINE Pay信用卡"

    def test_get_card_by_id_not_exists(self):
        assert get_card_by_id("nonexistent_card") is None

    def test_get_cards_by_ids_partial(self):
        """部分有效、部分無效的 card_id 列表"""
        cards = get_cards_by_ids(["ctbc_c_linepay", "invalid_id", "fubon_c_j"])
        assert len(cards) == 2
        ids = {c["card_id"] for c in cards}
        assert "ctbc_c_linepay" in ids
        assert "fubon_c_j" in ids

    def test_get_cards_by_ids_empty(self):
        assert get_cards_by_ids([]) == []

    def test_get_cards_menu_active_only(self):
        menu = get_cards_menu()
        assert len(menu) >= 1
        for item in menu:
            assert "card_id" in item
            assert "card_name" in item
            assert item["bank_id"] in {"ctbc", "fubon"}
            assert "last_verified" in item
            assert "data_source" in item

    def test_get_cards_menu_has_canonical_bank_ids(self):
        menu_by_id = {item["card_id"]: item for item in get_cards_menu()}

        assert menu_by_id["ctbc_c_linepay"]["bank_id"] == "ctbc"
        assert menu_by_id["fubon_c_j"]["bank_id"] == "fubon"

    def test_get_data_summary(self):
        summary = get_data_summary()
        assert summary["card_count"] == 13
        assert summary["version"] == "2.0"

    def test_merged_cards_runtime_data_matches_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        data = json.loads(MERGED_CARDS_PATH.read_text(encoding="utf-8"))
        validator = jsonschema.Draft7Validator(schema)

        errors = [
            f"{card.get('card_id')}:{list(error.path)}:{error.message}"
            for card in data.get("cards", [])
            for error in validator.iter_errors(card)
        ]

        assert errors == []

    def test_merged_cards_merge_sources_are_repo_relative(self):
        data = json.loads(MERGED_CARDS_PATH.read_text(encoding="utf-8"))

        for source in data.get("merge_sources", {}).values():
            assert not Path(source).is_absolute()
            assert not re.match(r"^[A-Za-z]:[\\/]", source)
            assert not source.startswith("/Users/")

    def test_get_best_channel_for_card_exists(self):
        """fubon_b_lifestyle 在 supermarket 有 2% 回饋（8 大生活通路）"""
        card = get_card_by_id("fubon_b_lifestyle")
        best = get_best_channel_for_card(card, "supermarket")
        assert best is not None
        assert best["cashback_rate"] == 0.02
        assert best["is_fallback"] is False

    def test_get_best_channel_for_card_fallback_to_general(self):
        """查詢不存在的通路，應 fallback 到 general"""
        card = get_card_by_id("fubon_c_j")
        best = get_best_channel_for_card(card, "pharmacy")
        assert best is not None
        assert best["is_fallback"] is True
        assert best["cashback_rate"] == 0.01  # fubon_c_j general = 1%

    def test_get_best_channel_for_card_none_when_no_general(self):
        """若連 general 都沒有，回傳 None"""
        # 建一張假卡無 channels
        fake_card = {"card_id": "test", "channels": []}
        assert get_best_channel_for_card(fake_card, "dining") is None

    def test_get_best_deal_for_card_linepay(self):
        """ctbc_c_linepay 在 ecommerce 有 deals（如蝦皮）"""
        card = get_card_by_id("ctbc_c_linepay")
        deals = card.get("deals", [])
        # 確認有 deals 資料
        if deals:
            deal = get_best_deal_for_card(card, "ecommerce")
            assert deal is not None
            assert deal.get("cashback_rate") is not None

    def test_get_best_deal_for_card_no_deals(self):
        """fubon_c_j 沒有 deals 資料"""
        card = get_card_by_id("fubon_c_j")
        assert get_best_deal_for_card(card, "ecommerce") is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. search_by_channel 測試
# ═══════════════════════════════════════════════════════════════════════════

class TestSearchByChannel:
    """Tool 1: search_by_channel"""

    def test_empty_cards_owned_error(self):
        result = search_by_channel("超商", cards_owned=[])
        assert result["error"] is not None
        assert result["results"] == []

    def test_invalid_cards_owned_error(self):
        result = search_by_channel("超商", cards_owned=["invalid_card_id"])
        assert result["error"] is not None

    def test_partial_invalid_cards_owned_error(self):
        result = search_by_channel("超商", cards_owned=["ctbc_c_linepay", "invalid_card_id"])

        assert result["error"] is not None
        assert "invalid_card_id" in result["error"]
        assert result["results"] == []

    def test_basic_convenience_store(self):
        """用 3 張卡查超商"""
        cards = ["ctbc_c_uniopen", "fubon_b_lifestyle", "fubon_c_j"]
        result = search_by_channel("超商", cards_owned=cards, amount=500)

        assert result["error"] is None
        assert result["channel_id"] == "convenience_store"
        assert result["channel_name"] == "超商"
        assert len(result["results"]) >= 1

        # 結果應有 rank
        for r in result["results"]:
            assert "rank" in r
            assert "card_id" in r
            assert "cashback_rate" in r

    def test_top_k_limit(self):
        """top_k=1 應只回傳 1 筆"""
        result = search_by_channel("超商", cards_owned=ALL_CARD_IDS, amount=500, top_k=1)
        assert result["error"] is None
        assert len(result["results"]) == 1

    def test_711_resolves_to_convenience_store(self):
        result = search_by_channel("711", cards_owned=COMBO_3, amount=300)
        assert result["channel_id"] == "convenience_store"

    def test_channel_id_passthrough(self):
        """直接傳入 channel_id 應 passthrough"""
        result = search_by_channel("ecommerce", cards_owned=COMBO_3, amount=1000)
        assert result["channel_id"] == "ecommerce"

    def test_overseas_general(self):
        result = search_by_channel("overseas_general", cards_owned=COMBO_3, amount=5000)
        assert result["channel_id"] == "overseas_general"
        assert result["error"] is None

    def test_amount_zero_no_estimated(self):
        """amount=0 時 estimated_cashback 應為 None"""
        result = search_by_channel("超商", cards_owned=COMBO_3, amount=0)
        assert result["error"] is None
        for r in result["results"]:
            assert r["estimated_cashback"] is None

    def test_merchant_hint_detection(self):
        """查全聯，merchant_hint 應被設定"""
        result = search_by_channel("全聯", cards_owned=COMBO_5, amount=1500)
        assert result["channel_id"] == "supermarket"
        assert result["merchant_hint"] in ("全聯", "")

    def test_ranking_order(self):
        """結果應依 estimated_cashback 降序排列"""
        result = search_by_channel("超商", cards_owned=ALL_CARD_IDS, amount=1000)
        results = result["results"]
        if len(results) >= 2:
            for i in range(len(results) - 1):
                est_a = results[i].get("estimated_cashback") or 0
                est_b = results[i + 1].get("estimated_cashback") or 0
                assert est_a >= est_b, f"排序錯誤: rank {i+1} ({est_a}) < rank {i+2} ({est_b})"

    def test_result_structure(self):
        """驗證結果包含所有必要欄位"""
        result = search_by_channel("餐飲", cards_owned=COMBO_5, amount=1000)
        assert result["error"] is None
        required = {"card_id", "card_name", "cashback_rate", "cashback_type",
                     "estimated_cashback", "rank", "data_source", "calculation_trace"}
        for r in result["results"]:
            missing = required - set(r.keys())
            assert not missing, f"缺少欄位: {missing}"

    def test_calculation_trace_non_cash_points_formula(self):
        result = search_by_channel("家樂福", cards_owned=["ctbc_c_linepay"], amount=2000)
        trace = result["results"][0]["calculation_trace"]

        assert trace["amount"] == 2000
        assert trace["cashback_rate"] == 0.05
        assert trace["formula"] == "非現金回饋不換算 NT$ 預估"
        assert trace["raw_cashback"] == 100
        assert trace["cap"] is None
        assert trace["cap_applied"] is False
        assert trace["final_cashback"] is None

    def test_calculation_trace_with_cap(self):
        trace = _build_calculation_trace(
            amount=10000,
            cashback_rate=0.05,
            cap=300,
            estimated_cashback=300,
        )

        assert trace["formula"] == "min(10000 × 5%, 300) = 300"
        assert trace["raw_cashback"] == 500
        assert trace["cap_applied"] is True
        assert trace["final_cashback"] == 300

    def test_calculation_trace_amount_zero(self):
        trace = _build_calculation_trace(
            amount=0,
            cashback_rate=0.05,
            cap=None,
            estimated_cashback=None,
        )

        assert trace["formula"] == "未計算預估回饋"
        assert trace["raw_cashback"] is None
        assert trace["final_cashback"] is None

    def test_fallback_general(self):
        """查一個沒有卡有資料的通路，應 fallback 到 general"""
        result = search_by_channel("藥妝", cards_owned=["fubon_c_j"], amount=500)
        assert result["error"] is None
        if result["results"]:
            r = result["results"][0]
            assert r["is_fallback"] is True

    def test_compact_search_result_for_tool_result(self):
        result = search_by_channel("家樂福", cards_owned=COMBO_5, amount=2000, top_k=3)
        compact = compact_search_result(result)

        assert compact["result_count"] == len(result["results"])
        assert compact["winner"]["card_name"] == result["results"][0]["card_name"]
        assert len(compact["candidates"]) <= 4
        assert "formula" in compact["candidates"][0]

    def test_tool_result_event_shape(self):
        event = tool_result_event(
            tool="search_by_channel",
            channel="家樂福",
            status="success",
            summary="回傳 3 張候選卡",
            data={"result_count": 3},
        )

        assert event["type"] == "tool_result"
        assert event["tool"] == "search_by_channel"
        assert event["channel"] == "家樂福"
        assert event["status"] == "success"
        assert event["data"]["result_count"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# 4. recommend_payment 測試
# ═══════════════════════════════════════════════════════════════════════════

def test_server_llm_is_disabled_by_default_even_when_api_key_exists(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(llm_parser, "ENABLE_SERVER_LLM", False)

    assert llm_parser.parse_scenario("全聯 1000 元") is None
    assert llm_parser.generate_reasons(
        scenario="全聯 1000 元",
        channel_name="超市／量販",
        amount=1000,
        recommendations=[{"card_id": "ctbc_c_linepay"}],
    ) == {}


class TestRecommendPayment:
    """Tool 2: recommend_payment"""

    @pytest.fixture(autouse=True)
    def disable_llm_calls(self, monkeypatch):
        """recommend_payment tests must stay deterministic and avoid real LLM calls."""
        import mcp_server.tools.recommend as recommend_module

        monkeypatch.setattr(recommend_module, "parse_scenario", lambda _: None)
        monkeypatch.setattr(recommend_module, "generate_reasons", lambda **_: {})

    # ── _extract_amount 子函式 ─────────────────────────────────────

    @pytest.mark.parametrize("text,expected", [
        ("花了 1500 元", 1500.0),
        ("大概花 3000", 3000.0),
        ("NT$2,500 元", 2500.0),
        ("消費500塊", 500.0),
        ("共 10000 元", 10000.0),
        ("沒有金額的文字", 0.0),
        ("一個300一個500", 500.0),  # 取最大值
    ])
    def test_extract_amount(self, text, expected):
        assert _extract_amount(text) == expected

    # ── _extract_channels 子函式 ───────────────────────────────────

    @pytest.mark.parametrize("text,expected_channels", [
        ("去7-11買東西", ["7-ELEVEN"]),
        ("我現在在 7-ELEVEN 結帳", ["7-ELEVEN"]),
        ("日本實體店刷卡", ["overseas_general"]),
        ("去好市多買東西", ["COSTCO"]),
        ("在SOGO百貨消費", ["遠東SOGO"]),
        ("繳保費", ["insurance"]),
        ("台灣大哥大繳電信費", ["台灣大哥大"]),
        ("全聯買菜", ["全聯"]),
        ("蝦皮購物", ["蝦皮"]),
        ("foodpanda外送", ["foodpanda"]),
        ("搭高鐵去台中", ["高鐵"]),
        ("去全聯買菜再叫foodpanda外送", ["全聯", "foodpanda"]),
        ("隨便逛逛", []),  # 無法識別
    ])
    def test_extract_channels(self, text, expected_channels):
        found = _extract_channels(text)
        assert found == expected_channels

    # ── recommend_payment 整合 ─────────────────────────────────────

    def test_empty_cards_owned_error(self):
        result = recommend_payment("去全聯買菜", cards_owned=[])
        assert result["error"] is not None

    def test_empty_scenario_error(self):
        result = recommend_payment("", cards_owned=COMBO_3)
        assert result["error"] is not None

    def test_single_channel_scenario(self):
        result = recommend_payment("去全聯買菜花1500元", cards_owned=COMBO_5)
        assert result["error"] is None
        assert result["parsed"]["amount"] == 1500.0
        assert len(result["parsed"]["channels"]) >= 1
        assert result["parsed"]["channels"][0]["channel_id"] == "supermarket"

    def test_multi_channel_scenario(self):
        result = recommend_payment(
            "去全聯買菜花3000元，晚上叫foodpanda外送500元",
            cards_owned=COMBO_5,
        )
        assert result["error"] is None
        channel_ids = [ch["channel_id"] for ch in result["parsed"]["channels"]]
        assert "supermarket" in channel_ids
        assert "food_delivery" in channel_ids

    def test_off_topic_without_llm_does_not_fallback_to_general(self):
        result = recommend_payment("今天天氣如何？", cards_owned=COMBO_3)
        assert result["error"] is None
        assert result["parsed"]["channels"] == []
        assert result["recommendations"] == []
        assert "信用卡消費建議助理" in result["off_topic_message"]

    def test_ambiguous_non_amount_card_question_is_rejected_by_strict_guard(self):
        result = recommend_payment("我的卡哪張最划算", cards_owned=COMBO_3)
        assert result["error"] is None
        assert result["recommendations"] == []
        assert "信用卡消費建議助理" in result["off_topic_message"]

    def test_general_fallback_requires_amount_and_payment_intent(self):
        result = recommend_payment("刷卡 1000 元哪張划算", cards_owned=COMBO_3)
        assert result["error"] is None
        assert result["parsed"]["amount"] == 1000.0
        assert result["parsed"]["channels"][0]["channel_id"] == "general"
        assert len(result["recommendations"]) >= 1

    def test_merchant_without_amount_is_allowed_by_strict_guard(self):
        result = recommend_payment("今天花了一些錢", cards_owned=COMBO_3)
        assert result["error"] is None
        assert result["recommendations"] == []
        assert "信用卡消費建議助理" in result["off_topic_message"]

        result = recommend_payment("去全聯買菜", cards_owned=COMBO_3)
        assert result["error"] is None
        assert len(result["parsed"]["channels"]) >= 1
        assert result["parsed"]["channels"][0]["channel_id"] == "supermarket"

    def test_momo_amount_is_allowed_by_strict_guard(self):
        result = recommend_payment("momo 3000 元", cards_owned=COMBO_3)
        assert result["error"] is None
        assert result["parsed"]["amount"] == 3000.0
        assert result["parsed"]["channels"][0]["channel_id"] == "ecommerce"

    def test_recommendation_has_best_card(self):
        result = recommend_payment("去711買東西花300元", cards_owned=COMBO_5)
        assert result["error"] is None
        if result["recommendations"]:
            rec = result["recommendations"][0]
            assert "best_options" in rec
            assert len(rec["best_options"]) >= 1
            assert "card_id" in rec["best_options"][0]


# ═══════════════════════════════════════════════════════════════════════════
# 5. compare_cards 測試
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareCards:
    """Tool 3: compare_cards"""

    def test_empty_cards_owned_error(self):
        result = compare_cards(cards_owned=[])
        assert result["error"] is not None

    def test_partial_invalid_cards_owned_error(self):
        result = compare_cards(cards_owned=["ctbc_c_linepay", "invalid_card_id"])

        assert result["error"] is not None
        assert "invalid_card_id" in result["error"]
        assert result["comparison"] == []

    def test_single_channel_comparison(self):
        result = compare_cards(cards_owned=COMBO_3, channel="超商", amount=500)
        assert result["error"] is None
        assert result["channel_filter"] == "convenience_store"
        assert len(result["comparison"]) >= 1

        # 每個通路的 card_rates 數量應等於持有卡數
        for comp in result["comparison"]:
            assert len(comp["card_rates"]) == len(COMBO_3)

    def test_full_comparison(self):
        result = compare_cards(cards_owned=COMBO_3, amount=1000)
        assert result["error"] is None
        assert result["channel_filter"] is None
        assert len(result["comparison"]) >= 1

    def test_best_card_marking(self):
        """至少有一張卡被標記為 is_best"""
        result = compare_cards(cards_owned=COMBO_5, channel="超商", amount=1000)
        assert result["error"] is None
        for comp in result["comparison"]:
            best_count = sum(1 for r in comp["card_rates"] if r["is_best"])
            assert best_count >= 1, f"通路 {comp['channel_id']} 無 is_best 標記"

    def test_summary_generation(self):
        result = compare_cards(cards_owned=COMBO_3, amount=1000)
        assert result["error"] is None
        assert len(result["summary"]) == len(COMBO_3)
        for s in result["summary"]:
            assert "card_id" in s
            assert "best_channels" in s

    def test_cards_list_in_result(self):
        result = compare_cards(cards_owned=COMBO_3)
        assert len(result["cards"]) == len(COMBO_3)

    def test_comparison_structure(self):
        """驗證 comparison 每筆的必要欄位"""
        result = compare_cards(cards_owned=COMBO_3, channel="餐飲", amount=1000)
        assert result["error"] is None
        for comp in result["comparison"]:
            assert "channel_id" in comp
            assert "channel_name" in comp
            assert "card_rates" in comp
            for rate in comp["card_rates"]:
                assert "card_id" in rate
                assert "cashback_rate" in rate
                assert "is_best" in rate

    def test_compare_uses_same_non_cash_estimation_as_search(self):
        search = search_by_channel("家樂福", cards_owned=["ctbc_c_linepay"], amount=2000)
        comparison = compare_cards(cards_owned=["ctbc_c_linepay"], channel="家樂福", amount=2000)

        search_option = search["results"][0]
        compare_option = comparison["comparison"][0]["card_rates"][0]

        assert search_option["cashback_type"] == "points"
        assert search_option["estimated_cashback"] is None
        assert compare_option["cashback_type"] == "points"
        assert compare_option["estimated_cashback"] is None
        assert compare_option["cashback_rate"] == search_option["cashback_rate"]


# ═══════════════════════════════════════════════════════════════════════════
# 6. get_promotions / get_card_details 測試
# ═══════════════════════════════════════════════════════════════════════════

class TestPromotionsAndDetails:
    """Tool 4 & 5: get_promotions, get_card_details"""

    def test_get_promotions_basic(self):
        result = get_promotions(cards_owned=COMBO_3)
        assert result["error"] is None
        assert "promotions" in result

    def test_get_promotions_empty_cards(self):
        result = get_promotions(cards_owned=[])
        assert result["error"] is not None

    def test_get_promotions_invalid_cards_owned_error(self):
        result = get_promotions(cards_owned=["invalid_card_id"])

        assert result["error"] is not None
        assert "invalid_card_id" in result["error"]

    def test_get_card_details_valid(self):
        """get_card_details 回傳扁平結構（card 欄位直接在頂層）"""
        result = get_card_details(card_id="fubon_c_j")
        assert result["error"] is None
        assert result["card_id"] == "fubon_c_j"
        assert result["card_name"] == "富邦J卡"
        assert "channels" in result

    def test_get_card_details_invalid(self):
        result = get_card_details(card_id="nonexistent")
        assert result["error"] is not None

    def test_get_card_details_has_channels(self):
        result = get_card_details(card_id="fubon_b_lifestyle")
        channels = result["channels"]
        assert len(channels) >= 1
        # fubon_b_lifestyle 8 大生活通路：百貨、量販、超市、餐飲、加油、旅遊
        channel_ids = {ch["channel_id"] for ch in channels}
        assert "supermarket" in channel_ids
        assert "dining" in channel_ids


# ═══════════════════════════════════════════════════════════════════════════
# 7. 準確度測試（具體回饋率驗證）
# ═══════════════════════════════════════════════════════════════════════════

class TestAccuracy:
    """
    驗證系統查詢回饋率與預期值一致。
    預期值基於 merged_cards.json 中的實際資料。
    """

    def test_fubon_lifestyle_supermarket_2pct(self):
        """富邦富利生活卡在超市應有 2% 回饋"""
        result = search_by_channel("超市", cards_owned=["fubon_b_lifestyle"], amount=1000)
        assert result["error"] is None
        assert len(result["results"]) == 1
        r = result["results"][0]
        assert r["card_id"] == "fubon_b_lifestyle"
        assert r["cashback_rate"] == 0.02
        assert r["estimated_cashback"] == 20.0

    def test_fubon_costco_ecommerce_3pct(self):
        """富邦Costco卡在電商應有 3% 回饋"""
        result = search_by_channel("電商", cards_owned=["fubon_c_costco"], amount=2000)
        assert result["error"] is None
        assert len(result["results"]) == 1
        r = result["results"][0]
        assert r["cashback_rate"] == 0.03
        assert r["estimated_cashback"] == 60.0

    def test_fubon_j_overseas_6pct(self):
        """富邦J卡海外消費 Q4 加碼活動有效期內，應有 6%（基本 3% + 加碼 3%）"""
        result = search_by_channel("overseas_general", cards_owned=["fubon_c_j"], amount=10000)
        assert result["error"] is None
        assert len(result["results"]) == 1
        r = result["results"][0]
        assert r["cashback_rate"] == 0.06
        assert r["is_fallback"] is False
        assert r["estimated_cashback"] == 600.0

    def test_fubon_momo_ecommerce_7pct(self):
        """富邦momo卡在 momo 購物網應有 7% mo 幣回饋"""
        result = search_by_channel("電商", cards_owned=["fubon_c_momo"], amount=3000)
        assert result["error"] is None
        r = result["results"][0]
        assert r["cashback_rate"] == 0.07
        assert r["estimated_cashback"] == 210.0

    def test_ranking_ecommerce_momo_vs_costco(self):
        """電商比較：momo 7% 應排在 costco 3% 前面"""
        result = search_by_channel(
            "電商", cards_owned=["fubon_c_momo", "fubon_c_costco"], amount=1000,
        )
        assert result["error"] is None
        rates = [r["cashback_rate"] for r in result["results"]]
        assert rates[0] == 0.07
        assert rates[1] == 0.03

    def test_compare_dining_hanshin_best(self):
        """餐飲比較：漢神 10% vs 遠東SOGO 20% vs 富利生活 2%"""
        result = compare_cards(
            cards_owned=["ctbc_c_hanshin", "ctbc_c_cs", "fubon_b_lifestyle"],
            channel="餐飲",
            amount=1000,
        )
        assert result["error"] is None
        assert len(result["comparison"]) >= 1
        dining = result["comparison"][0]
        # 找到 is_best 的卡
        best = [r for r in dining["card_rates"] if r["is_best"]]
        assert len(best) >= 1
        # 遠東SOGO 有最高的餐飲回饋率（20%）
        assert best[0]["card_id"] == "ctbc_c_cs"

    def test_estimated_cashback_with_cap(self):
        """有回饋上限的卡，預估金額應被上限截斷"""
        # 使用 calc 直接測試
        assert calc_estimated_cashback(10000, 0.05, 200) == 200.0
        assert calc_estimated_cashback(1000, 0.05, 200) == 50.0

    def test_711_does_not_use_unrelated_general_marketing_fallback(self):
        """7-ELEVEN 查詢不可拿非超商活動的一般通路行銷文案計算回饋。"""
        result = search_by_channel("7-ELEVEN", cards_owned=ALL_CARD_IDS, amount=350, top_k=8)
        assert result["error"] is None
        assert len(result["results"]) >= 3

        descriptions = [r["cashback_description"] for r in result["results"]]
        assert not any("大巨蛋秀泰" in desc for desc in descriptions)
        assert not any("最高享16%回饋" in desc for desc in descriptions)

    def test_openpoint_reward_is_not_reported_as_cash_estimate(self):
        """OPENPOINT 回饋不能被直接顯示成 NT$ 現金預估。"""
        result = search_by_channel("7-ELEVEN", cards_owned=["ctbc_c_uniopen"], amount=350)
        assert result["error"] is None
        assert len(result["results"]) == 1

        option = result["results"][0]
        assert option["cashback_type"] == "points"
        assert option["estimated_cashback"] is None
        assert option["calculation_trace"]["formula"] == "非現金回饋不換算 NT$ 預估"

    def test_general_fallback_excludes_specific_highest_reward_campaigns(self):
        """無專屬通路時，只能 fallback 到明確一般消費，不可拿指定活動最高回饋。"""
        result = search_by_channel(
            "藥妝",
            cards_owned=["ctbc_c_linepay", "ctbc_c_cs"],
            amount=350,
            top_k=5,
        )
        assert result["error"] is None

        descriptions = [r["cashback_description"] for r in result["results"]]
        assert not any("最高享16%回饋" in desc for desc in descriptions)
        assert not any("大巨蛋秀泰" in desc for desc in descriptions)

    def test_general_query_excludes_specific_highest_reward_campaigns(self):
        """直接查一般消費時，也不可拿指定活動最高回饋當一般消費。"""
        result = search_by_channel("一般消費", cards_owned=ALL_CARD_IDS, amount=350, top_k=8)
        assert result["error"] is None

        descriptions = [r["cashback_description"] for r in result["results"]]
        assert not any("最高享16%回饋" in desc for desc in descriptions)
        assert not any("大巨蛋秀泰" in desc for desc in descriptions)

    def test_specific_transport_merchant_excludes_unrelated_transit_offer(self):
        """高鐵查詢不可拿日本交通儲值優惠排序。"""
        result = search_by_channel("高鐵", cards_owned=ALL_CARD_IDS, amount=1500, top_k=5)
        assert result["error"] is None
        assert result["results"][0]["card_id"] in {"fubon_c_costco", "fubon_c_momo"}

        descriptions = [r["cashback_description"] for r in result["results"]]
        assert not any("Suica" in desc or "PASMO" in desc or "ICOCA" in desc for desc in descriptions)

    def test_specific_mobile_payment_excludes_other_payment_tools(self):
        """LINE Pay 查詢不可拿 icash Pay 或 AI 工具訂閱優惠排序。"""
        result = search_by_channel("LINE Pay", cards_owned=ALL_CARD_IDS, amount=500, top_k=5)
        assert result["error"] is None

        descriptions = [r["cashback_description"] for r in result["results"]]
        assert not any("icash Pay" in desc for desc in descriptions)
        assert not any("AI 工具" in desc for desc in descriptions)

    def test_specific_dining_merchant_excludes_department_store_dining(self):
        """麥當勞查詢不可拿百貨館內餐飲優惠排序。"""
        result = search_by_channel("麥當勞", cards_owned=ALL_CARD_IDS, amount=300, top_k=5)
        assert result["error"] is None

        descriptions = [r["cashback_description"] for r in result["results"]]
        assert not any("SOGO" in desc or "館內" in desc or "店內餐飲" in desc for desc in descriptions)


# ═══════════════════════════════════════════════════════════════════════════
# 8. 邊界條件與錯誤處理測試
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """邊界條件、錯誤處理"""

    def test_search_all_13_cards(self):
        """全部 13 張卡查詢不應 crash"""
        result = search_by_channel("一般消費", cards_owned=ALL_CARD_IDS, amount=1000, top_k=13)
        assert result["error"] is None

    def test_search_unknown_channel(self):
        """未知通路應 fallback 到 general"""
        result = search_by_channel("火星購物", cards_owned=COMBO_3, amount=100)
        assert result["error"] is None
        assert result["channel_id"] == "general"

    def test_compare_single_card(self):
        """只有一張卡的比較不應 crash"""
        result = compare_cards(cards_owned=["fubon_c_j"], amount=1000)
        assert result["error"] is None
        assert len(result["cards"]) == 1

    def test_recommend_long_scenario(self):
        """長文情境描述不應 crash"""
        long_text = "我今天去了全聯買了很多東西，" * 20 + "大概花了3000元"
        result = recommend_payment(long_text, cards_owned=COMBO_3)
        assert result["error"] is None

    def test_search_special_characters(self):
        """特殊字元不應 crash"""
        result = search_by_channel("7-11!!!", cards_owned=COMBO_3, amount=100)
        assert result["error"] is None

    def test_recommend_whitespace_only(self):
        """純空白情境應回傳錯誤"""
        result = recommend_payment("   ", cards_owned=COMBO_3)
        assert result["error"] is not None

    def test_large_amount(self):
        """大金額不應 crash"""
        result = search_by_channel("電商", cards_owned=COMBO_3, amount=999999)
        assert result["error"] is None

    def test_negative_amount_treated_as_zero(self):
        """負數金額不應計算回饋"""
        result = search_by_channel("電商", cards_owned=COMBO_3, amount=-100)
        assert result["error"] is None
        for r in result["results"]:
            assert r["estimated_cashback"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 9. 通路映射完整性測試
# ═══════════════════════════════════════════════════════════════════════════

class TestChannelMapping:
    """驗證常見使用者輸入能正確映射到 channel_id"""

    def test_all_17_channel_ids_are_valid_search_inputs(self):
        expected = {
            "convenience_store", "supermarket", "wholesale", "ecommerce",
            "food_delivery", "transport", "dining", "travel", "entertainment",
            "gas_station", "pharmacy", "mobile_payment", "department_store",
            "insurance", "telecom", "general", "overseas_general",
        }

        for channel_id in expected:
            result = search_by_channel(channel_id, cards_owned=["fubon_c_costco"], amount=100)
            assert result["channel_id"] == channel_id

    def test_llm_parser_accepts_all_17_channel_ids(self):
        assert set(LLM_VALID_CHANNEL_IDS) == {
            "convenience_store", "supermarket", "wholesale", "ecommerce",
            "food_delivery", "transport", "dining", "travel", "entertainment",
            "gas_station", "pharmacy", "mobile_payment", "department_store",
            "insurance", "telecom", "general", "overseas_general",
        }

    @pytest.mark.parametrize("input_text,expected_cid", [
        ("711", "convenience_store"),
        ("7-11", "convenience_store"),
        ("全家", "convenience_store"),
        ("全聯", "supermarket"),
        ("家樂福", "supermarket"),
        ("好市多", "wholesale"),
        ("COSTCO", "wholesale"),
        ("蝦皮", "ecommerce"),
        ("momo", "ecommerce"),
        ("foodpanda", "food_delivery"),
        ("Uber Eats", "food_delivery"),
        ("高鐵", "transport"),
        ("捷運", "transport"),
        ("麥當勞", "dining"),
        ("星巴克", "dining"),
        ("加油", "gas_station"),
        ("屈臣氏", "pharmacy"),
        ("百貨", "department_store"),
        ("SOGO", "department_store"),
        ("保費", "insurance"),
        ("保險費", "insurance"),
        ("電信費", "telecom"),
        ("台灣大哥大", "telecom"),
        ("overseas_general", "overseas_general"),
        ("convenience_store", "convenience_store"),
    ])
    def test_channel_resolution(self, input_text, expected_cid):
        result = search_by_channel(input_text, cards_owned=["fubon_c_j"], amount=100)
        assert result["channel_id"] == expected_cid, \
            f"'{input_text}' 應映射到 '{expected_cid}'，實際得到 '{result['channel_id']}'"

    @pytest.mark.parametrize("input_text,expected_cid", [
        ("wholesale", "wholesale"),
        ("department_store", "department_store"),
        ("insurance", "insurance"),
        ("telecom", "telecom"),
    ])
    def test_compare_cards_accepts_extended_channel_ids(self, input_text, expected_cid):
        result = compare_cards(cards_owned=["fubon_c_costco"], channel=input_text, amount=100)
        assert result["error"] is None
        assert result["channel_filter"] == expected_cid


class TestMcpToolRegistry:
    """Public MCP tools should not expose maintenance-only operations."""

    def test_reload_data_is_not_public_tool(self):
        import mcp_server.server as server_module

        assert not hasattr(server_module, "reload_data")
