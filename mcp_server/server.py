"""
server.py
---------
Phase 3：CTBC 支付建議 MCP Server（FastMCP）

啟動方式：
    python -m mcp_server.server          # stdio 模式（給 Agent 使用）
    mcp dev mcp_server/server.py         # 開發模式（帶 Inspector UI）

Tools（6個）：
    search_by_channel     → 依通路搜尋最優卡
    recommend_payment     → 依情境推薦最佳刷卡
    compare_cards         → 多卡回饋比較
    get_promotions        → 取得持有卡的優惠活動
    get_card_details      → 取得卡片完整資訊
    list_all_cards        → 列出所有可用卡片 ID（輔助）

Resources（2個）：
    card://ctbc/{card_id}  → 單張卡片 JSON
    channels://ctbc/all    → 通路分類表
"""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from .tools.compare import compare_cards as _compare_cards
from .tools.promotions import get_card_details as _get_card_details
from .tools.promotions import get_promotions as _get_promotions
from .tools.recommend import recommend_payment as _recommend_payment
from .tools.search import search_by_channel as _search_by_channel
from .utils.data_loader import (
    get_all_cards,
    get_card_by_id,
    get_cards_menu,
    get_channels_map,
    get_data_summary,
)

# ── FastMCP 初始化 ────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="CTBC Payment Advisor",
    instructions=(
        "你是中國信託銀行（CTBC）信用卡支付建議服務。"
        "工作流程："
        "(1) 接到消費場景時，優先呼叫 search_by_channel（每個通路查一次）。"
        "(2) 若需要橫向比較持有卡 → 呼叫 compare_cards。"
        "(3) 推薦結果想補活動資訊 → 呼叫 get_promotions。"
        "(4) 想確認單卡完整條件 → 呼叫 get_card_details。"
        "重要規則："
        "所有 Tool 的 cards_owned 參數必須【完全等於】使用者實際持有的 card_id 清單，不可增刪。"
        "凡涉及『海外／國外／出國／日本／韓國／歐美』等場景，channel 必須使用 'overseas_general'，"
        "不要因為商家類型而選 pharmacy/supermarket 等國內通路。"
        "與信用卡無關的閒聊請禮貌拒絕，不要呼叫任何工具。"
    ),
    host=os.getenv("MCP_HOST", os.getenv("HOST", "0.0.0.0")),
    port=int(os.getenv("MCP_PORT", os.getenv("PORT", "8000"))),
    # streamable_http_app() 內部會掛載在這個 path；改為 "/" 讓我們在 http_app.py
    # 透過 Mount("/mcp", ...) 對外，避免路徑重複成 /mcp/mcp。
    streamable_http_path="/",
)


# ── Tool 1：search_by_channel ─────────────────────────────────────────────────

