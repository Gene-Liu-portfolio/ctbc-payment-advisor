"""
llm_parser.py
-------------
使用 Claude API 解析自然語言消費情境，並為推薦結果產生中文說明。

兩個對外函式：
- parse_scenario(text)        → 抽取通路、金額、海外/國內
- generate_reasons(scenario, recommendations) → 為 top-K 卡片產生推薦理由
"""

from __future__ import annotations

import json
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# ── 模型設定 ──────────────────────────────────────────────────────────────────
PARSER_MODEL = os.getenv("CLAUDE_PARSER_MODEL", "claude-haiku-4-5-20251001")
REASONER_MODEL = os.getenv("CLAUDE_REASONER_MODEL", "claude-haiku-4-5-20251001")

# 合法 channel_id（與 search.py:_VALID_CHANNEL_IDS 同步）
_VALID_CHANNEL_IDS = [
    "convenience_store", "supermarket", "ecommerce", "food_delivery",
    "transport", "dining", "travel", "entertainment", "gas_station",
    "pharmacy", "mobile_payment", "general", "overseas_general",
]


def _client():
    """延遲建立 Anthropic client；無 API key 時回傳 None 觸發 fallback。"""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import Anthropic
        return Anthropic()
    except Exception:
        return None


# ── 解析消費情境 ─────────────────────────────────────────────────────────────

_PARSE_TOOL = {
    "name": "extract_consumption_intent",
    "description": (
        "判斷使用者輸入是否為消費／刷卡相關問題；若是，抽取結構化資訊（通路、金額、海外與否）。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "is_consumption_scenario": {
                "type": "boolean",
                "description": (
                    "true = 使用者明確在問刷卡 / 消費通路 / 信用卡推薦相關問題；"
                    "false = 與信用卡無關（閒聊、天氣、新聞、技術問題、純粹寒暄等）。"
                ),
            },
            "off_topic_message": {
                "type": "string",
                "description": (
                    "當 is_consumption_scenario=false 時填一段 30-60 字、繁體中文、"
                    "禮貌且帶引導範例的拒答訊息（如：我是信用卡助理，請問你想查哪個通路？範例：去全聯花 500）。"
                    "is_consumption_scenario=true 時填空字串。"
                ),
            },
            "channels": {
                "type": "array",
                "description": (
                    "辨識到的消費通路，可有多個。每個通路必須含 channel_id 與來源描述。"
                    "若 is_consumption_scenario=false，留空陣列。"
                    "若使用者描述明確提到海外、國外、境外、在某外國地點刷卡，channel_id 應為 'overseas_general'。"
                    "若是消費問題但無明確通路，channel_id 為 'general'。"
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "enum": _VALID_CHANNEL_IDS,
                        },
                        "merchant_or_keyword": {
                            "type": "string",
                            "description": "從敘述中擷取的商家名稱或通路關鍵字（如 '7-ELEVEN'、'momo'、'日本刷卡'）",
                        },
                    },
                    "required": ["channel_id", "merchant_or_keyword"],
                },
            },
            "amount": {
                "type": "number",
                "description": "消費金額（新台幣），無法解析或未提及則填 0",
            },
        },
        "required": ["is_consumption_scenario", "off_topic_message", "channels", "amount"],
    },
}

_PARSER_SYSTEM = """你是中文消費情境解析器。先判斷使用者輸入是否為「信用卡 / 刷卡 / 消費通路推薦」相關問題，再決定如何填欄位。

【是消費問題的判斷】
- 提到通路、商家、金額、付款方式、回饋率、卡片名稱 → 是
- 模糊但明顯在問付款建議（「該用哪張卡」「最划算」等）→ 是
- 純粹閒聊（天氣、心情、新聞）、技術問題、與信用卡無關的詢問 → 否

【是消費問題時】
- is_consumption_scenario = true，off_topic_message = ""
- 通路判斷：
  - 「在日本」「美國刷卡」「海外」「國外」「境外」→ overseas_general
  - 「出國買機票」「訂飯店」→ travel（票券本身在國內買）
  - 「出國刷卡買東西」「日本買藥妝」→ overseas_general（消費發生在國外）
  - 商家名（7-11、全聯、momo、UberEats…）→ 對應 channel_id
  - 同時提到多個通路時全部列出
  - 是消費問題但找不到明確通路 → general
- 金額：抓最具體的數字，無金額則填 0

【不是消費問題時】
- is_consumption_scenario = false
- channels = [], amount = 0
- off_topic_message：30-60 字繁體中文，禮貌說明你只協助信用卡消費問題，並給一個範例（如「想知道去全聯買菜該用哪張卡嗎？」）"""


