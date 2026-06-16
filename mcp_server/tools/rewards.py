"""Shared reward evaluation for payment recommendation tools."""

from __future__ import annotations

from ..utils.calculator import calc_estimated_cashback, is_expiring_soon
from ..utils.data_loader import get_best_channel_for_card, get_best_deal_for_card


def evaluate_card_reward(
    card: dict,
    channel_id: str,
    amount: float = 0,
    merchant_hint: str | None = None,
) -> dict | None:
    """Return the best reward option for one card on one channel."""
    deal = get_best_deal_for_card(card, channel_id, merchant_hint=merchant_hint)
    if deal:
        rate = deal.get("cashback_rate")
        cap = None
        cashback_type = normalize_cashback_type(
            deal.get("cashback_type"),
            deal.get("benefit", ""),
        )
        estimated = estimated_cash_value(amount, rate, cap, cashback_type)
        return {
            "card_id": card["card_id"],
            "card_name": card["card_name"],
            "cashback_rate": rate,
            "cashback_type": cashback_type,
            "cashback_description": deal.get("benefit", ""),
            "estimated_cashback": estimated,
            "max_cashback_per_period": cap,
            "valid_end": deal.get("valid_end"),
            "expiring_soon": is_expiring_soon(deal.get("valid_end")),
            "conditions": deal.get("conditions", ""),
            "merchant": deal.get("merchant", ""),
            "payment_method": deal.get("payment_method", ""),
            "data_source": "microsite",
            "is_fallback": False,
            "calculation_trace": build_calculation_trace(amount, rate, cap, estimated, cashback_type),
        }

    best_channel = get_best_channel_for_card(card, channel_id, merchant_hint=merchant_hint)
    if best_channel is None:
        return None

    rate = best_channel.get("cashback_rate")
    cap = best_channel.get("max_cashback_per_period")
    cashback_type = normalize_cashback_type(
        best_channel.get("cashback_type", "cash"),
        best_channel.get("cashback_description", ""),
    )
    estimated = estimated_cash_value(amount, rate, cap, cashback_type)

    return {
        "card_id": card["card_id"],
        "card_name": card["card_name"],
        "cashback_rate": rate,
        "cashback_type": cashback_type,
        "cashback_description": best_channel.get("cashback_description", ""),
        "estimated_cashback": estimated,
        "max_cashback_per_period": cap,
        "valid_end": best_channel.get("valid_end"),
        "expiring_soon": is_expiring_soon(best_channel.get("valid_end")),
        "conditions": best_channel.get("conditions", ""),
        "data_source": best_channel.get("data_source", "api"),
        "is_fallback": best_channel.get("is_fallback", False),
        "calculation_trace": build_calculation_trace(amount, rate, cap, estimated, cashback_type),
    }


def reward_sort_key(result: dict) -> tuple[float, float]:
    """Sort by estimated cash value, then reward rate."""
    estimated = result.get("estimated_cashback") or 0.0
    rate = result.get("cashback_rate") or 0.0
    return (estimated, rate)


def normalize_cashback_type(raw_type: str | None, description: str) -> str:
    text = f"{raw_type or ''} {description or ''}".lower()
    if "等效" in text:
        return "cash"
    point_keywords = (
        "openpoint", "open point", "line points", "line point",
        "sogo金", "點數", "紅利",
    )
    if any(keyword.lower() in text for keyword in point_keywords):
        return "points"
    if "哩程" in text or "里程" in text or "mile" in text:
        return "miles"
    return raw_type or "cash"


def estimated_cash_value(
    amount: float,
    cashback_rate: float | None,
    cap: int | float | None,
    cashback_type: str,
) -> float | None:
    if amount <= 0:
        return None
    if cashback_type != "cash":
        return None
    return calc_estimated_cashback(amount, cashback_rate, cap)


def build_calculation_trace(
    amount: float,
    cashback_rate: float | None,
    cap: int | float | None,
    estimated_cashback: float | None,
    cashback_type: str = "cash",
) -> dict:
    raw_cashback = None
    cap_applied = False
    formula = "未計算預估回饋"

    if amount > 0 and cashback_rate and cashback_rate > 0 and cashback_type != "cash":
        raw_cashback = round(amount * cashback_rate, 1)
        formula = "非現金回饋不換算 NT$ 預估"
    elif amount > 0 and cashback_rate and cashback_rate > 0:
        raw_cashback = round(amount * cashback_rate, 1)
        amount_text = _format_amount(amount)
        rate_text = _format_rate(cashback_rate)
        if cap is not None:
            cap_value = float(cap)
            cap_applied = raw_cashback > cap_value
            formula = f"min({amount_text} × {rate_text}, {cap_value:g}) = {_format_amount(estimated_cashback)}"
        else:
            formula = f"{amount_text} × {rate_text} = {_format_amount(estimated_cashback)}"

    return {
        "amount": amount,
        "cashback_rate": cashback_rate,
        "cashback_type": cashback_type,
        "formula": formula,
        "raw_cashback": raw_cashback,
        "cap": cap,
        "cap_applied": cap_applied,
        "final_cashback": estimated_cashback,
    }


def _format_amount(value: float | int | None) -> str:
    if value is None:
        return "0"
    numeric = float(value)
    return f"{numeric:g}"


def _format_rate(rate: float | None) -> str:
    if rate is None:
        return "N/A"
    return f"{rate * 100:g}%"
