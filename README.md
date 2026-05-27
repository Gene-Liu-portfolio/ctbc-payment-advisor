# 中國信託 Agent x MCP 支付建議服務模組設計與實作

基於 **Claude × MCP（Model Context Protocol）** 架構的智慧刷卡建議服務。React 前端可透過 structured SSE 呼叫一般推薦流程，也可透過 Anthropic **MCP Connector** 讓 Claude 直接以 MCP 協定呼叫工具（非 function-calling 包裝），從使用者持有的 **13 張熱門與 benchmark 信用卡**（中信 6 + 非中信 7）中推薦最佳刷卡選擇。

本專案合作對象為中國信託；資料集中額外納入部分非中信信用卡作為跨銀行推薦邏輯與 benchmark 測試資料，不代表與該銀行合作。

> 資料版本：2026-05-19 | 架構版本：v8.1（Structured SSE + MCP Connector）

---

## Features

- **單一前端（React）** — Vite + React 18 + Tailwind 4 + Radix UI 統一 demo 介面
- **真 MCP 協定整合** — Claude API 透過 `mcp_servers` 參數直接連 `/mcp`，前端可即時看到 Claude 呼叫了哪些工具
- **雙模式 SSE 串流** — `/api/recommend/stream` 提供一般推薦流程；`/api/chat` 提供 Claude Agent 對話與 tool_use 事件
- **情境推薦** — 輸入「去全聯買菜 1500 元」，自動推薦最優卡與預估回饋
- **多通路解析** — 一次輸入可辨識多個通路（如全聯 + foodpanda），分別推薦
- **持卡比較 / 優惠查詢 / 單卡詳情** — 透過 chat 自然觸發對應 MCP 工具
- **海外消費辨識** — Claude 解析與 deterministic fallback 均可識別 `overseas_general`
- **回饋種類區分** — 現金 / LINE Points / OPENPOINT / 哩程 / 紅利點數
- **優惠到期提醒** — `expiring_soon` 自動標記，Claude 會主動提醒

---

## Why MCP

本專案採用 MCP 不是為了把工具呼叫換一種包裝，而是把「推薦邏輯、資料來源、限制條件」固定在可控的後端服務中。LLM 負責理解使用者問題與選擇工具；實際可查哪些卡、可用哪些通路、怎麼計算回饋，仍由 `/mcp` 與 deterministic tool runtime 控制。

這個設計帶來三個專案價值：

- **推薦結果更可靠** — MCP 工具只從 `merged_cards.json`、通路對應表與後端計算邏輯取資料，降低 LLM 自行補卡片、補優惠或補回饋率的風險。
- **更容易接進銀行既有數位渠道** — `/mcp` 是標準工具介面，同一套能力未來可提供給 Claude API、內部客服工具、行動銀行、網銀或其他 MCP client，不需要為每個入口重寫 function schema。
- **核心規則留在 bank-owned backend** — 推薦排序、資料更新、優惠條件、fallback 規則都在後端維護；prompt 只負責引導 LLM 何時呼叫工具，不承擔資料真實性的責任。

`cards_owned` 由前端選卡狀態傳入後端，並寫入 chat system prompt 約束 Claude 工具呼叫時只能使用該 card_id 清單；deterministic REST/SSE 推薦流程則直接使用 request body 中的 `cards_owned`。使用者勾選的持卡清單是權限邊界：Claude 可以解讀需求、選擇工具，但推薦邏輯必須以使用者實際持有的 card_id 清單為準。這能降低推薦未持有卡的風險，並讓前端狀態、後端查詢與未來銀行登入 session 保持一致。

---

## Supported Cards（13 張）

**中信銀行（CTBC）**

| Card ID | 卡名 |
|---------|------|
| `ctbc_c_hanshin` | 漢神聯名卡 |
| `ctbc_c_uniopen` | uniopen聯名卡 |
| `ctbc_c_cs` | 遠東SOGO聯名卡 |
| `ctbc_c_linepay` | LINE Pay信用卡 |
| `ctbc_c_cal` | 中華航空聯名卡 |
| `ctbc_c_cpc` | 中油聯名卡 |

**Benchmark cards（非合作銀行資料）**

