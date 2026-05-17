"""Utilities for building compact MCP tool execution traces for the frontend."""

from __future__ import annotations


def compact_search_result(result: dict, limit: int = 4) -> dict:
    """Build a compact, display-safe view of search_by_channel output."""
    candidates = []
    for item in result.get("results", [])[:limit]:
        trace = item.get("calculation_trace") or {}
        candidates.append({
            "rank": item.get("rank"),
            "card_id": item.get("card_id"),
            "card_name": item.get("card_name"),
            "cashback_rate": item.get("cashback_rate"),
            "estimated_cashback": item.get("estimated_cashback"),
            "cashback_type": item.get("cashback_type"),
            "cashback_description": item.get("cashback_description"),
            "conditions": item.get("conditions"),
            "data_source": item.get("data_source"),
            "is_fallback": item.get("is_fallback", False),
            "formula": trace.get("formula"),
        })

    return {
        "channel_id": result.get("channel_id"),
        "channel_name": result.get("channel_name"),
        "query": result.get("query"),
        "amount": result.get("amount"),
        "merchant_hint": result.get("merchant_hint"),
        "result_count": len(result.get("results", [])),
        "winner": candidates[0] if candidates else None,
        "candidates": candidates,
        "error": result.get("error"),
    }


def compact_card_details(details_by_card: dict[str, dict]) -> dict:
    """Build a compact view of get_card_details results for the UI trace."""
    cards = []
    for card_id, detail in details_by_card.items():
        channels = []
        for channel in detail.get("channels", [])[:3]:
            channels.append({
                "channel_id": channel.get("channel_id"),
                "channel_name": channel.get("channel_name"),
                "cashback_rate": channel.get("cashback_rate"),
                "cashback_description": channel.get("cashback_description"),
                "conditions": channel.get("conditions"),
                "valid_end": channel.get("valid_end"),
                "data_source": channel.get("data_source"),
            })

        cards.append({
            "card_id": card_id,
            "card_name": detail.get("card_name"),
            "data_source": detail.get("data_source"),
            "tags": detail.get("tags", [])[:5],
            "channel_count": len(detail.get("channels", [])),
            "deal_count": len(detail.get("deals", [])),
            "channels": channels,
            "error": detail.get("error"),
        })

    return {
        "card_count": len(cards),
        "cards": cards,
    }


def compact_promotions(promotions_by_channel: dict[str, dict]) -> dict:
    """Build a compact view of get_promotions results for the UI trace."""
    channels = []
    for channel_id, result in promotions_by_channel.items():
        promotions = []
        for promo in result.get("promotions", [])[:3]:
            promotions.append({
                "title": promo.get("title"),
                "card_name": promo.get("card_name"),
                "category": promo.get("category"),
                "valid_start": promo.get("valid_start"),
                "valid_end": promo.get("valid_end"),
                "conditions": promo.get("conditions"),
            })

        expiring_channels = []
        for item in result.get("card_channels", [])[:3]:
            for channel in item.get("channels", [])[:1]:
                expiring_channels.append({
                    "card_name": item.get("card_name"),
                    "channel_name": channel.get("channel_name"),
                    "valid_end": channel.get("valid_end"),
                    "cashback_description": channel.get("cashback_description"),
                })

        channels.append({
            "channel_id": channel_id,
            "total": result.get("total", 0),
            "promotions": promotions,
            "expiring_channels": expiring_channels,
            "error": result.get("error"),
        })

    return {
        "channel_count": len(channels),
        "total_promotions": sum(item.get("total", 0) or 0 for item in promotions_by_channel.values()),
        "channels": channels,
    }


def tool_result_event(
    tool: str,
    status: str,
    summary: str,
    data: dict,
    channel=None,
) -> dict:
    return {
        "type": "tool_result",
        "tool": tool,
        "channel": channel,
        "status": status,
        "summary": summary,
        "data": data,
    }