def parse_scenario(text: str) -> Optional[dict]:
    """
    用 Claude 解析消費情境。

    Returns:
        {"channels": [{"channel_id": "...", "merchant_or_keyword": "..."}, ...],
         "amount": 1500.0}
        失敗時回傳 None（呼叫端應 fallback 到 regex 解析器）。
    """
    client = _client()
    if client is None:
        return None

    try:
        resp = client.messages.create(
            model=PARSER_MODEL,
            max_tokens=512,
            system=_PARSER_SYSTEM,
            tools=[_PARSE_TOOL],
            tool_choice={"type": "tool", "name": "extract_consumption_intent"},
            messages=[{"role": "user", "content": text}],
        )
    except Exception:
        return None

    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "extract_consumption_intent":
            data = block.input or {}

            is_consumption = bool(data.get("is_consumption_scenario", True))
            off_topic_message = (data.get("off_topic_message") or "").strip()

            # 不是消費問題：直接回傳，不要再 fallback 到 general
            if not is_consumption:
                return {
                    "is_consumption_scenario": False,
                    "off_topic_message": off_topic_message or
                        "我是信用卡消費建議助理，只能協助回答刷卡、通路推薦相關問題。例如：「去全聯買菜花 1500，該用哪張卡？」",
                    "channels": [],
                    "amount": 0.0,
                }

            # 是消費問題：防呆 channel_id 都在合法清單
            channels = []
            for ch in data.get("channels", []) or []:
                cid = ch.get("channel_id", "general")
                if cid not in _VALID_CHANNEL_IDS:
                    cid = "general"
                channels.append({
                    "channel_id": cid,
                    "merchant_or_keyword": ch.get("merchant_or_keyword", "") or "",
                })
            if not channels:
                channels = [{"channel_id": "general", "merchant_or_keyword": ""}]
            return {
                "is_consumption_scenario": True,
                "off_topic_message": "",
                "channels": channels,
                "amount": float(data.get("amount") or 0),
            }
    return None


# ── 為推薦結果產生中文理由 ────────────────────────────────────────────────────

_REASONER_SYSTEM = """你是信用卡推薦說明助理。針對每張卡給一段精簡（25-60 字）的推薦理由，內容要：
1. 點出該卡在此情境的賣點（回饋率、回饋類型如現金/紅利/mo幣）
2. 若是 fallback（is_fallback=true）必須明確說「此卡無此通路專屬回饋，套用一般消費 X% 計算」
3. 若有條件（conditions 非空）必須一併提醒，特別是 ⚠️ 警告、登錄、金額門檻、回饋上限
4. 即將到期（expiring_soon=true）要提醒
5. 純繁體中文、口吻親切但專業，不要寒暄不要重複卡名"""


_REASON_TOOL = {
    "name": "explain_recommendations",
    "description": "為每張推薦卡產生一段中文推薦理由。",
    "input_schema": {
        "type": "object",
        "properties": {
            "reasons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "card_id": {"type": "string"},
                        "reason": {"type": "string", "description": "25-60 字推薦理由"},
                    },
                    "required": ["card_id", "reason"],
                },
            },
        },
        "required": ["reasons"],
    },
}


def generate_reasons(
    scenario: str,
    channel_name: str,
    amount: float,
    recommendations: list[dict],
) -> dict[str, str]:
    """
    為一組推薦卡片產生 {card_id: reason} 對照表。

    呼叫失敗時回傳空字典（呼叫端應使用 cashback_description 作為 fallback）。
    """
    client = _client()
    if client is None or not recommendations:
        return {}

    # 只送必要欄位給 LLM，省 token
    compact = []
    for r in recommendations:
        compact.append({
            "card_id": r.get("card_id"),
            "card_name": r.get("card_name"),
            "cashback_rate": r.get("cashback_rate"),
            "cashback_type": r.get("cashback_type"),
            "cashback_description": r.get("cashback_description", ""),
            "estimated_cashback": r.get("estimated_cashback"),
            "max_cashback_per_period": r.get("max_cashback_per_period"),
            "valid_end": r.get("valid_end"),
            "expiring_soon": r.get("expiring_soon", False),
            "conditions": r.get("conditions", ""),
            "is_fallback": r.get("is_fallback", False),
            "rank": r.get("rank"),
        })

    user_msg = json.dumps({
        "scenario": scenario,
        "channel": channel_name,
        "amount": amount,
        "candidates": compact,
    }, ensure_ascii=False)

    try:
        resp = client.messages.create(
            model=REASONER_MODEL,
            max_tokens=1024,
            system=_REASONER_SYSTEM,
            tools=[_REASON_TOOL],
            tool_choice={"type": "tool", "name": "explain_recommendations"},
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception:
        return {}

    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "explain_recommendations":
            out: dict[str, str] = {}
            for item in (block.input or {}).get("reasons", []) or []:
                cid = item.get("card_id")
                reason = item.get("reason", "").strip()
                if cid and reason:
                    out[cid] = reason
            return out
    return {}