| Card ID | 卡名 |
|---------|------|
| `fubon_c_j` | 富邦J卡 |
| `fubon_c_diamond` | 富邦鑽保卡 |
| `fubon_b_lifestyle` | 富邦富利生活卡 |
| `fubon_c_costco` | 富邦Costco聯名卡 |
| `fubon_c_guardians` | 富邦悍將勇士聯名卡 |
| `fubon_c_momo` | 富邦momo聯名卡 |
| `fubon_c_twm` | 台灣大哥大Open Possible聯名卡 |

### 卡片 JSON 欄位說明

每張卡片在 `data/processed/merged_cards.json` 中為一個 object，結構參考 `data/schemas/card_schema.json`（JSON Schema Draft-07）。

**卡片層級欄位**

| 欄位 | 型別 | 說明 |
|------|------|------|
| `card_id` | string | 卡片唯一識別碼，格式 `{bank}_{name}`（例：`ctbc_c_linepay`） |
| `card_name` | string | 卡片完整名稱 |
| `card_status` | enum | `active` 現行 / `discontinued` 已停發 / `unknown` 待確認 |
| `card_org` | enum \| null | 發卡組織：`VISA` / `Mastercard` / `JCB` / `AE` / `UnionPay` |
| `annual_fee` | int \| null | 年費（NTD），`0` = 免年費 |
| `annual_fee_waiver` | string \| null | 免年費條件說明 |
| `card_url` | string \| null | 官網卡片介紹頁 URL |
| `apply_url` | string \| null | 線上申辦頁 URL |
| `tags` | string[] | 卡片標籤，用於快速搜尋（例：`["餐飲美食", "行動支付"]`） |
| `notes` | string \| null | 備註說明 |
| `data_source` | enum | 資料來源：`api` / `scraper` / `manual` / `manual_seed` |
| `last_verified` | date \| null | 最後人工驗證日期（`YYYY-MM-DD`） |
| `channels` | object[] | 各通路優惠設定（見下方） |
| `deals` | object[] | （Optional）microsite 商家層級優惠，build-time 由 `microsite_deals.json` 注入 |

**`channels[]` 內欄位**（單一通路的回饋設定）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `channel_id` | enum | 通路代碼：`convenience_store` / `supermarket` / `ecommerce` / `food_delivery` / `transport` / `dining` / `travel` / `entertainment` / `gas_station` / `pharmacy` / `mobile_payment` / `general` / `overseas_general` / `wholesale` / `department_store` / `insurance` / `telecom` |
| `channel_name` | string | 通路中文名稱 |
| `merchants` | string[] | 適用商家清單，**空陣列 = 該類別全部適用** |
| `cashback_type` | enum | `cash` 現金 / `points` 紅利點數 / `miles` 哩程 |
| `cashback_rate` | float \| null | 回饋率，`0.05` = 5%（範圍 0–1） |
| `cashback_description` | string \| null | 回饋說明原文（資料來源原始文字） |
| `max_cashback_per_period` | int \| null | 每期回饋上限（NTD），`null` = 無上限 |
| `min_spend` | int \| null | 最低消費門檻（NTD），`null` / `0` = 不限金額 |
| `conditions` | string \| null | 完整條件說明（含限制、排除項） |
| `valid_forever` | bool | `true` = 長期有效（非限時優惠） |
| `valid_start` | date \| null | 優惠開始日（`YYYY-MM-DD`） |
| `valid_end` | date \| null | 優惠截止日，`null` = 無截止 |
| `expiring_soon` | bool | 30 天內到期自動標記 `true`（由 `data_cleaner` 計算） |
| `data_source` | string | 該通路資料來源：`api` / `card_feature_direct` / `microsite` / `manual` |

**多重 `channel_id` 的處理**：同一張卡可能有多筆相同 `channel_id`（例：`general` 出現在 `cash` 和 `points` 兩種回饋形式），代表不同 `cashback_type` 的並列回饋方案。

---

## Architecture

<details>
<summary>Current backend flow</summary>

```
User input
├─ General recommendation mode
│  POST /api/recommend/stream
│  ├─ parse_scenario()        Claude Haiku or regex fallback
│  ├─ search_by_channel()     core ranking tool
│  ├─ get_card_details()      conditions and limits
│  ├─ get_promotions()        active promos and expiry reminders
│  ├─ generate_reasons()      Chinese explanation
│  └─ SSE result              recommendations[].best_options[]
│
└─ Agent chat mode
   POST /api/chat
   └─ Claude Sonnet
      └─ MCP Connector
         └─ /mcp Streamable HTTP
            └─ FastMCP tools/resources
               ├─ tools: search_by_channel, recommend_payment, compare_cards
               ├─ tools: get_card_details, get_promotions
               ├─ tools: list_all_cards, reload_data
               ├─ resource: card://ctbc/{card_id}
               └─ resource: channels://ctbc/all

Shared runtime layer
├─ channel_mapper.py
├─ data_loader.py
├─ calculator.py
├─ llm_parser.py
└─ tool_trace.py
   └─ data/processed/merged_cards.json
      ├─ deals[]      merchant-level offers
      └─ channels[]   channel-level offers

Build-time data flow
scraper/merge.py ──> data/processed/merged_cards.json
```

