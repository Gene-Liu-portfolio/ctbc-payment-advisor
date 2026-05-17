import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, Wrench } from 'lucide-react';

export interface CalculationCandidate {
  card_name: string;
  formula: string;
  estimated_cashback: number | null;
}

export interface ThinkingStep {
  tool: string;
  status: 'calling' | 'done';
  label: string;
  kind?: 'step' | 'calculation';
  channel?: string;
  candidates?: CalculationCandidate[];
  winner?: CalculationCandidate | null;
  rankingSummary?: string;
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
                <div
                  className="text-xs leading-relaxed"
                  style={{ color: step.status === 'done' ? '#374151' : '#007C7C' }}
                >
                  <span className="font-medium mr-1" style={{ color: '#6B7280' }}>
                    [{TOOL_LABELS[step.tool] ?? step.tool}]
                  </span>
                  {step.label}
                </div>
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
              </div>
            </div>
          ))}
          </div>
        </div>
      )}
    </div>
  );
}