@mcp.tool()
def search_by_channel(
    channel: str,
    cards_owned: list[str],
    amount: float = 0,
    top_k: int = 3,
) -> dict:
    """
    從使用者持有的信用卡中，找出在【特定通路】回饋最高的卡片。

    這是「主力查詢工具」—— 使用者一旦提到任何具體消費場景就應該優先呼叫此工具。
    一次只能查一個通路；若使用者問題涉及多個通路（如「全聯和星巴克」），請分別多次呼叫。

    ▎channel 參數請從以下 17 個 channel_id 擇一（標準 id 優先於商家名稱）：
    - "convenience_store" — 超商：7-11、全家、萊爾富、OK
    - "supermarket"       — 超市／量販：全聯、家樂福、大潤發
    - "wholesale"         — 量販倉儲：Costco 好市多
    - "ecommerce"         — 電商：蝦皮、momo、PChome、Yahoo 購物
    - "food_delivery"     — 外送：Uber Eats、foodpanda
    - "transport"         — 交通：高鐵、台鐵、捷運、悠遊卡、計程車
    - "dining"            — 餐飲：餐廳、咖啡廳、星巴克、麥當勞、手搖飲
    - "travel"            — 旅遊：訂房、訂機票、KKday、Klook、旅行社
    - "entertainment"     — 娛樂：電影院、KKBOX、Netflix、健身房
    - "gas_station"       — 加油站：中油、台塑
    - "pharmacy"          — 藥妝：屈臣氏、康是美、寶雅（國內）
    - "mobile_payment"    — 行動支付：LINE Pay、Apple Pay、街口、悠遊付
    - "department_store"  — 百貨公司：遠東SOGO、新光三越、統一時代百貨、微風、漢神
    - "insurance"         — 保費：壽險、產險、健康險、汽車保險
    - "telecom"           — 電信費：台灣大哥大、中華電信、遠傳
    - "general"           — 一般消費（找不到對應通路才用）
    - "overseas_general"  — 海外消費（國外刷卡，含實體店與境外網購）

    ▎特別重要：海外消費的判斷規則
    若情境含「日本／韓國／泰國／歐美／國外／海外／出國／旅遊」等關鍵字，
    **必須使用 "overseas_general"**，不要因為商家類型（藥妝、超商等）而選國內通路。
    原因：海外刷卡走信用卡「海外消費」費率，與國內同類商家完全不同卡別會勝出。
    若想同時凸顯商家類型，可【兩個都查】後比較：
      1. search_by_channel(channel="overseas_general", ...)
      2. search_by_channel(channel="pharmacy", ...) 等對應商家通路

    ▎範例對應
    - 「全聯買菜」→ channel="supermarket"
    - 「好市多買東西」→ channel="wholesale"
    - 「SOGO百貨消費」→ channel="department_store"
    - 「繳保費」→ channel="insurance"
    - 「台灣大哥大繳費」→ channel="telecom"
    - 「日本買藥妝 3000 日圓」→ channel="overseas_general"（不是 pharmacy）
    - 「台灣屈臣氏買面膜」→ channel="pharmacy"
    - 「用 LINE Pay 在 momo 買東西」→ 兩次：channel="mobile_payment" 與 channel="ecommerce"

    Args:
        channel:     channel_id 字串（請優先使用上表的標準 id）
        cards_owned: 使用者持有的卡 card_id 列表（必填，不可為空）
        amount:      預計消費金額（新台幣），用於計算預估回饋（0 = 不計算）
        top_k:       最多回傳幾張卡的結果（預設 3）
    """
    return _search_by_channel(
        channel=channel,
        cards_owned=cards_owned,
        amount=amount,
        top_k=top_k,
    )


# ── Tool 2：recommend_payment ─────────────────────────────────────────────────

@mcp.tool()
def recommend_payment(
    scenario: str,
    cards_owned: list[str],
) -> dict:
    """
    針對【自然語言消費情境】做一站式推薦。內部會自動解析情境、抽取通路與金額，
    再對每個通路呼叫 search_by_channel，最後綜合產出建議。

    ▎這個工具 vs search_by_channel 的選用判斷
    - 使用者輸入結構清楚、單一通路 → 直接用 search_by_channel（更可控）
    - 使用者輸入是模糊自然語句、可能多通路 → 可用 recommend_payment 一次處理
    - 不確定時，優先用 search_by_channel 並逐個通路查詢（推薦做法）

    ▎注意
    此工具的內部解析使用簡略字典，對「海外/國外」場景的辨識不如直接呼叫
    search_by_channel(channel="overseas_general") 精準。
    若情境明顯與海外消費有關，請改用 search_by_channel。

    Args:
        scenario:    自然語言消費情境描述
        cards_owned: 使用者持有的卡 card_id 列表（必填，不可為空）
    """
    return _recommend_payment(
        scenario=scenario,
        cards_owned=cards_owned,
    )


# ── Tool 3：compare_cards ─────────────────────────────────────────────────────

@mcp.tool()
def compare_cards(
    cards_owned: list[str],
    channel: str = "",
    amount: float = 1000,
) -> dict:
    """
    比較使用者持有的多張信用卡，列出每張卡在指定通路（或全通路）的回饋表現。

    ▎適用場景
    - 「我的這幾張卡哪張在超商最划算？」
    - 「幫我整體比較一下我的所有卡」
    - 「LINE Pay 卡和 uniopen 卡哪個適合刷電商？」

    ▎與 search_by_channel 的差別
    - search_by_channel：找「該通路最佳的 top_k 張卡」→ 排序、推薦用
    - compare_cards：把指定的所有卡【全部列出】橫向比較 → 對照用，不排序

    Args:
        cards_owned: 使用者持有的卡 card_id 列表（必填，不可為空）
        channel:     指定比較通路（17 個 channel_id 之一），不填則比較全通路
        amount:      參考消費金額（新台幣，預設 NT$1,000）
    """
    return _compare_cards(
        cards_owned=cards_owned,
        channel=channel,
        amount=amount,
    )