</details>

### MCP Tools

| Tool / Resource | 負責內容 |
|-----------------|----------|
| `search_by_channel` | 單一通路的主力排序工具。依使用者持有卡、通路、金額計算 top cards，並保留 fallback、條件與計算 trace。 |
| `recommend_payment` | 一站式自然語言推薦。解析情境中的金額與多個通路，再逐一呼叫 `search_by_channel` 產出整體建議。 |
| `compare_cards` | 橫向比較使用者持有卡，可針對指定通路或全通路列出各卡表現。 |
| `get_promotions` | 查詢目前有效活動與持有卡中即將到期的優惠提醒；不是長期回饋率來源。 |
| `get_card_details` | 回傳單張卡完整資料，包含通路回饋、限制條件、截止日、年費與備註。 |
| `list_all_cards` | 輔助查詢可用 `card_id` 與卡名；一般對話通常不需要主動呼叫。 |
| `reload_data` | 維運用工具，資料更新後手動重新載入 `data/processed/`；一般使用者對話不應呼叫。 |
| `card://ctbc/{card_id}` | MCP Resource，提供單張卡完整 JSON。 |
| `channels://ctbc/all` | MCP Resource，提供完整通路分類對照表。 |

**Key Design Decisions:**

- **一般推薦模式不經過 Sonnet Agent** — `/api/recommend/stream` 由後端固定執行 parse → search → details → promotions → reasons，前端以 structured SSE 顯示每一步
- **真 MCP Connector**（非 function calling）— `/api/chat` 後端呼叫 `anthropic.beta.messages.stream(mcp_servers=[...])`，Claude 直接以 MCP JSON-RPC 連 `/mcp`，前端零侵入即可看到 `tool_use` 事件；同一個 `/mcp` 也可供其他 MCP client 重用
- **Unified ASGI app** — REST API、SSE chat、MCP Streamable HTTP 全部由同一個 Starlette + uvicorn 提供（port 8000），方便 Render 單服務部署
- **Build-time merge** — 三層資料（API + card_features + microsite_deals）在 build time 合併為 `merged_cards.json`，runtime 只需查兩層
- **推薦防呆規則** — 具體商家會使用 `merchant_hint` 精準比對；非現金點數不換算 NT$；`general` fallback 只採安全的一般消費基礎回饋
- **Session 提供 cards_owned** — 前端把使用者勾選的持卡清單傳入 chat session；後端 system prompt 約束 Claude 呼叫工具時只能使用該清單，deterministic 推薦流程則直接以 request body 的 `cards_owned` 查詢

---

## Quick Start

### Prerequisites

