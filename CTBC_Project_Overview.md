# CTBC × Fubon Agent × MCP 支付建議服務 — 專案總覽

> 版本：v7.0 | 更新日期：2026-04-22 | 作者：政治大學 × 中信銀行實習生
> 截止驗收：2026-06-02

---

## 目錄

1. [專案概述](#1-專案概述)
2. [系統架構](#2-系統架構)
3. [整體系統流程](#3-整體系統流程)
4. [專案目錄結構](#4-專案目錄結構)
5. [各層說明 — 資料層（data/）](#5-各層說明--資料層data)
6. [各層說明 — MCP Server 層（mcp_server/）](#6-各層說明--mcp-server-層mcp_server)
7. [各層說明 — Agent 層（agent/）](#7-各層說明--agent-層agent)
8. [各層說明 — Gradio 前端（gradio_app.py）](#8-各層說明--gradio-前端gradio_apppy)
9. [MCP 工具完整說明](#9-mcp-工具完整說明)
10. [MCP 最優優惠選擇機制](#10-mcp-最優優惠選擇機制)
11. [資料集說明](#11-資料集說明)
12. [環境設定與啟動指南](#12-環境設定與啟動指南)
13. [各腳本用途速查表](#13-各腳本用途速查表)
14. [技術決策紀錄](#14-技術決策紀錄)
15. [已知限制與後續改善](#15-已知限制與後續改善)

---

## 1. 專案概述

### 1.1 目標

建立一個以 **Agent × MCP（Model Context Protocol）** 為核心的信用卡支付建議服務，讓使用者透過**自然語言**查詢，從自己持有的中信（CTBC）與富邦（Fubon）信用卡中獲得最佳刷卡建議。系統同時提供 **CLI 對話介面**（Agent）與 **Gradio 網頁 Demo**（視覺化展示）兩種使用方式。

### 1.2 核心功能

- **持卡選擇**：CLI 啟動時以選單勾選持有的信用卡；Gradio 介面提供勾選框
- **情境推薦**：輸入消費情境（如「去全聯買菜 1500 元」），自動推薦最優卡
- **海外消費辨識**：透過 Groq LLM + 關鍵字 fallback，自動偵測是否為海外消費，並查詢海外通路回饋率
- **回饋種類區分**：自動識別現金回饋、LINE Points、OPENPOINT、哩程、紅利點數等不同種類，動態調整顯示單位
- **偏好回饋篩選**：Gradio 介面支援使用者勾選偏好種類，結果依偏好優先排序
- **通路比較**：比較持有的多張卡在各消費通路的回饋差異
- **優惠查詢**：查看目前有效的優惠活動（含中信 19 筆 + 富邦 5 筆）與即將到期提醒
- **多輪對話**（CLI Agent）：記憶上下文，支援連續追問

### 1.3 三大產出

| 產出 | 說明 | 狀態 |
|------|------|------|
| 結構化資料集 | **13 張熱門信用卡**（中信 6 + 富邦 7）統一合併為 `merged_cards.json` | ✅ 完成 |
| MCP 支付建議服務模組 | FastMCP Server + **7 個工具函式** + 動態工具發現 | ✅ 完成 |
| CLI Agent | Groq API + 多輪對話 | ✅ 完成 |
| Gradio 前端 Demo | 視覺化勾選持卡 + 即時刷卡建議 + 海外消費辨識 | ✅ 完成 |

### 1.4 支援的信用卡（13 張）

**中信銀行（CTBC）6 張熱門卡：**

| card_id | 卡名 |
|---------|------|
| `ctbc_c_hanshin` | 漢神聯名卡 |
| `ctbc_c_uniopen` | uniopen聯名卡 |
| `ctbc_c_cs` | 遠東SOGO聯名卡 |
| `ctbc_c_linepay` | LINE Pay信用卡 |
| `ctbc_c_cal` | 中華航空聯名卡 |
| `ctbc_c_cpc` | 中油聯名卡 |

**台北富邦銀行（Fubon）7 張熱門卡：**

| card_id | 卡名 | 核心優勢 |
|---------|------|---------|
| `fubon_c_j` | 富邦J卡 | 日韓 JCB 特約商店長期 3%（Q1 活動加碼至 6%） |
| `fubon_c_j_travel` | 富邦J Travel卡 | 旅遊相關最高 6% |
| `fubon_c_costco` | 富邦Costco聯名卡 | Costco 網購 3%、門市 2% |
| `fubon_c_diamond` | 富邦鑽保卡 | 保費 0.5%、一般 0.7% |
| `fubon_c_momo` | 富邦momo卡 | momo購物最高 3% |
| `fubon_b_lifestyle` | 富邦富利生活卡 | 8大生活通路 5 倍紅利（約 2%） |
| `fubon_c_twm` | 台灣大哥大Open Possible聯名卡 | 台哥大消費 3.5% |

---

## 2. 系統架構

系統分為五大層：**使用者介面層**（CLI / Gradio）、**Agent 層**、**MCP Server 層**、**資料層**、**資料收集層**。

> ⚠️ **v7.0 重大架構變更**：
> - 資料層改為 **Build-time 合併**：三層資料（API 基礎 + card_features + microsite_deals）在 build time 合併為單一 `merged_cards.json`，MCP Server 不再 runtime 三層查詢
> - Agent 層改為**動態工具發現**：mcp_bridge.py 啟動時透過 MCP `tools/list` 動態發現 Server 工具，不再硬編碼 Tool Schema
> - Gradio 前端**完全解耦**：不再 import MCP Server 內部模組，自帶通路解析邏輯
> - `mcp_server/data/` 目錄已移除，統一由環境變數 `DATA_ROOT` 指向 `data/`
> - `channel_mapper.py` 複製一份至 `mcp_server/utils/`，消除 `sys.path.insert` hack

```
┌────────────────────────────────────────────────────────────────┐
│                      使用者介面層                               │
│                                                                │
│  [CLI] python main.py          [Gradio] python gradio_app.py  │
│   └─ 選卡 → 多輪對話              └─ 勾選卡 → 即時查詢         │
│                                    └─ 自帶通路解析（解耦）      │
└────────────┬───────────────────────────┬───────────────────────┘
             │                           │
             │ 自然語言                  │ HTTP POST /mcp
             ▼                           │ (Streamable HTTP)
┌────────────────────────┐               │
│      Agent 層          │               │
│     (agent/)           │               │
│                        │               │
│  payment_agent.py      │               │
│  ← Groq llama-3.3-70b │               │
│  prompts.py            │               │
│  mcp_bridge.py         │               │
│  ← 動態工具發現         │               │
│  ← HTTP 橋接層          │               │
└────────────┬───────────┘               │
             │ HTTP POST /mcp            │
             │ (Streamable HTTP)         │
             └──────────────┬────────────┘
                            ▼
┌────────────────────────────────────────────────────────────────┐
│          MCP Server 層（本地 / 部署於 Render — Streamable HTTP）│
│                                                                │
│  http_app.py           → ASGI 入口（uvicorn + Bearer Token）   │
│  search_by_channel()   → 依通路找最優持有卡（兩層：deals → channels）│
│  recommend_payment()   → 情境解析 + 推薦                       │
│  compare_cards()       → 多卡回饋比較（含 deals 查詢）          │
│  get_promotions()      → 優惠活動清單（中信 + 富邦）            │
│  get_card_details()    → 單卡完整資訊                          │
│  list_all_cards()      → 卡片選單（13 張）                     │
│  reload_data()         → 強制重載資料                          │
└────────────────────────────┬───────────────────────────────────┘
                             │ 讀取 merged_cards.json（Build-time 合併）
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                       資料層（data/）                            │
│                                                                │
│  processed/merged_cards.json  ← ★ 統一資料源（Build-time 合併） │
│    ├─ cards[].channels：card_features 覆蓋 API 基礎（已合併）  │
│    └─ cards[].deals：microsite 商家促銷（獨立陣列）             │
│                                                                │
│  processed/promotions.json  ← 24 項優惠（中信 19 + 富邦 5）    │
│  processed/channels.json    ← 通路分類對照表                   │
│                                                                │
│  [原始來源，供 merge.py 使用]                                   │
│  processed/ctbc_cards.json  ← 6 張中信卡（API 基礎）           │
│  processed/fubon_cards.json ← 7 張富邦卡（手動整理）           │
│  scraped/card_features.json ← 卡片特色頁回饋率                 │
│  scraped/microsite_deals.json ← LINE Pay 促銷                  │
│                                                                │
│  schemas/card_schema.json   ← JSON Schema（17 種 channel_id）  │
└────────────────────────────┬───────────────────────────────────┘
                             ▲ 更新資料 + merge
┌────────────────────────────────────────────────────────────────┐
│                    資料收集層（scraper/）                        │
│                                                                │
│  ctbc_scraper.py         ← CTBC 官方 JSON API（基礎）          │
│  card_feature_scraper.py ← 卡片特色頁直接爬取（6張中信卡）      │
│  data_cleaner.py         ← 清理、正規化、海外通路 override      │
│  channel_mapper.py       ← 通路名稱正規化對照表                │
│  microsite_scraper.py    ← 微型促銷網站爬取（選擇性）           │
│  merge.py                ← ★ Build-time 三層合併腳本            │
│                                                                │
│  ⚠️ 富邦卡資料為手動整理（無公開 API）                          │
└────────────────────────────────────────────────────────────────┘
```

### 2.1 資料查詢兩層優先序（Build-time 合併後）

> ⚠️ **v7.0 重大變更**：原本 runtime 三層查詢（microsite → card_features → 基礎）已改為 **Build-time 合併**。`scraper/merge.py` 在 build time 將三層資料合併進 `merged_cards.json`，MCP Server runtime 只需查兩層：

```
1. deals（原 microsite_deals，已合併進卡片的 deals 陣列）
   ├─ 若輸入為具體商家（如"蝦皮"）→ 優先比對 merchant 欄位，取商家專屬最高回饋
   └─ 輸入為通路類別（如"電商"）→ 取 channel 最高回饋（fallback）
        ↓ 若無
2. channels（card_features 已在 build time 覆蓋 API 基礎，同 channel_id 取高精確度來源）
   含中信 + 富邦所有卡；card_features 覆蓋僅影響中信 6 張卡
```

**Build-time 合併策略**（`scraper/merge.py`）：
- **Method A — Channel 合併**：card_features 中的 channel 資料覆蓋 API 基礎（同 channel_id 取 card_features 優先）
- **Method B — Deals 獨立陣列**：microsite_deals 保留為卡片的 `deals[]` 陣列，不與 channels 混合
- 過期的 deals 在 build time 即被過濾

### 2.2 通路分類（channel_id）

系統支援 **17 種**標準通路 ID：

| channel_id | 中文名稱 | 代表商家 |
|---|---|---|
| `convenience_store` | 超商 | 7-ELEVEN、全家、萊爾富、OK mart |
| `supermarket` | 超市／量販 | 全聯、家樂福 |
| `wholesale` | 量販/倉儲 | Costco 好市多 |
| `ecommerce` | 電商 | 蝦皮、momo、PChome、Yahoo |
| `food_delivery` | 外送 | foodpanda、Uber Eats |
| `transport` | 交通 | 台鐵、高鐵、捷運、Uber |
| `dining` | 餐飲 | 麥當勞、星巴克、路易莎 |
| `travel` | 旅遊 | 航空公司、Agoda、旅行社 |
| `entertainment` | 娛樂 | 威秀、Netflix、Spotify |
| `gas_station` | 加油站 | 中油、台塑石化 |
| `pharmacy` | 藥妝 | 屈臣氏、康是美 |
| `mobile_payment` | 行動支付 | LINE Pay、街口、Apple Pay |
| `department_store` | 百貨公司 | 遠東 SOGO、新光三越 |
| `insurance` | 保費 | 各大保險公司 |
| `telecom` | 電信費 | 台灣大哥大、中華電信 |
| `general` | 一般消費 | 其他國內消費 |
| `overseas_general` | **海外消費** | 國外實體商店消費 |

---

## 3. 整體系統流程

### 3.1 CLI Agent 流程（python main.py）

```
Step 1  ─── 啟動與選卡 ───────────────────────────────────────────
  使用者執行：python main.py
  main.py 呼叫 list_all_cards() → 顯示 13 張卡的 rich table
  使用者輸入編號選取持有的卡 → session_cards = ["ctbc_c_linepay", ...]
  PaymentAgent 初始化：model=llama-3.3-70b, cards_owned=session_cards

Step 2  ─── 使用者輸入問題 ─────────────────────────────────────────
  例："我今天要去全聯買菜，消費 2000 元，用哪張卡最划算？"

Step 3  ─── Agent 推理（Groq LLM） ───────────────────────────────
  payment_agent.chat(user_message)
    → 組合 System Prompt（含持卡清單）+ 對話歷史 + Tool Definitions
    → Tool Definitions 由 mcp_bridge.discover_tools() 動態發現
    → 送入 Groq API（llama-3.3-70b-versatile）
    → LLM 決定呼叫 Tool：search_by_channel(channel="全聯", amount=2000)

Step 4  ─── Tool 執行（mcp_bridge.py） ───────────────────────────
  execute_tool("search_by_channel", args, cards_owned=session_cards)
    → 自動注入 cards_owned（LLM 無法偽造）
    → 透過 HTTP 呼叫 MCP Server

Step 5  ─── 資料查詢（兩層優先序 + 商家層級比對） ─────────────────
  search_by_channel(channel="全聯", cards_owned=[...], amount=2000)
    → _resolve_channel("全聯") → "supermarket"
    → normalize_merchant("全聯") → 已知商家 → merchant_hint="全聯"
    → 對每張持有卡（從 merged_cards.json 載入）：
        1. get_best_deal_for_card(card, "supermarket", merchant_hint="全聯")
           ├─ 先找 deals[] 中 merchant 含"全聯"的 deal（商家層級精確比對）
           └─ 找不到 → fallback 到 channel 最高值
        2. get_best_channel_for_card(card, "supermarket")
           └─ 從 channels[]（已含 card_features 覆蓋）取最高回饋
    → 計算預估回饋：min(amount × rate, cap)
    → 依預估回饋排序，回傳 top_k 結果

Step 6  ─── LLM 整合結果 ──────────────────────────────────────────
  Tool 結果回傳給 LLM（history 中加入 tool_result）
  LLM 生成自然語言回覆，包含卡名、回饋率、預估金額

Step 7  ─── 多輪對話 ──────────────────────────────────────────────
  回覆存入 history，等待下一輪使用者輸入
  重複 Step 2-6（最多 MAX_TOOL_ROUNDS=5 輪 Tool Calling）
```

### 3.2 Gradio Demo 流程（python gradio_app.py）

```
Step 1  ─── 啟動 ────────────────────────────────────────────────
  使用者執行：python gradio_app.py
  _get_cards_menu_remote() 透過 HTTP 呼叫 MCP Server 的 list_all_cards()
  → 取得 13 張卡 → 建立 CheckboxGroup 選項

Step 2  ─── 使用者填表 ─────────────────────────────────────────
  ① 勾選持有的信用卡（中信 + 富邦，支援全選/清除）
  ② 勾選偏好回饋種類（現金/LINE Points/哩程/…）
  ③ 輸入消費金額（NT$）
  ④ 輸入消費情境（自然語言）
  → 按「查詢最優刷卡 →」

Step 3  ─── 海外消費辨識 ──────────────────────────────────────
  recommend() 呼叫 _detect_overseas(scenario)
    → 優先：關鍵字比對（日本、韓國、海外、出國…等 28 個詞）
    → fallback：Groq llama-3.1-8b-instant
        Prompt："這是海外消費嗎？只回答 yes 或 no"
        max_tokens=5, temperature=0（確定性輸出）
  若偵測為海外 → 在通路清單最前面插入 "overseas_general"

Step 4  ─── 情境解析與通路識別（自帶邏輯，不 import MCP Server）──
  _extract_channels(scenario) → 從情境抽取通路列表
    → regex 提取金額（若有）
    → _QUICK_CHANNEL_MAP（regex → display_name + channel_id）
  若無法識別 → fallback 到 "general"（一般消費）

Step 5  ─── 各通路查詢 ──────────────────────────────────────────
  對每個通路呼叫 _call_tool("search_by_channel", {...})（透過 HTTP 呼叫 MCP Server）
  → MCP Server 依兩層優先序查詢並計算回饋
  → SSE 格式回傳結果（mcp_bridge 強制 UTF-8 解碼後解析）

Step 6  ─── 格式化輸出 ──────────────────────────────────────────
  _format_single_channel(ch_display, results, amount, preferred_types)
    → _sort_results()：先依偏好種類，再依預估回饋降序排列
    → _reward_label()：識別回饋種類（現金/哩程/LINE Points/…）
    → _format_estimated()：依種類動態調整單位
    → _condition_note()：偵測踩點/任務/滿額等條件，加 ⚠️ 警語

Step 7  ─── 組合最終結果 ──────────────────────────────────────
  若海外消費 → 結果標頭加入警語
  所有通路的結果以 Markdown 格式呈現在 Gradio 頁面
```

---

## 4. 專案目錄結構

```
ctbc-payment-advisor/
│
├── main.py                        # ★ CLI 入口：持卡選單 + Agent 對話
├── gradio_app.py                  # ★ Gradio 前端 Demo（完全解耦，自帶通路解析）
│
├── data/
│   ├── processed/
│   │   ├── merged_cards.json      # ★ 統一資料源（Build-time 三層合併，v2.0）
│   │   ├── ctbc_cards.json        # 中信原始資料（6 張，供 merge.py 使用）
│   │   ├── fubon_cards.json       # 富邦原始資料（7 張，供 merge.py 使用）
│   │   ├── promotions.json        # 優惠活動（24 項：中信 19 + 富邦 5）
│   │   └── channels.json          # 通路分類對照表
│   ├── scraped/
│   │   ├── card_features.json     # 卡片特色頁爬取（6張中信熱門卡，供 merge.py）
│   │   └── microsite_deals.json   # 微型網站精確促銷（供 merge.py）
│   ├── seed/
│   │   └── ctbc_cards_seed.json   # 原始 seed 資料（備份用）
│   └── schemas/
│       └── card_schema.json       # JSON Schema（17 種 channel_id，支援 ctbc_ + fubon_）
│
├── scraper/
│   ├── __init__.py
│   ├── ctbc_scraper.py            # ★ 基礎資料收集（CTBC 官方 JSON API）
│   ├── card_feature_scraper.py    # ★ 卡片特色頁直接爬取（無需登入）
│   ├── data_cleaner.py            # 資料清理、海外 override、Schema 驗證
│   ├── channel_mapper.py          # 通路名稱正規化（17 種 channel_id）
│   ├── microsite_scraper.py       # 微型促銷網站爬取（選擇性）
│   ├── merge.py                   # ★ Build-time 三層資料合併腳本
│   └── run.py                     # CLI 子命令入口
│
├── cards_reference.md             # 13 張卡彙整說明 + 3 個使用者案例（含詳細算式）
├── system_architecture.drawio     # 系統架構圖（draw.io 格式，可匯入 app.diagrams.net）
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                  # ★ FastMCP Server（7 Tools + 2 Resources）
│   ├── http_app.py                # ★ HTTP 部署入口（uvicorn + Bearer Token 驗證）
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search.py              # Tool: search_by_channel（兩層：deals → channels）
│   │   ├── recommend.py           # Tool: recommend_payment + 情境解析
│   │   ├── compare.py             # Tool: compare_cards 全通路比較（含 deals 查詢）
│   │   └── promotions.py          # Tool: get_promotions + get_card_details
│   └── utils/
│       ├── __init__.py
│       ├── data_loader.py         # JSON 載入（lru_cache，讀取 merged_cards.json）
│       ├── calculator.py          # 回饋金額計算、到期判斷
│       └── channel_mapper.py      # ★ 通路名稱正規化（從 scraper/ 複製，消除 sys.path hack）
│
├── agent/
│   ├── __init__.py
│   ├── payment_agent.py           # ★ Agent 核心（Groq API + Tool Calling）
│   ├── mcp_bridge.py              # ★ 動態工具發現 + HTTP 橋接（自動注入 cards_owned）
│   └── prompts.py                 # 動態 System Prompt（注入持卡清單）
│
├── tests/
│   └── test_user_stories.py       # ★ User Story 端對端測試
│
├── .env.example                   # 環境變數範本
├── .env                           # 實際環境變數（勿進版控）
├── requirements.txt               # Python 依賴清單
└── mcp_config.json                # MCP Server 設定（目前清空，避免 Claude Desktop 讀取本地工具）
```

---

## 5. 各層說明 — 資料層（data/）

### 5.1 資料架構總覽

| 檔案 | 說明 | 來源 |
|------|------|------|
| `processed/merged_cards.json` | ★ **統一資料源**（13 張卡，含 channels + deals） | Build-time 合併（`scraper/merge.py`） |
| `processed/ctbc_cards.json` | 6 張中信卡原始資料（供 merge.py） | CTBC 官方 JSON API |
| `processed/fubon_cards.json` | 7 張富邦卡原始資料（供 merge.py） | 手動整理（無公開 API） |
| `processed/promotions.json` | 24 項優惠活動（中信 19 + 富邦 5） | CTBC API + 手動 |
| `processed/channels.json` | 通路分類對照表 | 手動建立 |
| `scraped/card_features.json` | 6 張中信熱門卡的精確回饋率（供 merge.py） | CTBC 卡片特色頁爬取 |
| `scraped/microsite_deals.json` | LINE Pay 精確促銷（供 merge.py） | CTBC 微型促銷頁爬取 |
| `schemas/card_schema.json` | 驗證格式，支援 `ctbc_` + `fubon_` 前綴，17 種 channel_id | 手動建立 |

### 5.2 Build-time 合併（`scraper/merge.py`）

合併流程：

```
[ctbc_cards.json]  ─┬─→ 基礎卡片清單（13 張）
[fubon_cards.json] ─┘
        │
        ▼  card_features 覆蓋
[card_features.json] → 比對 card_id + channel_id，以 card_features 回饋率優先覆蓋
        │
        ▼  deals 獨立插入
[microsite_deals.json] → 以 card_id 歸入各卡的 deals[] 陣列（過濾已過期）
        │
        ▼
merged_cards.json（version 2.0）
  ├─ cards[i].channels[]  ← 已合併（card_features 覆蓋 API 基礎）
  └─ cards[i].deals[]     ← microsite 促銷（獨立陣列）
```

### 5.3 技術突破（CTBC 資料收集）

原本計劃使用 Playwright 爬取 CTBC 官網 HTML，但遭遇 WAF（Imperva APP-1053）封鎖 headless browser，最終發現：

- **官方 JSON API**：`https://www.ctbcbank.com/web/content/twrbo/setting/creditcards.cardlist.json`（直接 requests 可存取）
- **iframe 直接存取**：卡片詳情頁的 `/web/content/` 路徑可繞過 WAF，用 BeautifulSoup 解析卡片特色

> ⚠️ CTBC CMS API 非官方公開文件，URL 或格式未來可能變動。
> ⚠️ 富邦銀行無公開 JSON API，fubon_cards.json 為手動整理，需定期人工更新。
> ⚠️ Python 3.13 對 CTBC 網站 SSL 驗證更嚴格（缺少 Subject Key Identifier），爬蟲需加 `verify=False`。

---

## 6. 各層說明 — MCP Server 層（mcp_server/）

### 6.1 啟動方式

```bash
# stdio 模式（本地開發 / Claude Desktop 整合）
python -m mcp_server.server

# 開發模式（帶 MCP Inspector UI）
mcp dev mcp_server/server.py

# HTTP 部署模式（本地測試 / Render 雲端 / 遠端存取）
python -m mcp_server.http_app
# 環境變數：MCP_AUTH_TOKEN=<token>（選填，啟用 Bearer Token 驗證）
#           HOST=0.0.0.0, PORT=8000（本地測試可改 8001 等）
```

### 6.2 `mcp_server/utils/data_loader.py`

資料載入層，使用 `@lru_cache` 避免重複 I/O，從 `merged_cards.json` 統一讀取：

| 函式 | 說明 |
|------|------|
| `get_all_cards()` | 回傳全部 **13 張卡**（從 merged_cards.json 讀取） |
| `get_card_by_id(card_id)` | 依 ID 取得單張卡（中信或富邦皆可） |
| `get_cards_by_ids(ids)` | 依 ID 列表取得多張卡 |
| `get_cards_menu()` | 精簡格式的卡片清單（供 CLI 選單與 Gradio） |
| `get_all_promotions(valid_only)` | 取得優惠活動（中信 + 富邦，可過濾已過期） |
| `get_best_channel_for_card(card, channel_id)` | 卡片 channels 中最優回饋（已含 card_features 覆蓋）；若無匹配退回 general 並標記 is_fallback |
| `get_deals_for_card(card, channel_id)` | 查詢卡片 deals 陣列中指定通路的所有促銷（過濾已過期） |
| `get_best_deal_for_card(card, channel_id, merchant_hint)` | deals 中最優促銷；有 merchant_hint 時優先比對商家 |
| `reload_all()` | 清除所有 lru_cache，強制重讀 |
| `get_data_summary()` | 回傳資料摘要：version, card_count=13, bank="CTBC + Fubon" |
| `get_channels_map()` | 回傳 channel_id → 通路資訊的完整對照表 |

**路徑解析**：優先使用環境變數 `DATA_ROOT`，否則預設為專案根目錄 `data/`。

### 6.3 `mcp_server/utils/calculator.py`

| 函式 | 說明 |
|------|------|
| `calc_estimated_cashback(amount, rate, cap)` | `min(amount × rate, cap)`，cap 為 None 時無上限 |
| `is_expiring_soon(valid_end, threshold=30)` | 30 天內到期回傳 True |
| `is_expired(valid_end)` | 已過期回傳 True |

### 6.4 `mcp_server/utils/channel_mapper.py`

從 `scraper/channel_mapper.py` 複製而來，提供通路名稱正規化功能，消除原本的 `sys.path.insert` hack。

| 函式 | 說明 |
|------|------|
| `get_channel_id(raw)` | 將使用者輸入（如 "711"、"全聯"）映射到 channel_id |
| `normalize_merchant(raw)` | 正規化商家名稱（如 "shopee" → "蝦皮"） |
| `MERCHANT_TO_CHANNEL` | 已知商家 → channel_id 的對照表 |

---

## 7. 各層說明 — Agent 層（agent/）

### 7.1 啟動

```bash
# 一般啟動（互動式持卡選擇）
python main.py

# 直接指定持有卡（跳過選單）
python main.py --cards ctbc_c_linepay fubon_c_j

# 列出所有可選卡片
python main.py --list-cards
```

### 7.2 `agent/payment_agent.py`

```python
class PaymentAgent:
    def chat(self, user_message: str) -> str:
        # 1. 加入對話記憶（user message）
        # 2. 送入 Groq（System Prompt + history + Tools Schema）
        #    Tools Schema 由 mcp_bridge.get_tool_definitions() 動態提供
        # 3. 若 LLM 發出 Tool Call → execute_tool（自動注入 cards_owned）
        # 4. Tool 結果加回 history → 重新送入 Groq
        # 5. 重複步驟 3-4，直到 LLM 無 Tool Call → 回傳最終回覆
```

**關鍵參數**：
- `MAX_TOOL_ROUNDS = 5`：防止無限 Tool-Calling loop
- `temperature = 0.3`：降低隨機性，確保推薦一致性
- Model：`GROQ_MODEL` 環境變數（預設 `llama-3.3-70b-versatile`）

### 7.3 `agent/mcp_bridge.py`

> ⚠️ **v7.0 重大變更**：從硬編碼 `TOOL_DEFINITIONS` 改為**動態工具發現**。

**動態工具發現流程**：

```
啟動時 → discover_tools()
  → 呼叫 MCP Server "tools/list"（JSON-RPC over Streamable HTTP）
  → 取得所有工具的 inputSchema
  → _mcp_schema_to_groq()：轉換為 Groq function calling 格式
  → 自動移除 cards_owned 參數（_HIDDEN_PARAMS）
  → 排除輔助工具（reload_data）
  → 快取結果（同一 process 只發現一次）
```

**核心函式**：

| 函式 | 說明 |
|------|------|
| `discover_tools()` | 從 MCP Server 動態發現工具，轉換為 Groq Schema（含快取） |
| `get_tool_definitions()` | 取得 Groq 格式的工具定義（呼叫 discover_tools） |
| `execute_tool(tool_name, arguments, cards_owned)` | 自動注入 cards_owned 後，透過 HTTP 呼叫遠端 MCP Tool |
| `_mcp_schema_to_groq(tool)` | MCP inputSchema → Groq function calling 格式轉換 |
| `_parse_sse_response(resp)` | SSE 回應解析（強制 UTF-8，避免中文截斷） |
| `_get_session_id()` | MCP session 初始化（同一 process 只初始化一次） |
| `_get_cards_menu_remote()` | 從遠端取得卡片選單 |

**SSE 解析注意事項**：`requests` 對 `text/event-stream` 預設用 ISO-8859-1 解碼，中文 UTF-8 字元的某些 byte（如 `0x85`）會被 `splitlines()` 誤判為換行符號，導致 JSON 截斷。修法為強制 `resp.content.decode('utf-8')` 並使用 `split('\n')` 而非 `splitlines()`。

**環境變數**：`MCP_SERVER_URL`（預設 `https://ctbc-payment-advisor.onrender.com/mcp`，本地測試可改為 `http://localhost:8001/mcp`）

### 7.4 `agent/prompts.py`

動態根據 session 選擇的卡片建立 System Prompt：列出所有持有卡名稱和 card_id，強制限制只能推薦持有的卡。

---

## 8. 各層說明 — Gradio 前端（gradio_app.py）

> ⚠️ **v7.0 重大變更**：Gradio 前端已**完全解耦**，不再 import MCP Server 內部模組。通路解析邏輯自帶於 gradio_app.py 內。

### 8.1 啟動

```bash
python gradio_app.py
# 自動開啟瀏覽器，port 自動選取
```

### 8.2 解耦設計

原本 Gradio 直接 import MCP Server 的 `_resolve_channel`、`_channel_display_name`、`_extract_channels` 等內部函式，造成 Server 與前端的耦合。

v7.0 改為 Gradio 自帶：
- `_CHANNEL_NAMES`：channel_id → 中文名稱對照表
- `_QUICK_CHANNEL_MAP`：regex → (display_name, channel_id) 的通路識別規則
- `_extract_channels()`：從情境文字中抽取通路列表，回傳 `list[tuple[str, str]]`（display_name, channel_id）
- `_channel_display_name()`：channel_id → 中文名稱

### 8.3 UI 結構

```
┌──────────────────────────────────────────────────────┐
│  💳 CTBC & 富邦信用卡支付建議                          │
│  中國信託銀行 × 台北富邦銀行熱門信用卡                   │
├────────────────────┬─────────────────────────────────┤
│ 左欄（scale=4）     │ 右欄（scale=6）                  │
│                    │                                 │
│ [全選] [清除]       │ ☑ 偏好回饋種類（可複選）          │
│                    │   ○ 現金回饋  ○ LINE Points      │
│ ✅ 選擇持有的信用卡 │   ○ OPENPOINT ○ 航空哩程         │
│  （中信 + 富邦）    │   ○ 中信紅利點數 ○ 其他點數      │
│   □ LINE Pay信用卡  │                                 │
│   □ 漢神聯名卡      │ 消費金額（NT$）[______]          │
│   □ 富邦J卡         │                                 │
│   □ 富邦momo卡      │ 消費情境 [____________]          │
│   □ ...            │                                 │
│                    │ [查詢最優刷卡 →]                 │
│                    │                                 │
│                    │ 推薦結果...                      │
└────────────────────┴─────────────────────────────────┘
```

### 8.4 海外消費辨識邏輯

```python
def _detect_overseas(scenario: str) -> bool:
    # 第一層：關鍵字快速比對（無需 API 呼叫）
    OVERSEAS_KW = ("日本", "韓國", "美國", "歐洲", "英國", "法國",
                   "德國", "泰國", "香港", "澳門", "新加坡", ...)
    if any(kw in scenario for kw in OVERSEAS_KW):
        return True

    # 第二層：Groq LLM 語意判斷
    resp = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",  # 二元分類任務，速度優先
        messages=[...只回答 yes 或 no...],
        max_tokens=5, temperature=0
    )
    return answer.startswith("yes")
```

---

## 9. MCP 工具完整說明

MCP Server 共提供 **7 個 Tools** 和 **2 個 Resources**：

> ⚠️ **v7.0 變更**：Agent 不再硬編碼 Tool Schema，而是透過 MCP `tools/list` 動態發現。`reload_data` 工具在動態發現時被排除，不暴露給 LLM。

### Tool 1：`search_by_channel` — 通路最優卡查詢

```python
search_by_channel(channel, cards_owned, amount=0, top_k=3)
```

**用途**：在持有卡中，找出在「某個消費通路」回饋最高的卡片排行。

**查詢流程（每張卡）**：
1. 先查 deals（microsite 商家促銷，已合併進卡片的 deals 陣列）— 最精確
2. 再查 channels（已在 build time 合併 card_features + API 基礎）— 通路層級

**輸入範例**：
- `channel="蝦皮"` → 解析為 `ecommerce`，並以 `merchant_hint="蝦皮"` 優先比對商家專屬 deal
- `channel="全聯"` → 自動解析為 `supermarket`，merchant_hint="全聯"
- `channel="711"` → 解析為 `convenience_store`
- `channel="overseas_general"` → 直接使用（短路保護，避免誤判）
- `channel="電商"` → 解析為 `ecommerce`，無具體商家故 merchant_hint=None

**輸出**：
```json
{
  "channel_id": "supermarket",
  "channel_name": "超市／量販",
  "merchant_hint": "全聯",
  "results": [
    {
      "rank": 1,
      "card_id": "ctbc_c_uniopen",
      "card_name": "uniopen聯名卡",
      "cashback_rate": 0.03,
      "estimated_cashback": 45.0,
      "data_source": "microsite",
      "is_fallback": false
    }
  ]
}
```

---

### Tool 2：`recommend_payment` — 情境推薦

```python
recommend_payment(scenario, cards_owned)
```

**用途**：輸入自然語言情境，自動解析通路 + 金額，對每個識別出的通路分別推薦最佳卡。

**情境解析流程**：
```
"去全聯買菜花了1500元，再用foodpanda點晚餐"
     ↓
金額抽取：_extract_amount() → 1500
通路識別：_extract_channels() → ["全聯", "foodpanda"]
     ↓
對每個通路呼叫 search_by_channel()
     ↓
回傳多通路推薦
```

**特性**：一次可解析多通路（如全聯 + foodpanda），分別推薦最優卡。

---

### Tool 3：`compare_cards` — 持有卡全通路比較

```python
compare_cards(cards_owned, channel="", amount=1000)
```

**用途**：比較持有的多張卡，在所有（或指定）通路的回饋差異。

> ⚠️ **v7.0 變更**：compare_cards 現在同時查詢 deals（microsite 促銷）和 channels，不再僅依賴 channels 資料。

- `channel=""` → 比較全部 12 種通路（不含 overseas_general）
- `channel="dining"` → 只比較餐飲通路
- `amount=1000` → 以 NT$1,000 計算預估回饋（方便比較）

**輸出格式**：每個通路顯示各卡的回饋率與預估金額，以及該通路的最優卡（`is_best: true`），並包含 `data_source` 欄位（"microsite" 或 "api"）。

---

### Tool 4：`get_promotions` — 優惠活動查詢

```python
get_promotions(cards_owned, category="")
```

**用途**：取得目前有效的優惠活動（含即將到期提醒），以及持有卡中即將到期的通路優惠。

**資料來源**：`promotions.json`（24 項：中信 19 + 富邦 5）

**注意**：優惠活動目前未與特定卡片綁定（中信活動為全行通用，富邦活動有 `applicable_cards` 欄位）。需至各銀行官網確認適用卡片。

---

### Tool 5：`get_card_details` — 單卡完整資訊

```python
get_card_details(card_id)
```

**用途**：取得指定卡片的完整資料，包含所有通路、回饋率、條件、年費等。

支援中信（`ctbc_` 前綴）和富邦（`fubon_` 前綴）兩種卡片。

---

### Tool 6：`list_all_cards` — 卡片清單

```python
list_all_cards()
```

**用途**：列出所有 13 張卡的 `card_id`、名稱、`bank_id`、標籤，供 CLI 選單和初始化使用。

---

### Tool 7：`reload_data` — 重載資料

```python
reload_data()
```

**用途**：清除 `lru_cache`，強制從磁碟重新讀取所有資料（更新資料後呼叫）。

> 此工具在動態發現時被排除（`_EXCLUDE_TOOLS`），不暴露給 LLM，僅供內部維護使用。

---

### Resources

| URI | 說明 |
|-----|------|
| `card://ctbc/{card_id}` | 單張卡片的完整 JSON |
| `channels://ctbc/all` | 通路分類對照表 JSON |

---

## 10. MCP 最優優惠選擇機制

這是整個系統最核心的邏輯，位於 `mcp_server/tools/search.py`。

### 10.1 商家層級比對（Merchant-Level Matching）

在進入資料查詢前，`search_by_channel` 會先判斷使用者輸入是否為**已知具體商家**：

```python
normalized = normalize_merchant(channel)           # "蝦皮" → "蝦皮"（標準名稱）
merchant_hint = normalized if normalized in MERCHANT_TO_CHANNEL else None
# "蝦皮" ∈ MERCHANT_TO_CHANNEL → hint = "蝦皮"
# "電商" ∉ MERCHANT_TO_CHANNEL → hint = None
```

有 `merchant_hint` 時，`get_best_deal_for_card()` 優先搜尋 `merchant` 欄位包含 hint 的 deal，確保「查蝦皮 → 回傳蝦皮 5%」而不是「回傳同 channel 最高值（如 OB嚴選 12%）」。

### 10.2 兩層資料優先序（Build-time 合併後）

```
┌─────────────────────────────────────────────────────┐
│ 層級 1：deals（原 microsite_deals，已合併進卡片）      │
│   來源：信用卡微型網站（如 ctbc_c_linepay 限時活動）  │
│   特色：最精確、有具體商家名稱和付款方式             │
│   限制：目前只有 ctbc_c_linepay 有 deals 資料        │
└──────────────────────┬──────────────────────────────┘
                       │ 找不到 ↓
┌─────────────────────────────────────────────────────┐
│ 層級 2：channels（card_features 已在 build time 覆蓋）│
│   來源：card_features 覆蓋 → API 基礎（同 channel_id）│
│   特色：覆蓋所有 13 張卡，card_features 精確度高      │
│   合併：同 card_id + channel_id 時取 card_features    │
│   限制：card_features 僅含中信卡，富邦依賴 API 基礎   │
└─────────────────────────────────────────────────────┘
```

### 10.3 通路 Fallback 機制

若卡片在指定通路（如 `food_delivery`）沒有資料，自動退回查詢 `general`（一般消費）的回饋，並在結果中標記 `is_fallback: true`，避免因無資料而漏掉該卡。

```
查詢 food_delivery
    ↓ 找不到
自動改查 general
    ↓
標記 is_fallback=True 回傳
```

### 10.4 排序決策邏輯

```python
def sort_key(r):
    est  = r.get("estimated_cashback") or 0.0   # 預估回饋金額（NT$）
    rate = r.get("cashback_rate") or 0.0         # 回饋率
    return (est, rate)  # 先比金額，同金額再比比率

results.sort(key=sort_key, reverse=True)
```

**為何先比金額再比比率？**

同一張卡在不同通路可能有回饋上限（`max_cashback_per_period`）。例如：
- 卡 A：回饋率 5%，上限 NT$100 → 消費 NT$5,000 只回饋 NT$100
- 卡 B：回饋率 3%，無上限 → 消費 NT$5,000 回饋 NT$150

若只比比率，錯選卡 A；比金額才能選出真正多回饋的卡 B。

當 `amount=0`（未輸入金額）時，預估金額皆為 None/0，退化為只比回饋率。

### 10.5 完整流程示意

```
使用者輸入：channel="全聯", cards_owned=["ctbc_c_uniopen", "fubon_b_lifestyle"], amount=2000

Step 1：通路解析
  "全聯" → _resolve_channel() → "supermarket"
  normalize_merchant("全聯") → merchant_hint="全聯"

Step 2：對每張卡查詢最優回饋（以 ctbc_c_uniopen 為例）
  ① get_best_deal_for_card(card, "supermarket", merchant_hint="全聯")
     └─ 搜尋 card.deals[] 中 channel_id="supermarket" 且 merchant 含 "全聯" 的 deal
     → 找到 / 找不到
  ② get_best_channel_for_card(card, "supermarket")
     └─ 從 card.channels[]（card_features 已覆蓋）取最高回饋
     → 找到 rate=0.03
  預估回饋：min(2000 × 0.03, cap) = NT$60

Step 3：對 fubon_b_lifestyle 查詢
  ① get_best_deal_for_card(card, "supermarket") → 無 deals
  ② get_best_channel_for_card(card, "supermarket")
     → 從 channels[] 找到 cashback_rate=0.02（5倍紅利等效）
  預估回饋：min(2000 × 0.02, cap) = NT$40

Step 4：排序
  ctbc_c_uniopen：NT$60 → rank 1
  fubon_b_lifestyle：NT$40 → rank 2

Step 5：回傳結果
  最優推薦：uniopen聯名卡（3%，預估回饋 NT$60）
```

---

## 11. 資料集說明

### 11.1 `data/processed/merged_cards.json`（★ 統一資料源）

**13 張**信用卡（中信 6 + 富邦 7），版本 v2.0，由 `scraper/merge.py` 在 build time 生成。

每張卡包含：
- `card_id`、`card_name`、`bank_id`、`card_org`、`card_status`、`tags` 等基本欄位
- `channels[]`：通路回饋陣列（card_features 已覆蓋 API 基礎）
- `deals[]`：microsite 促銷陣列（僅有資料的卡片才有內容）

LINE Pay 卡的結構範例：

```json
{
  "card_id": "ctbc_c_linepay",
  "card_name": "LINE Pay信用卡",
  "channels": [
    {
      "channel_id": "general",
      "cashback_type": "points",
      "cashback_rate": 0.01,
      "cashback_description": "一般消費累積 LINE POINTS 1%"
    },
    {
      "channel_id": "overseas_general",
      "cashback_type": "cash",
      "cashback_rate": 0.028
    }
  ],
  "deals": [
    {
      "channel_id": "ecommerce",
      "merchant": "蝦皮",
      "cashback_rate": 0.05,
      "benefit": "蝦皮購物LINE Pay付款享5%",
      "valid_end": "2026-06-30"
    }
  ]
}
```

### 11.2 `data/processed/promotions.json`

**24 項**優惠活動（中信 19 + 富邦 5）。

- 中信優惠：從官方 API 爬取，`bank_id: "ctbc"`，適用所有中信信用卡（通用活動）
- 富邦優惠：手動整理，`bank_id: "fubon"`，含 `applicable_cards` 欄位指定適用卡

### 11.3 `data/schemas/card_schema.json`

JSON Schema（draft-07），**支援中信 + 富邦兩種格式**：

- `card_id` pattern：`^(ctbc|fubon)_[a-z0-9_]+$`
- 新增 `bank_id` 欄位：`"ctbc"` / `"fubon"`
- 17 種 `channel_id`（原 13 種 + `wholesale`, `department_store`, `insurance`, `telecom`）

---

## 12. 環境設定與啟動指南

### 12.1 安裝

```bash
cd ctbc-payment-advisor
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 12.2 環境變數

```bash
cp .env.example .env
# 編輯 .env，填入：
GROQ_API_KEY=your_key_here        # 至 https://console.groq.com 免費取得
GROQ_MODEL=llama-3.3-70b-versatile
# MCP_SERVER_URL=http://localhost:8001/mcp  # 本地測試時使用
```

### 12.3 更新資料

```bash
# 更新中信基礎資料（6 張熱門卡 + 優惠活動）
python -m scraper.run full

# 更新中信卡片特色回饋率（無需登入）
python -m scraper.run card-feature --direct

# Build-time 合併（三層 → merged_cards.json）
python -m scraper.merge

# 驗證資料格式
python -m scraper.run validate
```

### 12.4 啟動方式

```bash
# ── 本地測試 ──────────────────────────────────────────

# 1. 啟動 MCP Server（本地 HTTP 模式）
python -m mcp_server.http_app   # 預設 port 8000，或設 PORT=8001

# 2. 啟動 Gradio 網頁 Demo
python gradio_app.py            # 預設 port 7860

# 3. CLI Agent 對話
python main.py

# ── 遠端部署（Render）──────────────────────────────────

# MCP Server HTTP 模式（Render 雲端）
python -m mcp_server.http_app

# MCP Server stdio 模式（本地開發 / Claude Desktop 整合）
python -m mcp_server.server
```

---

## 13. 各腳本用途速查表

| 檔案路徑 | 類型 | 核心用途 |
|---------|------|---------|
| `main.py` | CLI 入口 | 持卡選單（rich table）+ 啟動 Agent 多輪對話 |
| `gradio_app.py` | 前端 Demo | Gradio 網頁介面：自帶通路解析（解耦），中信+富邦勾選持卡 + 海外辨識 + 即時刷卡建議 |
| `scraper/ctbc_scraper.py` | 資料收集 | 呼叫 CTBC 官方 JSON API 取得基礎卡片與優惠資料 |
| `scraper/card_feature_scraper.py` | 資料收集 | 直接爬取卡片特色頁回饋率（iframe URL，無需登入） |
| `scraper/data_cleaner.py` | 資料處理 | 清理、正規化、海外通路 override、JSON Schema 驗證 |
| `scraper/channel_mapper.py` | 工具函式 | 通路名稱正規化，支援模糊輸入 → 17 種 channel_id |
| `scraper/microsite_scraper.py` | 資料收集 | 微型促銷網站爬取（ctbc_c_linepay 限時活動） |
| `scraper/merge.py` | **Build-time 合併** | 三層資料合併為 merged_cards.json（card_features 覆蓋 + deals 獨立陣列） |
| `mcp_server/server.py` | MCP Server | FastMCP 主程式（7 個 Tools + 2 個 Resources） |
| `mcp_server/http_app.py` | HTTP 部署 | ASGI 入口（uvicorn）+ Bearer Token 驗證 Middleware |
| `mcp_server/tools/search.py` | MCP Tool | `search_by_channel`：商家層級比對 + 兩層優先序（deals → channels） |
| `mcp_server/tools/recommend.py` | MCP Tool | `recommend_payment`：情境解析 + 多通路推薦 |
| `mcp_server/tools/compare.py` | MCP Tool | `compare_cards`：全通路回饋比較（含 deals 查詢） |
| `mcp_server/tools/promotions.py` | MCP Tool | `get_promotions`（中信+富邦）+ `get_card_details` |
| `mcp_server/utils/data_loader.py` | 工具函式 | JSON 載入（lru_cache，讀取 merged_cards.json） |
| `mcp_server/utils/calculator.py` | 工具函式 | 回饋金額計算、到期判斷 |
| `mcp_server/utils/channel_mapper.py` | 工具函式 | 通路名稱正規化（從 scraper/ 複製，消除 sys.path hack） |
| `agent/payment_agent.py` | Agent 核心 | Groq API + Tool Calling loop（llama-3.3-70b） |
| `agent/mcp_bridge.py` | 橋接層 | **動態工具發現** + HTTP 橋接（自動注入 cards_owned，SSE 解析強制 UTF-8）|
| `agent/prompts.py` | 提示工程 | 動態 System Prompt（注入持卡清單） |
| `data/processed/merged_cards.json` | **統一資料源** | 13 張卡（Build-time 合併，含 channels + deals） |
| `data/processed/ctbc_cards.json` | 原始資料 | 6 張中信卡（供 merge.py） |
| `data/processed/fubon_cards.json` | 原始資料 | 7 張富邦卡（手動整理，供 merge.py） |
| `data/processed/promotions.json` | 資料集 | 24 項優惠活動（中信 19 + 富邦 5） |
| `data/scraped/card_features.json` | 原始資料 | 6 張中信卡的特色頁回饋率（供 merge.py） |
| `data/scraped/microsite_deals.json` | 原始資料 | LINE Pay 精確促銷（供 merge.py） |
| `data/schemas/card_schema.json` | Schema | JSON Schema（17 種 channel_id，支援 ctbc_ + fubon_） |
| `cards_reference.md` | 參考文件 | 13 張卡優惠彙整 + 3 個使用者案例（含詳細回饋算式） |
| `system_architecture.drawio` | 架構圖 | 系統架構圖（draw.io 格式） |

---

## 14. 技術決策紀錄

| 決策 | 選項 | 結果 | 原因 |
|------|------|------|------|
| 基礎資料收集 | Playwright 爬蟲 vs. API 攔截 | **API 攔截（requests）** | CTBC 為 SPA，攔截 XHR 發現官方 JSON API，直接呼叫更穩定 |
| 卡片特色資料 | IB 登入爬取 vs. iframe 直接存取 | **iframe 直接存取** | `/web/content/` 路徑繞過 WAF，無需登入 |
| 卡片範圍 | 全 47 張中信 vs. 熱門 13 張 | **熱門 13 張（中信 6 + 富邦 7）** | 精簡資料集提升推薦品質，避免雜訊；加入富邦擴大適用場景 |
| 中信 6 張選擇 | 原 6 張 vs. 官網熱門推薦 | **官網熱門推薦 6 張**（漢神、uniopen、SOGO、LINE Pay、中華航空、中油） | 與官網熱門推薦頁一致，更具代表性 |
| 富邦資料取得 | 爬取 HTML vs. 手動整理 | **手動整理** | 富邦無公開 JSON API，HTML 結構複雜，手動整理品質更可靠 |
| LLM 服務 | OpenAI / Anthropic / Groq | **Groq API（免費額度）** | 免費額度足夠 demo，LPU 推理速度快，支援 Function Calling |
| 海外辨識策略 | 純關鍵字 vs. 純 LLM vs. 混合 | **混合（關鍵字優先，LLM fallback）** | 關鍵字無需 API 呼叫速度快；LLM 處理未知情境 |
| 最優卡排序依據 | 只比回饋率 vs. 先比預估金額 | **先比預估金額，再比比率** | 有上限的卡在高消費金額時實際回饋可能低於低比率無上限的卡 |
| 資料合併時機 | Runtime 三層查詢 vs. Build-time 合併 | **Build-time 合併** | 減少 runtime 複雜度，查詢從三層簡化為兩層；`scraper/merge.py` 負責合併 |
| Tool Schema 管理 | 硬編碼 vs. 動態發現 | **MCP tools/list 動態發現** | Server 新增/修改 Tool 時，Agent 自動同步，無需手動維護雙份 Schema |
| Gradio 耦合 | import MCP 內部模組 vs. 自帶邏輯 | **完全解耦（自帶通路解析）** | 前端與 Server 獨立部署，避免 import 路徑問題 |
| 資料路徑 | 多路徑 fallback vs. 環境變數 | **環境變數 DATA_ROOT** | 統一路徑管理，消除 `mcp_server/data/` 重複目錄 |
| Tool 執行方式 | 直接 Python 呼叫 vs. HTTP（Streamable HTTP） | **HTTP 遠端呼叫** | MCP 標準協定，Client 與 Server 可獨立部署和更新 |
| cards_owned 注入 | LLM 控制 vs. Agent 強制注入 | **Agent 強制注入** | 確保 LLM 無法推薦未持有的卡；不放入 Tool Schema |
| valid_only 參數 | 放入 Schema vs. 移除 | **移除** | LLM 會傳入字串 `"false"` 而非布林，導致 Groq API 驗證失敗 |
| 前端框架 | CLI only vs. Gradio | **CLI + Gradio 並存** | Gradio 對 AI Demo 最友善；CLI 保留 MCP 完整展示 |
| 資料儲存 | SQLite vs. JSON files | **JSON files** | 開發期資料量小（13 張卡），JSON 最簡單且便於 debug |
| channel_mapper 位置 | sys.path hack vs. 複製到 mcp_server/utils/ | **複製一份** | 消除 `sys.path.insert` hack，保持 package 邊界乾淨 |

---

## 15. 已知限制與後續改善

### 15.1 資料品質

- **富邦卡資料為手動整理**：無爬取機制，需定期人工更新；回饋率為截至 2026-03-16 的資料
- **富邦卡無 card_features 層資料**：card_features.json 只含中信卡，富邦卡在 merged_cards.json 中的 channels 為 API 基礎
- **overseas_general 資料完整性**：部分卡片的海外回饋描述不完整，cashback_rate 可能為 null
- **API 不穩定**：CTBC CMS API 非官方公開文件，URL 或格式可能隨時變動
- **Python 3.13 SSL 嚴格性**：CTBC 網站 SSL 憑證缺少 Subject Key Identifier，爬蟲需 `verify=False`

### 15.2 功能限制

- **promotions 未完整關聯卡片**：中信優惠活動為全行通用，無法自動判斷哪張卡適用
- **富邦促銷資料有限**：富邦 5 筆優惠為常設優惠，無限時活動爬取機制
- **情境解析靠 regex**：`recommend_payment` 遇到複雜情境可能誤判通路
- **海外辨識局限**：若使用者說「我在日本刷 foodpanda」，目前只顯示海外通路，不會同時查外送通路
- **merchant_hint 覆蓋率**：只有 `MERCHANT_TO_CHANNEL` 中的已知商家才會觸發商家層級比對，新商家需手動加入對照表
- **channel_mapper 雙份維護**：`scraper/channel_mapper.py` 和 `mcp_server/utils/channel_mapper.py` 需手動保持同步

### 15.3 後續改善方向

- [ ] 建立富邦卡的爬取機制（目前完全手動）
- [ ] 為富邦卡補充 card_features 層資料
- [ ] 海外消費支援複合通路（海外 + 特定通路並行查詢）
- [ ] 優惠活動加入卡片關聯欄位（`applicable_cards`）
- [ ] 擴充至更多銀行（玉山、國泰世華等）
- [ ] 擴充 `MERCHANT_TO_CHANNEL` 對照表（OB嚴選、Pinkoi 等電商商家尚未收錄）
- [ ] LLM 情境理解強化（以 LLM 補充 regex 情境解析的不足）
- [x] ~~microsite 只比 channel 不比 merchant~~ → 已實作 merchant-level matching（2026-03-23）
- [x] ~~Runtime 三層查詢~~ → 已改為 Build-time 合併（2026-04-21）
- [x] ~~硬編碼 Tool Schema~~ → 已改為 MCP 動態工具發現（2026-04-21）
- [x] ~~Gradio import MCP 內部模組~~ → 已完全解耦（2026-04-21）
- [x] ~~mcp_server/data/ 資料重複~~ → 已移除，統一用 DATA_ROOT 環境變數（2026-04-21）
- [x] ~~compare_cards 未查詢 deals~~ → 已加入 deals 查詢（2026-04-21）
- [x] ~~sys.path.insert hack~~ → channel_mapper 已複製至 mcp_server/utils/（2026-04-21）

---

*此文件記錄截至 2026-04-22 的實作狀態。由 Claude Code 協助生成與維護。*
