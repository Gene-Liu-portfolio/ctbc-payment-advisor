"""
mcp_bridge.py
-------------
MCP Tools 與 Groq Function Calling 的橋接層。

功能：
1. 啟動時透過 MCP tools/list 動態發現 Server 工具，自動轉換為 Groq Tool Schema
2. cards_owned 由 Agent 自動注入，不暴露給 LLM
3. 提供 execute_tool() 函式，透過 HTTP 呼叫遠端 MCP Server
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

MCP_SERVER_URL = os.environ.get(
    "MCP_SERVER_URL",
    "https://ctbc-payment-advisor.onrender.com/mcp",
)

# cards_owned 由 Agent 注入，不讓 LLM 看到也無法填寫
_HIDDEN_PARAMS = {"cards_owned"}

_session_id: str | None = None
_discovered_tools: list[dict] | None = None


# ── MCP HTTP 通訊層 ──────────────────────────────────────────────────────────

def _parse_sse_response(resp: requests.Response) -> dict:
    """
    解析 MCP Streamable HTTP 的 SSE 回應。
    強制 UTF-8 解碼，避免 requests 自動用 ISO-8859-1 導致中文截斷。
    """
    body = resp.content.decode("utf-8")
    events: list[str] = []
    current_data_lines: list[str] = []
    for line in body.split("\n"):
        if line.startswith("data:"):
            current_data_lines.append(line[len("data:"):].lstrip())
        elif line.strip() == "" and current_data_lines:
            events.append("\n".join(current_data_lines))
            current_data_lines = []
    if current_data_lines:
        events.append("\n".join(current_data_lines))

    for event_data in events:
        try:
            payload = json.loads(event_data)
        except json.JSONDecodeError:
            continue
        if "error" in payload:
            return {"error": payload["error"].get("message", "未知錯誤")}
        return payload

    return {"error": "MCP server 回傳格式無法解析"}


def _mcp_request(method: str, params: dict, *, need_session: bool = True) -> dict:
    """發送 JSON-RPC 請求到 MCP Server，回傳解析後的 payload。"""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if need_session:
        headers["mcp-session-id"] = _get_session_id()

    resp = requests.post(
        MCP_SERVER_URL,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        },
        timeout=30,
    )
    resp.raise_for_status()

    # initialize 回傳 session ID，需額外處理
    if method == "initialize":
        sid = resp.headers.get("mcp-session-id")
        if sid:
            global _session_id
            _session_id = sid

    return _parse_sse_response(resp)


def _get_session_id() -> str:
    """初始化 MCP session，回傳 session ID（同一 process 內只初始化一次）。"""
    global _session_id
    if _session_id:
        return _session_id

    _mcp_request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ctbc-agent", "version": "2.0"},
        },
        need_session=False,
    )
    if not _session_id:
        raise RuntimeError("MCP server 未回傳 session ID，請確認 server 是否正常運作")
    return _session_id


# ── 動態工具發現 ──────────────────────────────────────────────────────────────

def _mcp_schema_to_groq(tool: dict) -> dict:
    """
    將 MCP tool schema 轉換為 Groq function calling 格式。
    自動移除 cards_owned 參數（由 Agent 注入，不讓 LLM 控制）。
    """
    input_schema = tool.get("inputSchema", {})
    properties = dict(input_schema.get("properties", {}))
    required = list(input_schema.get("required", []))

    # 移除隱藏參數
    for param in _HIDDEN_PARAMS:
        properties.pop(param, None)
        if param in required:
            required.remove(param)

    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def discover_tools() -> list[dict]:
    """
    從 MCP Server 動態發現所有工具，轉換為 Groq Tool Schema。
    結果會快取，同一 process 只呼叫一次。
    """
    global _discovered_tools
    if _discovered_tools is not None:
        return _discovered_tools

    payload = _mcp_request("tools/list", {})
    mcp_tools = payload.get("result", {}).get("tools", [])

    # 排除輔助工具（reload_data 不需要暴露給 LLM）
    _EXCLUDE_TOOLS = {"reload_data"}
    groq_tools = [
        _mcp_schema_to_groq(t)
        for t in mcp_tools
        if t["name"] not in _EXCLUDE_TOOLS
    ]

    _discovered_tools = groq_tools
    return _discovered_tools


def get_tool_definitions() -> list[dict]:
    """取得 Groq 格式的工具定義（動態發現，含快取）。"""
    return discover_tools()


# ── 工具呼叫 ──────────────────────────────────────────────────────────────────

def _call_tool(tool_name: str, arguments: dict) -> dict:
    """透過 HTTP 呼叫遠端 MCP tool，回傳 result dict。"""
    payload = _mcp_request("tools/call", {"name": tool_name, "arguments": arguments})

    # 從 JSON-RPC result 中取出工具回傳值
    content = payload.get("result", {}).get("content", [])
    if content and content[0].get("type") == "text":
        try:
            return json.loads(content[0]["text"])
        except json.JSONDecodeError:
            return {"text": content[0]["text"]}
    return payload.get("result", payload)


def _get_cards_menu_remote() -> list[dict]:
    """從遠端取得卡片選單。"""
    result = _call_tool("list_all_cards", {})
    return result.get("cards", [])


# ── 工具執行（自動注入 cards_owned）─────────────────────────────────────────

def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    cards_owned: list[str],
) -> str:
    """
    執行指定的 MCP 工具，自動注入 cards_owned 後回傳 JSON 字串。

    Args:
        tool_name:   工具名稱
        arguments:   LLM 生成的參數（不含 cards_owned）
        cards_owned: 本 session 的持卡清單（自動注入）

    Returns:
        工具執行結果的 JSON 字串
    """
    args = dict(arguments)
    args["cards_owned"] = cards_owned  # 自動注入，不讓 LLM 控制

    try:
        result = _call_tool(tool_name, args)
    except Exception as e:
        result = {"error": f"工具執行失敗：{e}"}

    return json.dumps(result, ensure_ascii=False)


def get_all_card_ids() -> list[str]:
    """取得所有卡片的 card_id 清單（供選單使用）。"""
    return [c["card_id"] for c in _get_cards_menu_remote()]


def get_all_cards_for_menu() -> list[dict]:
    """取得供選單顯示的卡片清單。"""
    return _get_cards_menu_remote()