- Python 3.10+ 與 Node 18+
- [Anthropic API Key](https://console.anthropic.com)

### Installation

```bash
git clone https://github.com/Gene-Liu-portfolio/ctbc-payment-advisor.git
cd ctbc-payment-advisor

# Backend
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# 編輯 .env 填入 ANTHROPIC_API_KEY

# Frontend
cd "Credit Card AI Payment Advisor"
npm install
```

### Usage

**1. 啟動後端**（同時提供 REST + MCP + Chat，port 8000）

```bash
python -m mcp_server.http_app
```

端點：
- `GET  /api/cards` — 卡片清單
- `POST /api/recommend/stream` — 一般推薦模式 structured SSE
- `POST /api/chat` — Claude SSE 串流（透過 MCP Connector 呼叫工具）
- `POST /api/{search,compare,promotions,card-details}` — REST deterministic 查詢
- `POST /api/recommend` — 情境推薦（Claude Haiku 輔助解析情境與產生理由；失敗時 regex fallback）
- `*    /mcp` — MCP Streamable HTTP（給 Claude API 用，需公網 HTTPS 才有 effect）

**2. 啟動前端**（Vite dev server，port 5173；目前設定會將 `/api` proxy 到 Render backend）

```bash
cd "Credit Card AI Payment Advisor"
npm run dev
```

開 `http://localhost:5173/`：勾選持有的卡 → 點 Start → 用自然語言聊天 → Claude 即時呼叫 MCP 工具回覆。

若要測本地後端，需先啟動 `python -m mcp_server.http_app`，再將 `Credit Card AI Payment Advisor/vite.config.ts` 的 `/api` proxy target 從 Render URL 改成 `http://127.0.0.1:8000`。

> ⚠️ **本地 chat 限制**：Anthropic 機房需從公網連到你的 `/mcp`。本地測試請：
> (a) 把 MCP Server 部署到 Render（已預先設定 default URL `https://ctbc-payment-advisor.onrender.com/mcp`），或
> (b) 開 Cloudflared tunnel：`cloudflared tunnel --url http://localhost:8000`，再設 env `MCP_PUBLIC_URL=https://xxx.trycloudflare.com/mcp`。
> 純走 REST API（不經 Claude）則無此限制。

### Deployment（Render）

1. Push 到 GitHub，Render 連 repo，使用 `pyproject.toml` 的 `ctbc-mcp-http` script
2. 設 env `ANTHROPIC_API_KEY` 與（可選）`CLAUDE_AGENT_MODEL`
3. Render 會把同一個服務同時對外暴露 `/api/*`、`/mcp`，前端設 `MCP_PUBLIC_URL` 為自己的 Render URL 即可閉環

---

## Supported Channels

系統支援模糊輸入，自動對應到 17 種標準通路：

| 輸入範例 | 對應通路 |
|---------|---------|
| `7-11`、`小7`、`全家` | 超商 |
| `全聯`、`家樂福`、`大潤發` | 超市／量販 |
| `COSTCO`、`好市多` | 量販倉儲 |
| `蝦皮`、`momo`、`網購` | 電商 |
| `foodpanda`、`Uber Eats` | 外送 |
| `捷運`、`高鐵`、`Uber` | 交通 |
| `麥當勞`、`星巴克` | 餐飲 |
| `機票`、`飯店`、`出國` | 旅遊 |
| `Netflix`、`電影院`、`健身房` | 娛樂 |
| `中油`、`加油` | 加油站 |
| `屈臣氏`、`康是美` | 藥妝 |
| `LINE Pay`、`Apple Pay` | 行動支付 |
| `SOGO`、`新光三越`、`百貨` | 百貨公司 |
| `保費`、`保險費`、`壽險` | 保費 |
| `電信費`、`台灣大哥大`、`中華電信` | 電信費 |
| `一般消費`、`其他消費` | 一般消費 |
| `日本`、`韓國`、`海外` | 海外消費（自動辨識）|

---

## Data Pipeline

```bash
# 1. 爬取中信基礎資料（6 張熱門卡 + 優惠活動）
python -m scraper.run full

# 2. 爬取卡片特色頁回饋率
python -m scraper.run card-feature --direct

# 3. Build-time 三層合併
python -m scraper.merge

# 4. 驗證
python -m pytest tests/test_mcp_tools.py -v
```

### Merge Strategy（`scraper/merge.py`）

```
ctbc_cards.json + fubon_cards.json     → 基礎卡片（13 張）
    + card_features.json               → channels 覆蓋（同 channel_id 取 card_features 優先）
    + microsite_deals.json             → deals 獨立陣列（過濾已過期）
    → merged_cards.json (v2.0)
```

---

## Testing

```bash
# 單元測試（不需 LLM API，純資料邏輯）
python -m pytest tests/test_mcp_tools.py -v
```

### Test Coverage

| 類別 | 數量 | 涵蓋 |
|------|------|------|
| Calculator | 12 | 回饋計算、日期判斷 |
| DataLoader | 12 | 資料載入、查詢、fallback |
| SearchByChannel | 12 | 通路查詢、排序、結構 |
| RecommendPayment | 13 | 金額抽取、通路識別、情境推薦 |
| CompareCards | 7 | 比較邏輯、is_best 標記 |
| Promotions | 5 | 優惠查詢、卡片詳情 |
| Accuracy | 8 | 具體回饋率驗證 |
| EdgeCases | 8 | 空值、特殊字元、邊界條件 |
| ChannelMapping | 18 | 17 種通路與模糊輸入映射案例 |

---

## Project Structure

```
ctbc-payment-advisor/
├── Credit Card AI Payment Advisor/   # React Web Demo（唯一前端）
│   ├── src/app/
│   │   ├── App.tsx                   # 主畫面：卡片選擇 → 多輪 chat
│   │   ├── api.ts                    # fetchCards + streamChat（SSE）
│   │   └── components/
│   │       ├── ChatInput.tsx
│   │       ├── ChatMessage.tsx       # 顯示 text + tool_use chips
│   │       ├── CardSelectionPage.tsx
│   │       ├── LeftSidebar.tsx
│   │       ├── WelcomeSection.tsx
│   │       └── RecommendationCarousel.tsx
│   └── vite.config.ts                # /api → Render backend proxy（本地測試可切到 :8000）
│
├── mcp_server/
│   ├── http_app.py            # ★ 統一 ASGI（REST + MCP + chat）
│   ├── chat.py                # /api/chat — Claude MCP Connector + SSE
│   ├── server.py              # FastMCP server 定義（7 tools + 2 resources）
│   ├── tools/
│   │   ├── search.py          # search_by_channel
│   │   ├── recommend.py       # recommend_payment（情境解析）
│   │   ├── compare.py         # compare_cards
│   │   └── promotions.py      # get_promotions + get_card_details
│   └── utils/
│       ├── data_loader.py     # merged_cards.json 統一存取
│       ├── calculator.py      # 回饋計算
│       └── channel_mapper.py  # 通路名稱正規化
│
├── scraper/
│   ├── ctbc_scraper.py        # CTBC 官方 JSON API
│   ├── card_feature_scraper.py # 卡片特色頁爬蟲
│   ├── microsite_scraper.py   # 商家層級優惠爬蟲
│   ├── merge.py               # Build-time 三層合併
│   └── channel_mapper.py      # 通路對應表（source of truth）
│
├── data/
│   ├── processed/
│   │   ├── merged_cards.json  # ★ Runtime 唯一卡片資料源
│   │   ├── promotions.json    # standalone promotions
│   │   └── channels.json      # 通路分類表
│   ├── scraped/               # card_features.json + microsite_deals.json
│   ├── schemas/card_schema.json  # JSON Schema 驗證
│   └── seed/                  # bootstrap 備援
│
└── tests/
    └── test_mcp_tools.py      # 單元測試（deterministic，不需 LLM）
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Anthropic Claude API（Sonnet 4.6 用於 chat；Haiku 4.5 用於情境解析與推薦理由） |
| LLM ↔ Tools | **MCP Connector**（`anthropic.beta.messages.stream(mcp_servers=...)`，beta `mcp-client-2025-04-04`） |
| MCP Framework | FastMCP（Python `mcp` SDK 1.27+） |
| Transport | Streamable HTTP（SSE） |
| Backend | Starlette + uvicorn（單一 ASGI） |
| Frontend | React 18 + Vite 6 + TypeScript + Tailwind 4 + Radix UI |
| Data | JSON files（build-time merged） |
| Testing | pytest（deterministic，不需 LLM） |

---

## FAQ

**Q: 需要哪些 API Key？**

只需 `ANTHROPIC_API_KEY`。到 https://console.anthropic.com 申請即可。Claude API 會代表你連到 `/mcp` 呼叫工具。

**Q: 為什麼要用 MCP Connector，不直接 function calling？**

詳見前段 **Why MCP**。簡短來說，function calling 需要把工具 schema 綁在單一 LLM API 呼叫中；MCP 讓 `/mcp` 成為可重用的標準工具介面，推薦規則與資料查詢留在後端，未來更容易接到不同數位渠道。

**Q: 富邦卡的資料來源？**

富邦銀行無公開 JSON API，資料為手動整理。需定期人工更新。

**Q: 如何新增卡片或更新資料？**

1. 修改 `data/processed/` 中的原始 JSON
2. 執行 `python -m scraper.merge` 重新合併
3. 重啟（或 redeploy）後端

---

## Contributors

中信銀行實習專案團隊：

| GitHub | 角色 |
|--------|------|
| [@Gene-Liu-portfolio](https://github.com/Gene-Liu-portfolio) | 實習生 |
| [@LarryinMexico](https://github.com/LarryinMexico) | 實習生 |
| [@Lyyyy17](https://github.com/Lyyyy17) | 實習生 |
| [@rockeywang404](https://github.com/rockeywang404) | 實習生 |
