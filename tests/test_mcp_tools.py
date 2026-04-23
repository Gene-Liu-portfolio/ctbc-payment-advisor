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

import sys
from pathlib import Path

import pytest

# 確保 project root 在 sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── 被測模組 ───────────────────────────────────────────────────────────────
from mcp_server.tools.search import search_by_channel
from mcp_server.tools.recommend import recommend_payment, _extract_amount, _extract_channels
from mcp_server.tools.compare import compare_cards
from mcp_server.tools.promotions import get_promotions, get_card_details
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
    "fubon_c_j", "fubon_c_j_travel", "fubon_c_costco",
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

    def test_get_data_summary(self):
        summary = get_data_summary()
        assert summary["card_count"] == 13
        assert summary["version"] == "2.0"

    def test_get_best_channel_for_card_exists(self):
        """fubon_b_lifestyle 在 convenience_store 有 2% 回饋"""
        card = get_card_by_id("fubon_b_lifestyle")
        best = get_best_channel_for_card(card, "convenience_store")
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
                     "estimated_cashback", "rank", "data_source"}
        for r in result["results"]:
            missing = required - set(r.keys())
            assert not missing, f"缺少欄位: {missing}"

    def test_fallback_general(self):
        """查一個沒有卡有資料的通路，應 fallback 到 general"""
        result = search_by_channel("藥妝", cards_owned=["fubon_c_j"], amount=500)
        assert result["error"] is None
        if result["results"]:
            r = result["results"][0]
            assert r["is_fallback"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 4. recommend_payment 測試
# ═══════════════════════════════════════════════════════════════════════════

class TestRecommendPayment:
    """Tool 2: recommend_payment"""

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

    def test_fallback_to_general(self):
        """無法識別通路時 fallback 到一般消費"""
        result = recommend_payment("今天花了一些錢", cards_owned=COMBO_3)
        assert result["error"] is None
        assert len(result["parsed"]["channels"]) >= 1

    def test_recommendation_has_best_card(self):
        result = recommend_payment("去711買東西花300元", cards_owned=COMBO_5)
        assert result["error"] is None
        if result["recommendations"]:
            rec = result["recommendations"][0]
            assert "best_card" in rec
            assert "card_id" in rec["best_card"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. compare_cards 測試
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareCards:
    """Tool 3: compare_cards"""

    def test_empty_cards_owned_error(self):
        result = compare_cards(cards_owned=[])
        assert result["error"] is not None

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
        # fubon_b_lifestyle 應有 supermarket, convenience_store, dining, general
        channel_ids = {ch["channel_id"] for ch in channels}
        assert "supermarket" in channel_ids
        assert "convenience_store" in channel_ids


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

    def test_fubon_j_overseas_fallback(self):
        """富邦J卡 Q1 海外活動已到期（2026-03-31），應 fallback 到 general 1%"""
        result = search_by_channel("overseas_general", cards_owned=["fubon_c_j"], amount=10000)
        assert result["error"] is None
        assert len(result["results"]) == 1
        r = result["results"][0]
        # 6% 活動已到期被過濾，fallback 到 general 1%
        assert r["cashback_rate"] == 0.01
        assert r["is_fallback"] is True

    def test_fubon_momo_ecommerce_3pct(self):
        """富邦momo卡在電商應有 3% 回饋"""
        result = search_by_channel("電商", cards_owned=["fubon_c_momo"], amount=3000)
        assert result["error"] is None
        r = result["results"][0]
        assert r["cashback_rate"] == 0.03
        assert r["estimated_cashback"] == 90.0

    def test_fubon_j_travel_travel_6pct(self):
        """富邦J Travel卡在旅遊應有 6% 回饋"""
        result = search_by_channel("旅遊", cards_owned=["fubon_c_j_travel"], amount=20000)
        assert result["error"] is None
        r = result["results"][0]
        assert r["cashback_rate"] == 0.06
        assert r["estimated_cashback"] == 1200.0

    def test_ranking_ecommerce_momo_vs_costco(self):
        """電商比較：momo 和 costco 都是 3%，應並列"""
        result = search_by_channel(
            "電商", cards_owned=["fubon_c_momo", "fubon_c_costco"], amount=1000,
        )
        assert result["error"] is None
        rates = [r["cashback_rate"] for r in result["results"]]
        assert rates[0] == 0.03
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

    @pytest.mark.parametrize("input_text,expected_cid", [
        ("711", "convenience_store"),
        ("7-11", "convenience_store"),
        ("全家", "convenience_store"),
        ("全聯", "supermarket"),
        ("家樂福", "supermarket"),
        ("好市多", "supermarket"),  # channel_mapper 將 COSTCO 映射到 supermarket
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
        ("overseas_general", "overseas_general"),
        ("convenience_store", "convenience_store"),
    ])
    def test_channel_resolution(self, input_text, expected_cid):
        result = search_by_channel(input_text, cards_owned=["fubon_c_j"], amount=100)
        assert result["channel_id"] == expected_cid, \
            f"'{input_text}' 應映射到 '{expected_cid}'，實際得到 '{result['channel_id']}'"
