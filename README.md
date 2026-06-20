# 中國信託 Agent x MCP 支付建議服務模組設計與實作

[![CI](https://github.com/Gene-Liu-portfolio/ctbc-payment-advisor/actions/workflows/ci.yml/badge.svg)](https://github.com/Gene-Liu-portfolio/ctbc-payment-advisor/actions/workflows/ci.yml)

基於 **Claude × MCP** 架構的智慧刷卡建議服務。使用者可在 React Web Demo 中勾選持有卡片，輸入自然語言消費情境，系統會透過後端推薦邏輯與 MCP tools 推薦較適合的刷卡選擇。

本專案合作對象為中國信託；資料集中額外納入部分非中信信用卡作為跨銀行推薦邏輯與 benchmark 測試資料，並沒有與該銀行合作。

除了本專案的前端網頁，`/mcp` 也可作為獨立 MCP server 使用。由於 MCP 服務直接以後端形式部署在 Render，只要 MCP client 支援 remote MCP / Streamable HTTP，例如 Cursor 或其他可設定線上 MCP URL 的工具，就可以透過公開 `/mcp` endpoint 連接並使用本專案暴露的推薦工具與卡片資料資源。

> Runtime 資料版本以 `data/processed/merged_cards.json` 的 `last_updated` 為準；目前 committed data 為 2026-06-08 | 架構版本：v8.1（Structured SSE + MCP Connector）

---

## Features

- **Web Demo 可直接試用**：只需啟動前端，預設連到已部署的 Render 服務。
- **真實 MCP 協定整合**：Agent mode 透過 Claude MCP Connector 呼叫 `/mcp`，不是把工具包成 function calling。
- **公開 remote MCP endpoint**：支援 remote MCP over Streamable HTTP 或 SSE 的 client，例如 Cursor，可直接連線使用。
- **雙模式推薦流程**：一般推薦模式使用 structured SSE；Agent mode 可顯示 Claude 的 tool use 與 tool result。
- **後端可信計算**：通路解析、持卡驗證、回饋計算、排序與非現金回饋處理都由後端 deterministic runtime 控制。
- **可測試的工程流程**：`pytest` 覆蓋推薦邏輯與 MCP contract，Playwright 覆蓋本地 Web E2E。

---

## Why MCP

本專案採用 MCP 不是為了把工具呼叫換一種包裝，而是把「推薦邏輯、資料來源、限制條件」固定在可控的後端服務中。LLM 負責理解使用者問題與選擇工具；實際可查哪些卡、可用哪些通路、怎麼計算回饋，仍由 `/mcp` 與 deterministic tool runtime 控制。

這個設計有三個優勢：

- **推薦結果更可靠**：MCP 工具只從 `merged_cards.json`、通路對應表與後端計算邏輯取資料，降低 LLM 自行補卡片、補優惠或補回饋率的風險。
- **更容易接進銀行既有數位渠道**：`/mcp` 是標準工具介面，同一套能力未來可提供給 Claude API、內部客服工具、行動銀行、網銀或其他 MCP client，不需要為每個入口重寫 function schema。
- **核心規則留在 bank-owned runtime**：推薦排序、資料更新、優惠條件、fallback 規則都在受控服務中維護；prompt 只負責引導 LLM 何時呼叫工具，不承擔資料真實性的責任。

`cards_owned` 由前端選卡狀態傳入後端，並寫入 chat system prompt 約束 Claude 工具呼叫時只能使用該 card_id 清單；deterministic REST/SSE 推薦流程則直接使用 request body 中的 `cards_owned`。使用者勾選的持卡清單是權限邊界：Claude 可以解讀需求、選擇工具，但推薦邏輯必須以使用者實際持有的 card_id 清單為準。這能降低推薦未持有卡的風險，並讓前端狀態、後端查詢與未來銀行登入 session 保持一致。

---

## Quick start

本專案有兩條使用路線：

- **1. Web Demo**：下載專案後只啟動前端，前端會連到已部署的 Render 服務；公開 Render 不提供專案方 LLM API key。
- **2. MCP client**：在 Cursor 或其他支援 remote MCP 的工具中設定 Render `/mcp` URL。

### 1. Web Demo

需求：

- Node.js 22 LTS recommended（至少需要 Node 20+）
- npm

啟動：

```bash
git clone https://github.com/Gene-Liu-portfolio/ctbc-payment-advisor.git
cd ctbc-payment-advisor

cd "Credit Card AI Payment Advisor"
npm ci
npm run dev
```

開啟：

```text
http://localhost:5173/
```

使用流程：勾選持有卡片，點 Start，輸入像「去好市多採買 5000 元」或「在 momo 買家電 3000 元」這類消費情境。

前端預設會把 `/api` request proxy 到已部署的 Render 服務：

```text
https://ctbc-payment-advisor.onrender.com
```

公開 Render 服務不放置專案方 LLM API key。Web Demo 可展示後端推薦工具與基本流程；若要完整測試 LLM parse、自然語言回答或 Agent mode，需要使用者自己的 Anthropic API key 與自行管理的執行環境。

### 2. 在 Cursor 或其他 MCP client 使用

如果只想使用本專案的 MCP tools，不需要 clone 專案，也不需要啟動 Web Demo。直接在支援 remote MCP / Streamable HTTP 的 client 設定：

```text
https://ctbc-payment-advisor.onrender.com/mcp
```

Cursor `mcp.json` 範例：

```json
{
  "mcpServers": {
    "ctbc-payment-advisor": {
      "url": "https://ctbc-payment-advisor.onrender.com/mcp"
    }
  }
}
```

設定完成後，client 可以呼叫本專案暴露的 MCP tools，例如 `search_by_channel`、`recommend_payment`、`compare_cards`、`get_promotions`、`get_card_details`、`list_all_cards`。

範例 prompt：

```text
使用 ctbc-payment-advisor 比較 LINE Pay信用卡、富邦momo聯名卡、富邦Costco聯名卡，在 momo 消費 3000 元哪張比較划算。
```

```text
使用 ctbc-payment-advisor MCP tools，推薦好市多消費 5000 元適合用哪張卡。
```

這個 endpoint 是公開工具介面，適合 demo 與整合測試。請不要透過 MCP 暴露 admin tool、secret、維運工具或客戶個資。

---

## MCP tools


| Tool / Resource         | 負責內容                                                           |
| ----------------------- | ------------------------------------------------------------------ |
| `search_by_channel`     | 依通路、持有卡與金額搜尋較適合的卡片，回傳排序、條件與計算 trace。 |
| `recommend_payment`     | 從自然語言消費情境解析通路與金額，再產生整體推薦。                 |
| `compare_cards`         | 比較多張持有卡在指定通路或全通路的回饋差異。                       |
| `get_promotions`        | 查詢目前有效活動與即將到期的優惠提醒。                             |
| `get_card_details`      | 查詢單張卡完整資料、通路回饋、限制條件與年費資訊。                 |
| `list_all_cards`        | 查詢目前可用的`card_id` 與卡名。                                   |
| `card://ctbc/{card_id}` | MCP Resource，提供單張卡 JSON。                                    |
| `channels://ctbc/all`   | MCP Resource，提供通路分類對照。                                   |

---

## Support cards

- 中國信託：漢神聯名卡、uniopen聯名卡、遠東SOGO聯名卡、LINE Pay信用卡、中華航空聯名卡、中油聯名卡
- 富邦 (benchmark)：富邦J卡、富邦鑽保卡、富邦富利生活卡、富邦Costco聯名卡、富邦悍將勇士聯名卡、富邦momo聯名卡、台灣大哥大Open Possible聯名卡

---

## Architecture

```text
React Web Demo
├─ /api/recommend/stream  一般推薦模式，structured SSE
├─ /api/chat              Agent mode，Claude MCP Connector
└─ /api/*                 REST deterministic 查詢

Render service
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

## Development verification

以下只給開發者在修改程式或驗證 PR 時使用，一般使用者不需要執行。

- `pytest`：驗證推薦邏輯、資料契約、MCP tool 結果與 SSE contract。
- `Playwright`：本地 E2E，模擬使用者操作網頁並驗證 thinking panel / Agent mock SSE 渲染。

```bash
uv sync
uv run pytest tests/test_mcp_tools.py tests/test_recommend_stream_integration.py tests/test_chat_contract.py tests/test_project_automation_contracts.py -q
uv run python -m scraper.run validate

cd "Credit Card AI Payment Advisor"
npm ci
npm run build
npm run test:e2e
```

第一次在新機器跑 Playwright 時，如果提示瀏覽器不存在：

```bash
cd "Credit Card AI Payment Advisor"
npx playwright install chromium
```

---

## Security Notes and Known Limitations

- `/mcp` 是公開 endpoint，目的是支援 Claude MCP Connector 與 remote MCP client。
- 公開 Render 服務只暴露推薦、比較、優惠查詢、卡片查詢等 deterministic tool 能力；不暴露 reload data、admin tool、內部維運工具或專案方 LLM quota。
- 正式環境應使用 `ALLOWED_ORIGINS` 限制前端來源。
- 使用者或其他 MCP client 呼叫工具時，請求會打到本專案 Render service；人數增加時需考慮 Render 資源、冷啟動與流量限制。
- 卡片資料為 demo / benchmark data，可能不是最新銀行優惠；實際回饋、活動、限制條件仍以銀行官方公告為準。
- 富邦卡為 benchmark 資料，不代表合作銀行資料。

---

## FAQ

**Q: 一般使用者需要自己的 Anthropic API key 嗎？**

分使用情境：

- 使用 Web Demo 測完整 LLM parse、自然語言回答或 Agent mode 時，需要使用者自己的 Anthropic API key。
- Cursor 或其他 MCP client 只需要設定 `/mcp` URL，不需要本專案提供 API key。對話與推理由使用者自己的 agent / client 負責，本服務只提供卡片資料、推薦、比較與優惠查詢工具。

**Q: 為什麼要用 MCP，不直接 function calling？**

MCP 讓推薦工具成為可重用的標準介面。同一套 `/mcp` 可被 Web Demo、Claude MCP Connector、Cursor 或其他支援 remote MCP 的 client 使用；推薦規則與資料查詢仍留在 bank-owned runtime。

**Q: 如果 `npm ci` 出現 Node engine warning 怎麼辦？**

請使用 Node.js 22 LTS。CI 也使用 Node 22。

**Q: 如果 Render 服務睡著了怎麼辦？**

第一次開啟可能需要等待 cold start。若前端短時間內沒有資料，稍等後重新整理。

**Q: 如何更新或驗證資料？**

資料 schema 在 `data/schemas/card_schema.json`，runtime data 在 `data/processed/merged_cards.json`。修改資料後請執行 `uv run python -m scraper.run validate`。

---

## Contributor

中信銀行實習專案小組：


| GitHub                                                       | 角色   |
| ------------------------------------------------------------ | ------ |
| [@Gene-Liu-portfolio](https://github.com/Gene-Liu-portfolio) | 實習生 |
| [@LarryinMexico](https://github.com/LarryinMexico)           | 實習生 |
| [@Lyyyy17](https://github.com/Lyyyy17)                       | 實習生 |
| [@rockeywang404](https://github.com/rockeywang404)           | 實習生 |
