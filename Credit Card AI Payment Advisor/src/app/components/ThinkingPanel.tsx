import { useState, useEffect } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, Loader2, CheckCircle2, Wrench } from 'lucide-react';

export interface CalculationCandidate {
  card_name: string;
  formula: string;
  estimated_cashback: number | null;
}

export interface ToolResultTrace {
  tool: string;
  channel?: string | null;
  status: 'success' | 'error';
  summary: string;
  data: Record<string, unknown>;
}

export interface ThinkingStep {
  tool: string;
  status: 'calling' | 'done';
  label: string;
  kind?: 'step' | 'calculation' | 'tool_result';
  channel?: string;
  candidates?: CalculationCandidate[];
  winner?: CalculationCandidate | null;
  rankingSummary?: string;
  toolResult?: ToolResultTrace;
}

interface ThinkingPanelProps {
  steps: ThinkingStep[];
  isDone: boolean;
  elapsedSeconds?: number;
}

const TOOL_LABELS: Record<string, string> = {
  parse_scenario:    '情境解析',
  search_by_channel: '通路查詢',
  get_card_details:  '卡片詳情',
  get_promotions:    '優惠活動',
  generate_reasons:  '理由生成',
  mcp_calculation:   'MCP 完成計算',
};

const MCP_TOOL_NAMES = new Set([
  'search_by_channel',
  'recommend_payment',
  'compare_cards',
  'get_promotions',
  'get_card_details',
  'list_all_cards',
  'reload_data',
]);

function formatJson(data: Record<string, unknown>): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function ToolResultBlock({ result }: { result: ToolResultTrace }) {
  const [isOpen, setIsOpen] = useState(false);
  const isError = result.status === 'error';

  return (
    <div className="mt-1 rounded-md border bg-white" style={{ borderColor: isError ? '#FCA5A5' : '#007C7C1f' }}>
      <button
        type="button"
        className="w-full flex items-center gap-1.5 px-2 py-1.5 text-left"
        onClick={() => setIsOpen((v) => !v)}
      >
        {isError ? (
          <AlertTriangle size={11} className="flex-shrink-0" style={{ color: '#DC2626' }} />
        ) : (
          <CheckCircle2 size={11} className="flex-shrink-0" style={{ color: '#22c55e' }} />
        )}
        <span className="text-[11px] font-medium flex-1" style={{ color: isError ? '#991B1B' : '#0F766E' }}>
          MCP 工具回傳：{result.tool}
          {result.channel ? ` / ${result.channel}` : ''}
        </span>
        {isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
      </button>
      <div className="px-2 pb-1.5 text-[11px] leading-relaxed" style={{ color: '#4B5563' }}>
        {result.summary}
      </div>
      {isOpen && (
        <pre
          className="mx-2 mb-2 max-h-72 overflow-auto rounded px-2 py-1.5 text-[11px] font-mono"
          style={{ backgroundColor: isError ? '#FEF2F2' : '#F0FAFA', color: '#1F2937' }}
        >
          {formatJson(result.data)}
        </pre>
      )}
    </div>
  );
}

export function ThinkingPanel({ steps, isDone, elapsedSeconds }: ThinkingPanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Auto-collapse 1s after done
  useEffect(() => {
    if (isDone) {
      const timer = setTimeout(() => setIsCollapsed(true), 1000);
      return () => clearTimeout(timer);
    }
  }, [isDone]);

  const doneCount = steps.filter((s) => s.status === 'done').length;
  const mcpTools = Array.from(
    new Set(steps.map((step) => step.tool).filter((tool) => MCP_TOOL_NAMES.has(tool))),
  );

  return (
    <div
      className="rounded-xl border overflow-hidden mb-2"
      style={{ borderColor: '#007C7C33', backgroundColor: '#F0FAFA' }}
    >
      {/* Header */}
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
        style={{ color: '#007C7C' }}
        onClick={() => setIsCollapsed((v) => !v)}
      >
        {isDone ? (
          <CheckCircle2 size={13} className="flex-shrink-0" />
        ) : (
          <Loader2 size={13} className="flex-shrink-0 animate-spin" />
        )}
        <span className="text-xs font-medium flex-1">
          {isDone
            ? `工具執行完成（${elapsedSeconds}s）`
            : `工具執行中... ${doneCount}/${steps.length} 步驟`}
        </span>
        {isCollapsed
          ? <ChevronRight size={12} className="flex-shrink-0" />
          : <ChevronDown size={12} className="flex-shrink-0" />}
      </button>

      {/* Steps */}
      {!isCollapsed && steps.length > 0 && (
        <div className="px-3 pb-2.5 space-y-2">
          {mcpTools.length > 0 && (
            <div className="rounded-lg border px-2.5 py-2 bg-white/70" style={{ borderColor: '#007C7C22' }}>
              <div className="flex items-center gap-1.5 mb-1.5">
                <Wrench size={11} className="flex-shrink-0" style={{ color: '#007C7C' }} />
                <span className="text-[11px] font-medium" style={{ color: '#0F766E' }}>
                  本情境調用的 MCP 工具
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {mcpTools.map((tool) => (
                  <span
                    key={tool}
                    className="text-[11px] font-mono rounded-full px-2 py-0.5"
                    style={{ backgroundColor: '#E6F4F1', color: '#0F766E' }}
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-1">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <div className="pt-0.5">
                {step.status === 'calling' ? (
                  <Loader2 size={11} className="flex-shrink-0 animate-spin" style={{ color: '#007C7C' }} />
                ) : (
                  <CheckCircle2 size={11} className="flex-shrink-0" style={{ color: '#22c55e' }} />
                )}
              </div>
              <div className="min-w-0 flex-1">
                {step.kind !== 'tool_result' && (
                  <div
                    className="text-xs leading-relaxed"
                    style={{ color: step.status === 'done' ? '#374151' : '#007C7C' }}
                  >
                    <span className="font-medium mr-1" style={{ color: '#6B7280' }}>
                      [{TOOL_LABELS[step.tool] ?? step.tool}]
                    </span>
                    {step.label}
                  </div>
                )}
                {step.kind === 'calculation' && step.candidates && step.candidates.length > 0 && (
                  <div className="mt-1 rounded-md border bg-white px-2 py-1.5" style={{ borderColor: '#007C7C1f' }}>
                    <div className="space-y-0.5">
                      {step.candidates.slice(0, 4).map((candidate) => (
                        <div key={`${step.channel}-${candidate.card_name}`} className="flex justify-between gap-3 text-[11px] leading-relaxed">
                          <span className="truncate" style={{ color: '#374151' }}>{candidate.card_name}</span>
                          <span className="font-mono text-right flex-shrink-0" style={{ color: '#0F766E' }}>{candidate.formula}</span>
                        </div>
                      ))}
                    </div>
                    {step.rankingSummary && (
                      <div className="mt-1 border-t pt-1 text-[11px]" style={{ borderColor: '#007C7C1f', color: '#6B7280' }}>
                        依預估回饋排序：{step.rankingSummary}
                      </div>
                    )}
                  </div>
                )}
                {step.kind === 'tool_result' && step.toolResult && (
                  <ToolResultBlock result={step.toolResult} />
                )}
              </div>
            </div>
          ))}
          </div>
        </div>
      )}
    </div>
  );
}
