# 中國信託 Agent x MCP 支付建議服務模組設計與實作

[![CI](https://github.com/Gene-Liu-portfolio/ctbc-payment-advisor/actions/workflows/ci.yml/badge.svg)](https://github.com/Gene-Liu-portfolio/ctbc-payment-advisor/actions/workflows/ci.yml)

基於 **Claude × MCP** 架構的智慧刷卡建議服務。使用者可在 React Web Demo 中勾選持有卡片，輸入自然語言消費情境，系統會透過後端推薦邏輯與 MCP tools 推薦較適合的刷卡選擇。

本專案合作對象為中國信託；資料集中額外納入部分非中信信用卡作為跨銀行推薦邏輯與 benchmark 測試資料，並沒有與該銀行合作。

除了本專案的前端網頁，`/mcp` 也可作為獨立 MCP server 使用。由於 MCP 服務直接以後端形式部署在 Render，只要 MCP client 支援 remote MCP / Streamable HTTP，例如 Cursor 或其他可設定線上 MCP URL 的工具，就可以透過公開 `/mcp` endpoint 連接並使用本專案暴露的推薦工具與卡片資料資源。

> 資料版本：2026-05-19 | 架構版本：v8.1（Structured SSE + MCP Connector）

---

## Features

- **Web Demo 示範 LLM 調用 MCP tools**：使用自己的 Claude API key 啟動本地或私有 backend，可完整測試自然語言解析、推薦理由與 Agent chat。
- **真實 MCP 協定整合**：Agent mode 透過 Claude MCP Connector 呼叫 `/mcp`，不是把工具包成 function calling。
- **公開 remote MCP endpoint**：支援 remote MCP over Streamable HTTP 或 SSE 的 client，例如 Cursor，可直接連線使用。
- **雙模式推薦流程**：一般推薦模式使用 structured SSE；Agent mode 顯示 Claude 的 tool use 與 tool result。
- **後端可信計算**：通路解析、持卡驗證、回饋計算、排序與非現金回饋處理都由後端 deterministic runtime 控制。
- **可測試的工程流程**：`pytest` 覆蓋推薦邏輯與 MCP contract，Playwright 覆蓋本地 Web E2E。

---

## Why MCP

本專案採用 MCP 不是為了把工具呼叫換一種包裝，而是把「推薦邏輯、資料來源、限制條件」固定在可控的後端服務中。LLM 負責理解使用者問題與選擇工具；實際可查哪些卡、可用哪些通路、怎麼計算回饋，仍由 `/mcp` 與 deterministic tool runtime 控制。

這個設計有三個優勢：

- **推薦結果更可靠** — MCP 工具只從 `merged_cards.json`、通路對應表與後端計算邏輯取資料，降低 LLM 自行補卡片、補優惠或補回饋率的風險。
- **更容易接進銀行既有數位渠道** — `/mcp` 是標準工具介面，同一套能力未來可提供給 Claude API、內部客服工具、行動銀行、網銀或其他 MCP client，不需要為每個入口重寫 function schema。
- **核心規則留在 bank-owned backend** — 推薦排序、資料更新、優惠條件、fallback 規則都在後端維護；prompt 只負責引導 LLM 何時呼叫工具，不承擔資料真實性的責任。

`cards_owned` 由前端選卡狀態傳入後端，並寫入 chat system prompt 約束 Claude 工具呼叫時只能使用該 card_id 清單；deterministic REST/SSE 推薦流程則直接使用 request body 中的 `cards_owned`。使用者勾選的持卡清單是權限邊界：Claude 可以解讀需求、選擇工具，但推薦邏輯必須以使用者實際持有的 card_id 清單為準。這能降低推薦未持有卡的風險，並讓前端狀態、後端查詢與未來銀行登入 session 保持一致。

---

## Quick start

本專案有兩條使用路線：

- **路線一：使用 Web Demo 完整示範 LLM + MCP 流程**。適合想測試前端、Claude parse、推薦理由與 Agent chat 的使用者；需要自己的 `ANTHROPIC_API_KEY`，並啟動本地或私有 backend。
- **路線二：只使用公開 MCP tools**。適合在 Cursor 或其他 MCP client 中直接調用本專案的推薦、比較與卡片查詢工具；不需要本專案提供任何 LLM API key，client 端自己的模型負責對話與推理。

### 路線一：Web Demo 完整流程

需求：

- Python 3.10+
- uv
- Node.js 22 LTS recommended（目前前端依賴至少需要 Node 20+）
- npm
- Anthropic API key

啟動 backend：

```bash
git clone https://github.com/Gene-Liu-portfolio/ctbc-payment-advisor.git
cd ctbc-payment-advisor

uv sync
cp .env.example .env
# 在 .env 填入 ANTHROPIC_API_KEY
# 若要啟用一般推薦的 LLM parse / reason：
# ENABLE_SERVER_LLM=true
# 若要啟用 /api/chat Agent mode：
# ENABLE_AGENT_CHAT=true

uv run python -m mcp_server.http_app
```

另一個 Terminal 啟動前端，並指定使用本地 backend：

```bash
cd "Credit Card AI Payment Advisor"
npm ci
VITE_API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
```

開啟：

```text
http://localhost:5173/
```

使用流程：勾選持有卡片，點 Start，輸入像「去好市多採買 5000 元」或「在 momo 買家電 3000 元」這類消費情境。

### 路線二：只使用公開 MCP tools

如果你只是想在 Cursor 或其他支援 remote MCP 的工具中使用本專案的刷卡推薦工具，不需要 clone 專案，也不需要本專案的 `ANTHROPIC_API_KEY`。直接把 MCP client 指到公開 Render endpoint：

```text
https://ctbc-payment-advisor.onrender.com/mcp
```

Render 在這裡的角色是把本專案後端服務，例如卡片資料取得、通路查詢、優惠運算、推薦比較，包裝成可被 MCP client 呼叫的線上 MCP server。LLM 對話、推理與工具選擇由使用者自己的 MCP client / 模型環境負責；本服務回傳 deterministic tool result。

### 前端預設 proxy

`vite.config.ts` 預設會把 `/api` request proxy 到已部署的 Render backend：

```text
https://ctbc-payment-advisor.onrender.com
```

這個預設值保留是為了展示「前端可透過公開 backend / MCP 入口連線」。如果要完整測試 Web Demo 的 Claude-backed flows，請使用路線一的 `VITE_API_PROXY_TARGET=http://127.0.0.1:8000` 指向自己的本地或私有 backend。

---

## Using this MCP server from other clients

本專案的 Render backend 同時提供公開 remote MCP endpoint：

```text
https://ctbc-payment-advisor.onrender.com/mcp
```

任何支援 remote MCP over Streamable HTTP 或 SSE 的 MCP client 都可以直接連到這個 endpoint。以 Cursor 為例，可在 `~/.cursor/mcp.json` 或專案內 `.cursor/mcp.json` 加入：

```json
{
  "mcpServers": {
    "ctbc-payment-advisor": {
      "url": "https://ctbc-payment-advisor.onrender.com/mcp"
    }
  }
}
```

啟用後，client 可以呼叫本專案暴露的 MCP tools，例如 `search_by_channel`、`recommend_payment`、`compare_cards`、`get_promotions`、`get_card_details`、`list_all_cards`。

範例 prompt：

```text
使用 ctbc-payment-advisor 比較 LINE Pay信用卡、富邦momo聯名卡、富邦Costco聯名卡，在 momo 消費 3000 元哪張比較划算。
```

```text
使用 ctbc-payment-advisor MCP tools，推薦好市多消費 5000 元適合用哪張卡。
```

這個 endpoint 是公開工具介面，適合 demo 與整合測試。請不要透過 MCP 暴露 admin tool、secret、維運工具或客戶個資。

---

## 可用 MCP 工具

| Tool / Resource | 負責內容 |
|-----------------|----------|
| `search_by_channel` | 依通路、持有卡與金額搜尋較適合的卡片，回傳排序、條件與計算 trace。 |
| `recommend_payment` | 從自然語言消費情境解析通路與金額，再產生整體推薦。 |
| `compare_cards` | 比較多張持有卡在指定通路或全通路的回饋差異。 |
| `get_promotions` | 查詢目前有效活動與即將到期的優惠提醒。 |
| `get_card_details` | 查詢單張卡完整資料、通路回饋、限制條件與年費資訊。 |
| `list_all_cards` | 查詢目前可用的 `card_id` 與卡名。 |
| `card://ctbc/{card_id}` | MCP Resource，提供單張卡 JSON。 |
| `channels://ctbc/all` | MCP Resource，提供通路分類對照。 |

---

## 支援卡片（13 張）

- 中國信託：漢神聯名卡、uniopen聯名卡、遠東SOGO聯名卡、LINE Pay信用卡、中華航空聯名卡、中油聯名卡
- 富邦 benchmark：富邦J卡、富邦鑽保卡、富邦富利生活卡、富邦Costco聯名卡、富邦悍將勇士聯名卡、富邦momo聯名卡、台灣大哥大Open Possible聯名卡

---

## 架構簡介

```text
React Web Demo
├─ /api/recommend/stream  一般推薦模式，structured SSE
├─ /api/chat              Agent mode，Claude MCP Connector
└─ /api/*                 REST deterministic 查詢

Render backend
├─ Starlette + uvicorn    REST / SSE / MCP 共用 ASGI service
├─ FastMCP                /mcp Streamable HTTP
├─ mcp_server/tools/      推薦、比較、優惠、卡片查詢 tools
└─ data/processed/merged_cards.json
```

核心原則：

- LLM 負責理解使用者語意與選擇工具；推薦排序、持卡驗證、資料查詢與回饋計算留在後端。
- `cards_owned` 會在後端以 canonical card data 驗證，避免信任前端傳入的卡名。
- 非現金回饋，例如 LINE Points、OPENPOINT、哩程，不會被誤當成 NT$ 現金回饋估算。
- 卡片 runtime schema 定義在 `data/schemas/card_schema.json`；資料合併邏輯在 `scraper/merge.py`。

---

## 本地後端與測試

需要完整 Web Demo LLM flows、開發後端、跑 Python 測試、資料驗證，或不想使用 Render backend 時，才需要本地後端。

```bash
uv sync
cp .env.example .env
# Web Demo LLM flows 需要填入 ANTHROPIC_API_KEY
# ENABLE_SERVER_LLM=true
# ENABLE_AGENT_CHAT=true

uv run python -m mcp_server.http_app
```

另一個 Terminal 啟動前端並指定本地後端：

```bash
cd "Credit Card AI Payment Advisor"
VITE_API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
```

測試定位：

- `pytest`：測推薦邏輯、資料契約、MCP tool 結果、SSE contract 與 CI/E2E 設定契約。
- `Playwright`：模擬使用者操作網頁，驗證前端、卡片選擇、推薦卡片、thinking panel、Agent mock SSE 是否能正常渲染。
- Playwright 是本地 E2E 測試工具，不是資料驗證工具，也不是取代 `pytest`。

常用驗證指令：

```bash
uv run pytest tests/test_mcp_tools.py tests/test_recommend_stream_integration.py tests/test_chat_contract.py tests/test_project_automation_contracts.py -q
uv run python -m scraper.run validate

cd "Credit Card AI Payment Advisor"
npm ci
npm run build
npm run test:e2e
```

第一次在新機器跑 Playwright 時，如果提示瀏覽器不存在，再執行：

```bash
cd "Credit Card AI Payment Advisor"
npx playwright install chromium
```

---

## 安全邊界與限制

- `/mcp` 是公開 endpoint，目的是支援 Claude MCP Connector 與 remote MCP client。
- 公開 Render backend 不應設定 `ANTHROPIC_API_KEY`，也不應開啟 `ENABLE_SERVER_LLM=true` 或 `ENABLE_AGENT_CHAT=true`；避免公開服務消耗專案方 LLM quota。
- MCP 只暴露推薦、比較、優惠查詢、卡片查詢等 deterministic tool 能力；不暴露 reload data、admin tool 或內部維運工具。
- 正式環境應使用 `ALLOWED_ORIGINS` 限制前端來源。
- 使用者或其他 MCP client 呼叫工具時，請求會打到本專案 Render service；人數增加時需考慮 Render 資源、冷啟動與流量限制。
- 卡片資料為 demo / benchmark data，可能不是最新銀行優惠；實際回饋、活動、限制條件仍以銀行官方公告為準。
- 富邦卡為 benchmark 資料，不代表合作銀行資料。

---

## 常見問題

**Q: 一般使用者需要自己的 Anthropic API key 嗎？**

分使用情境：

- 使用 Cursor 或其他 remote MCP client 連到本專案公開 `/mcp` endpoint 時，不需要提供 `ANTHROPIC_API_KEY`。對話與推理由使用者自己的 MCP client / 模型環境負責，本服務只回傳 deterministic MCP tool 結果。
- 使用本專案 Web Demo 並想完整測試 Claude parse、推薦理由生成或 `/api/chat` Agent mode 時，需要使用者自己的 `ANTHROPIC_API_KEY`，並在本地或私有 backend 主動開啟 `ENABLE_SERVER_LLM=true` 或 `ENABLE_AGENT_CHAT=true`。

**Q: 為什麼要用 MCP，不直接 function calling？**

MCP 讓推薦工具成為可重用的標準介面。同一套 `/mcp` 可被 Web Demo、Claude MCP Connector、Cursor 或其他支援 remote MCP 的 client 使用；推薦規則與資料查詢仍留在 bank-owned backend。

**Q: 如果 `npm ci` 出現 Node engine warning 怎麼辦？**

請使用 Node.js 22 LTS。CI 也使用 Node 22。

**Q: 如果 Render backend 睡著了怎麼辦？**

第一次開啟可能需要等待 cold start。若前端短時間內沒有資料，稍等後重新整理。

**Q: 如何更新或驗證資料？**

資料 schema 在 `data/schemas/card_schema.json`，runtime data 在 `data/processed/merged_cards.json`。修改資料後請執行 `uv run python -m scraper.run validate`。

---

## Contributor

中信銀行實習專案小組：

| GitHub | 角色 |
|--------|------|
| [@Gene-Liu-portfolio](https://github.com/Gene-Liu-portfolio) | 實習生 |
| [@LarryinMexico](https://github.com/LarryinMexico) | 實習生 |
| [@Lyyyy17](https://github.com/Lyyyy17) | 實習生 |
| [@rockeywang404](https://github.com/rockeywang404) | 實習生 |