# ── Tool 4：get_promotions ────────────────────────────────────────────────────

@mcp.tool()
def get_promotions(
    cards_owned: list[str],
    category: str = "",
    valid_only: bool = True,
) -> dict:
    """
    取得目前有效的信用卡優惠活動清單，以及持有卡中「即將到期」的優惠提醒。

    ▎適用場景
    - 使用者主動問「最近有什麼優惠？」「有沒有優惠快到期？」
    - 推薦完想補一句「順帶提醒目前還有 X 活動」（加分用）

    ▎注意
    此工具回傳的是【活動快訊】，不是卡片本身的長期回饋率。
    要查回饋率請用 search_by_channel 或 get_card_details。

    Args:
        cards_owned: 使用者持有的卡 card_id 列表（必填，不可為空）
        category:    通路分類篩選（17 個 channel_id 之一），不填回傳全部
        valid_only:  是否只回傳有效優惠（預設 True，幾乎不需改）
    """
    return _get_promotions(
        cards_owned=cards_owned,
        category=category,
        valid_only=valid_only,
    )


# ── Tool 5：get_card_details ──────────────────────────────────────────────────

@mcp.tool()
def get_card_details(card_id: str) -> dict:
    """
    取得單張信用卡的完整資料：所有通路回饋率、條件、截止日、年費、備註。

    ▎適用場景
    - 使用者問「ctbc_c_uniopen 這張卡有什麼回饋？」
    - 推薦後想補充某張卡的完整條件
    - 確認某張卡是否有特定通路的優惠

    ▎注意
    一次只能查一張卡。要查多張請多次呼叫。
    若是要排序、推薦或橫向比較，請改用 search_by_channel 或 compare_cards。

    Args:
        card_id: 卡片 ID，格式如 "ctbc_c_linepay"（不知道時可先用 list_all_cards 查詢）
    """
    return _get_card_details(card_id=card_id)


# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.resource("card://ctbc/{card_id}")
def get_card_resource(card_id: str) -> str:
    """
    提供單張卡片的完整 JSON 資料作為 MCP Resource。
    URI 格式：card://ctbc/ctbc_c_linepay
    """
    card = get_card_by_id(card_id)
    if not card:
        return json.dumps({"error": f"找不到卡片：{card_id}"}, ensure_ascii=False)
    return json.dumps(card, ensure_ascii=False, indent=2)


@mcp.resource("channels://ctbc/all")
def get_channels_resource() -> str:
    """
    提供完整的通路分類對照表 JSON。
    URI 格式：channels://ctbc/all
    """
    return json.dumps(get_channels_map(), ensure_ascii=False, indent=2)


# ── 輔助 Tools（供 Agent 查詢可用 ID）───────────────────────────────────────

@mcp.tool()
def list_all_cards() -> dict:
    """
    列出資料集中所有可用的信用卡 card_id 和卡名。

    ▎適用場景
    - 你不確定某張卡的 card_id 時，先用此工具查表
    - 一般對話中通常【不需要】主動呼叫；使用者持有的卡已在 system prompt 告知

    Returns:
        {
          "last_updated": "2026-05-17",
          "card_count": 13,
          "cards": [{"card_id": "...", "card_name": "...", "tags": [...]}]
        }
    """
    summary = get_data_summary()
    return {
        "last_updated": summary.get("last_updated"),
        "card_count":   summary.get("card_count"),
        "cards":        get_cards_menu(),
    }


# ── 啟動入口 ──────────────────────────────────────────────────────────────────

def main():
    """套件安裝後的指令入口（ctbc-mcp）。"""
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mount_path = os.getenv("MCP_MOUNT_PATH")
    mcp.run(transport=transport, mount_path=mount_path)


if __name__ == "__main__":
    main()
