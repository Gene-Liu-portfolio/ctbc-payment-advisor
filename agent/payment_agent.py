"""
payment_agent.py
----------------
Phase 4 Agent 核心：Claude API + MCP Tool Calling + 多輪對話。

流程：
  1. 接收使用者訊息
  2. 連同對話記憶 + System Prompt 送入 Claude
  3. 若 Claude 呼叫 Tool → 執行 MCP Tool（自動注入 cards_owned）→ 回送結果
  4. 重複步驟 2-3 直到生成最終自然語言回覆
"""

from __future__ import annotations

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from .mcp_bridge import get_tool_definitions, execute_tool
from .prompts import build_system_prompt

load_dotenv()

# ── 模型設定 ──────────────────────────────────────────────────────────────────
DEFAULT_MODEL = os.getenv("CLAUDE_AGENT_MODEL", "claude-sonnet-4-6")
MAX_TOOL_ROUNDS = 5  # 防止無限 tool-call loop


class PaymentAgent:
    """
    CTBC 支付建議 Agent。

    Attributes:
        cards_owned:   本 session 持有卡的 card_id 列表
        cards_info:    持有卡的基本資訊（card_id + card_name），用於 System Prompt
        model:         Claude 模型名稱
        history:       多輪對話記憶（user / assistant 訊息，含 tool_use/tool_result blocks）
    """

    def __init__(
        self,
        cards_owned: list[str],
        cards_info: list[dict],
        model: str = DEFAULT_MODEL,
    ):
        self.cards_owned = cards_owned
        self.cards_info  = cards_info
        self.model       = model
        self.history:    list[dict] = []
        self._client     = Anthropic()
        self._system_prompt = build_system_prompt(cards_info)

    # ── 公開介面 ──────────────────────────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        """
        單輪對話：送入使用者訊息，回傳助理的自然語言回覆。
        對話記憶自動累積在 self.history。
        """
        self.history.append({"role": "user", "content": user_message})

        # Tool-calling loop
        for _ in range(MAX_TOOL_ROUNDS):
            response = self._client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self._system_prompt,
                tools=get_tool_definitions(),
                messages=self.history,
                temperature=0.3,
            )

            # 把 assistant 回覆（含可能的 tool_use blocks）寫入歷史
            assistant_blocks = [b.model_dump() for b in response.content]
            self.history.append({"role": "assistant", "content": assistant_blocks})

            # 若無 tool_use → 結束 loop
            if response.stop_reason != "tool_use":
                # 把所有文字 block 串起來作為最終回覆
                text_parts = [b["text"] for b in assistant_blocks if b.get("type") == "text"]
                return "\n".join(text_parts).strip() or ""

            # 執行所有 tool_use blocks，集中放進一則 user tool_result
            tool_results = []
            for block in assistant_blocks:
                if block.get("type") != "tool_use":
                    continue
                tool_name = block["name"]
                arguments = block.get("input", {}) or {}
                tool_result = execute_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    cards_owned=self.cards_owned,
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": tool_result,
                })

            self.history.append({"role": "user", "content": tool_results})

        # 超過 tool round 限制（理論上不應發生）
        return "抱歉，處理您的請求時發生內部錯誤，請重試。"

    def reset_history(self):
        """清空對話記憶，開始新對話。"""
        self.history = []

    def get_history_summary(self) -> str:
        """回傳對話輪次摘要（用於 debug）。"""
        turns = sum(1 for m in self.history if m["role"] == "user" and isinstance(m["content"], str))
        return f"對話記憶：{turns} 輪 / {len(self.history)} 則訊息"
