/**
 * api.ts
 * ------
 * 前端 API client：
 * - REST：列卡、推薦/比較/優惠/單卡詳情
 *   （/api/recommend 會用 Haiku 輔助解析情境與產生理由；失敗時後端 fallback 到 regex）
 * - SSE Chat：與 Claude 多輪對話，Claude 透過 MCP Connector 自動呼叫 /mcp 工具
 *
 * 所有路徑走 /api/*；Vite 預設 proxy 到 Render backend，
 * 可用 VITE_API_PROXY_TARGET=http://127.0.0.1:8000 切到本地 backend。
 */

export interface CardMenuItem {
  card_id: string;
  card_name: string;
  bank_id: 'ctbc' | 'fubon';
  tags: string[];
  card_org?: string | null;
  last_verified: string | null;
  data_source: string;
}

export interface SearchResult {
  rank?: number;
  card_id: string;
  card_name: string;
  cashback_rate: number | null;
  cashback_type: string;
  cashback_description: string;
  estimated_cashback: number | null;
  max_cashback_per_period: number | null;
  valid_end: string | null;
  expiring_soon: boolean;
  conditions: string;
  data_source: string;
  is_fallback: boolean;
  merchant?: string;
  payment_method?: string;
  reason?: string;
  detail_highlights?: string[];
  promotion_alerts?: string[];
}

/** Claude messages 格式（user/assistant），content 為純文字。 */
export interface ChatHistoryItem {
  role: 'user' | 'assistant';
  content: string;
}

export interface ToolUseEvent {
  id: string;
  tool_name: string;
  server_name: string;
  input: Record<string, unknown>;
}

export interface ToolResultEvent {
  tool_use_id: string;
  tool_name?: string;
  input?: Record<string, unknown>;
  is_error: boolean;
  summary: string;
  data?: {
    source_tool?: string;
    parsed?: unknown;
    recommendations?: Array<{
      channel_name?: string;
      channel_id?: string;
      best_options?: SearchResult[];
    }>;
  } | null;
}

/** 對應後端 _classify_error() 的分類；type 用於前端決定錯誤畫面。 */
export type ChatErrorType =
  | 'mcp_connection_failed'
  | 'api_connection_failed'
  | 'api_rate_limit'
  | 'api_invalid_request'
  | 'api_error'
  | 'unknown';

export interface ChatErrorEvent {
  type: ChatErrorType;
  message: string;
  raw_type?: string;
  status_code?: number;
}

export interface ChatStreamHandlers {
  onText?: (delta: string) => void;
  onToolUse?: (evt: ToolUseEvent) => void;
  onToolResult?: (evt: ToolResultEvent) => void;
  onDone?: (stopReason: string | null) => void;
  onError?: (evt: ChatErrorEvent) => void;
}

/** GET /api/cards */
export async function fetchCards(): Promise<CardMenuItem[]> {
  const res = await fetch('/api/cards');
  const data = await res.json();
  return data.cards ?? [];
}

/**
 * POST /api/chat — SSE 串流。
 *
 * 後端會以 `event: <type>\ndata: <json>\n\n` 格式吐：
 *   - text       → 文字增量
 *   - tool_use   → Claude 呼叫的 MCP 工具
 *   - tool_result→ 工具回傳摘要
 *   - done       → 結束（stop_reason）
 *   - error      → 錯誤
 */
export async function streamChat(
  message: string,
  cardsOwned: { card_id: string; card_name: string }[],
  history: ChatHistoryItem[],
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, cards_owned: cardsOwned, history }),
    signal,
  });

  if (!res.ok || !res.body) {
    handlers.onError?.({
      type: 'api_error',
      message: `HTTP ${res.status}`,
      status_code: res.status,
    });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE 框格：以雙換行分隔
    let idx;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      let eventName = 'message';
      let dataStr = '';
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        else if (line.startsWith('data:')) dataStr += line.slice(5).trim();
      }
      if (!dataStr) continue;

      try {
        const data = JSON.parse(dataStr);
        switch (eventName) {
          case 'text':
            handlers.onText?.(data.text ?? '');
            break;
          case 'tool_use':
            handlers.onToolUse?.(data as ToolUseEvent);
            break;
          case 'tool_result':
            handlers.onToolResult?.(data as ToolResultEvent);
            break;
          case 'done':
            handlers.onDone?.(data.stop_reason ?? null);
            break;
          case 'error':
            handlers.onError?.({
              type: (data.type as ChatErrorType) ?? 'unknown',
              message: data.message ?? '未知錯誤',
              raw_type: data.raw_type,
              status_code: data.status_code,
            });
            break;
        }
      } catch {
        // 忽略無法解析的事件
      }
    }
  }
}
