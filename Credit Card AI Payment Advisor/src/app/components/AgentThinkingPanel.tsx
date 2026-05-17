import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  Wrench,
} from 'lucide-react';
import type { ChatErrorType } from '../api';

export type AgentEvent =
  | {
      kind: 'tool_use';
      id: string;
      tool_name: string;
      input: Record<string, unknown>;
    }
  | {
      kind: 'tool_result';
      tool_use_id: string;
      summary: string;
      is_error: boolean;
    }
  | {
      kind: 'error';
      type: ChatErrorType;
      message: string;
      status_code?: number;
    };

interface Props {
  events: AgentEvent[];
  isDone: boolean;
  elapsedSeconds?: number;
}

const ERROR_TITLES: Record<ChatErrorType, string> = {
  mcp_connection_failed: 'MCP 工具伺服器連線失敗',
  api_connection_failed: '無法連線至 Claude API',
  api_rate_limit: 'Claude API 流量限制（429）',
  api_invalid_request: 'Claude API 參數錯誤',
  api_error: 'Claude API 錯誤',
  unknown: '未知錯誤',
};

function formatInput(input: Record<string, unknown>): string {
  try {
    return JSON.stringify(input, null, 2);
  } catch {
    return String(input);
  }
}

function formatSummary(summary: string): string {
  // Try to pretty-print JSON; otherwise return as-is.
  const trimmed = summary.trim();
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch {
      return summary;
    }
  }
  return summary;
}

interface ToolBlockProps {
  toolUse: Extract<AgentEvent, { kind: 'tool_use' }>;
  result: Extract<AgentEvent, { kind: 'tool_result' }> | null;
}

function ToolBlock({ toolUse, result }: ToolBlockProps) {
  const [showResult, setShowResult] = useState(false);

  return (
    <div className="rounded-lg border bg-white/80" style={{ borderColor: '#007C7C22' }}>
      {/* Tool use row */}
      <div className="px-3 py-2 border-b" style={{ borderColor: '#007C7C11' }}>
        <div className="flex items-center gap-1.5 mb-1.5">
          <Wrench size={12} className="flex-shrink-0" style={{ color: '#007C7C' }} />
          <span className="text-[11px] font-medium" style={{ color: '#0F766E' }}>
            Claude 決定呼叫 MCP 工具
          </span>
        </div>
        <div className="text-xs font-mono" style={{ color: '#1F2937' }}>
          <span className="font-semibold" style={{ color: '#0F766E' }}>{toolUse.tool_name}</span>
          <span className="text-gray-500">(</span>
        </div>
        <pre
          className="text-[11px] font-mono mt-1 px-2 py-1.5 rounded overflow-x-auto"
          style={{ backgroundColor: '#F0FAFA', color: '#1F2937' }}
        >
          {formatInput(toolUse.input)}
        </pre>
        <div className="text-xs font-mono" style={{ color: '#9CA3AF' }}>)</div>
      </div>

      {/* Tool result row */}
      <div className="px-3 py-2">
        {result === null ? (
          <div className="flex items-center gap-1.5 text-[11px]" style={{ color: '#6B7280' }}>
            <Loader2 size={11} className="animate-spin flex-shrink-0" />
            <span>等待 MCP 工具回傳結果...</span>
          </div>
        ) : (
          <>
            <button
              type="button"
              onClick={() => setShowResult((v) => !v)}
              className="w-full flex items-center gap-1.5 text-[11px]"
              style={{ color: result.is_error ? '#DC2626' : '#0F766E' }}
            >
              {result.is_error ? (
                <AlertTriangle size={11} className="flex-shrink-0" />
              ) : (
                <CheckCircle2 size={11} className="flex-shrink-0" style={{ color: '#16A34A' }} />
              )}
              <span className="font-medium flex-1 text-left">
                {result.is_error ? 'MCP 回傳錯誤' : 'MCP 已回傳資料'}
              </span>
              {showResult ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            </button>
            {showResult && (
              <pre
                className="text-[11px] font-mono mt-1.5 px-2 py-1.5 rounded overflow-x-auto max-h-64 overflow-y-auto"
                style={{
                  backgroundColor: result.is_error ? '#FEF2F2' : '#F0FAFA',
                  color: '#1F2937',
                }}
              >
                {formatSummary(result.summary)}
              </pre>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function AgentThinkingPanel({ events, isDone, elapsedSeconds }: Props) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Auto-collapse 1.5s after done (slightly longer than hardcoded panel so user can glance)
  useEffect(() => {
    if (isDone) {
      const timer = setTimeout(() => setIsCollapsed(true), 1500);
      return () => clearTimeout(timer);
    }
  }, [isDone]);

  const toolUses = events.filter(
    (e): e is Extract<AgentEvent, { kind: 'tool_use' }> => e.kind === 'tool_use',
  );
  const toolResults = events.filter(
    (e): e is Extract<AgentEvent, { kind: 'tool_result' }> => e.kind === 'tool_result',
  );
  const errors = events.filter(
    (e): e is Extract<AgentEvent, { kind: 'error' }> => e.kind === 'error',
  );

  const resultById = new Map(toolResults.map((r) => [r.tool_use_id, r]));

  const headerLabel = isDone
    ? `Agent 思考完成（${elapsedSeconds ?? '—'}s，共呼叫 ${toolUses.length} 個 MCP 工具）`
    : `Agent 思考中... 已呼叫 ${toolUses.length} 個 MCP 工具`;

  return (
    <div
      className="rounded-xl border overflow-hidden mb-2"
      style={{ borderColor: '#007C7C33', backgroundColor: '#F0FAFA' }}
    >
      <button
        type="button"
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
        style={{ color: '#007C7C' }}
        onClick={() => setIsCollapsed((v) => !v)}
      >
        {isDone ? (
          <CheckCircle2 size={13} className="flex-shrink-0" />
        ) : (
          <Loader2 size={13} className="flex-shrink-0 animate-spin" />
        )}
        <span className="text-xs font-medium flex-1">{headerLabel}</span>
        {isCollapsed ? (
          <ChevronRight size={12} className="flex-shrink-0" />
        ) : (
          <ChevronDown size={12} className="flex-shrink-0" />
        )}
      </button>

      {!isCollapsed && (toolUses.length > 0 || errors.length > 0) && (
        <div className="px-3 pb-3 space-y-2">
          {toolUses.map((tu) => (
            <ToolBlock key={tu.id} toolUse={tu} result={resultById.get(tu.id) ?? null} />
          ))}

          {errors.map((err, i) => (
            <div
              key={`err-${i}`}
              className="rounded-lg border px-3 py-2"
              style={{ borderColor: '#FCA5A5', backgroundColor: '#FEF2F2' }}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle size={12} className="flex-shrink-0" style={{ color: '#DC2626' }} />
                <span className="text-[11px] font-medium" style={{ color: '#991B1B' }}>
                  {ERROR_TITLES[err.type]}
                  {err.status_code ? `（HTTP ${err.status_code}）` : ''}
                </span>
              </div>
              <p className="text-[11px] leading-relaxed" style={{ color: '#7F1D1D' }}>
                {err.message}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
