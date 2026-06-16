"""
search.py
---------
Tool 1：search_by_channel
依通路搜尋使用者持有的卡中回饋最高的選擇。

資料來源：merged_cards.json（已在 build time 合併三層資料）
- channels：card_features 優先覆蓋 API，直接查 get_best_channel_for_card
- deals：microsite 商家促銷，查 get_best_deal_for_card
"""

from __future__ import annotations

from ..utils.data_loader import validate_card_ids

from ..utils.channel_mapper import get_channel_id, normalize_merchant
from .rewards import (
    build_calculation_trace as _build_calculation_trace,
    evaluate_card_reward,
    reward_sort_key,
)


def search_by_channel(
    channel: str,
    cards_owned: list[str],
    amount: float = 0,
    top_k: int = 3,
) -> dict:
    """
    從使用者持有的信用卡中，找出在指定通路回饋最高的卡片。

    查詢流程（每張卡）：
    1. 先查 deals（microsite 商家促銷）— 最精確
    2. 再查 channels（已合併 card_features + API）— 通路層級

    Args:
        channel:     通路名稱，支援模糊輸入（如 "711"、"超商"、"全聯"）
        cards_owned: 使用者持有的卡 card_id 列表（必填）
        amount:      消費金額（新台幣），用於計算預估回饋（0 = 不計算）
        top_k:       回傳前幾名（預設 3）

    Returns:
        {
          "channel_id": "convenience_store",
          "channel_name": "超商",
          "query": "711",
          "amount": 500,
          "results": [ ... ],
          "error": null
        }
    """
    # 驗證持卡清單
    if not cards_owned:
        return _error("請先選擇您持有的信用卡（cards_owned 不可為空）")

    # 正規化通路 → channel_id
    channel_id = _resolve_channel(channel)
    channel_display = _channel_display_name(channel_id, channel)

    # 載入並驗證持有卡
    owned_cards, validation_error = validate_card_ids(cards_owned)
    if validation_error:
        return _error(validation_error)

    # 若輸入是已知商家，保留商家名稱作為 hint（供 deals 商家層級比對）
    normalized = normalize_merchant(channel)
    from ..utils.channel_mapper import MERCHANT_TO_CHANNEL
    merchant_hint = normalized if normalized in MERCHANT_TO_CHANNEL else None

    # 對每張持有卡查最優回饋
    results = []
    for card in owned_cards:
        reward = evaluate_card_reward(card, channel_id, amount, merchant_hint=merchant_hint)
        if reward is not None:
            results.append(reward)

    # 排序：預估回饋↓ → 回饋率↓
    results.sort(key=reward_sort_key, reverse=True)
    results = results[:top_k]

    # 加 rank
    for i, r in enumerate(results, 1):
        r["rank"] = i

    return {
        "channel_id":    channel_id,
        "channel_name":  channel_display,
        "query":         channel,
        "amount":        amount,
        "merchant_hint": merchant_hint or "",
        "results":       results,
        "error":         None,
    }


# ── 內部工具 ──────────────────────────────────────────────────────────────────

_VALID_CHANNEL_IDS = {
    "convenience_store", "supermarket", "wholesale", "ecommerce",
    "food_delivery", "transport", "dining", "travel", "entertainment",
    "gas_station", "pharmacy", "mobile_payment", "department_store",
    "insurance", "telecom", "general", "overseas_general",
}


def _resolve_channel(raw: str) -> str:
    """
    把使用者輸入的通路文字映射到 channel_id。
    若輸入本身就是合法 channel_id，直接回傳（避免部分比對誤判）。
    再試 normalize_merchant，再試 category keyword，fallback 到 general。
    """
    if raw in _VALID_CHANNEL_IDS:
        return raw
    cid = get_channel_id(raw)
    return cid if cid else "general"


_CHANNEL_NAMES = {
    "convenience_store": "超商",
    "supermarket":       "超市／量販",
    "wholesale":         "量販倉儲",
    "ecommerce":         "電商",
    "food_delivery":     "外送",
    "transport":         "交通",
    "dining":            "餐飲",
    "travel":            "旅遊",
    "entertainment":     "娛樂",
    "gas_station":       "加油站",
    "pharmacy":          "藥妝",
    "mobile_payment":    "行動支付",
    "department_store":  "百貨公司",
    "insurance":         "保費",
    "telecom":           "電信費",
    "general":           "一般消費",
    "overseas_general":  "海外消費",
}


def _channel_display_name(channel_id: str, fallback: str) -> str:
    return _CHANNEL_NAMES.get(channel_id, fallback)


def _error(msg: str) -> dict:
    return {
        "channel_id":   None,
        "channel_name": None,
        "query":        None,
        "amount":       0,
        "results":      [],
        "error":        msg,
    }
