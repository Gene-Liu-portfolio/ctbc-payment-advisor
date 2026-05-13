import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Loader2, CheckCircle2 } from 'lucide-react';

export interface ThinkingStep {
  tool: string;
  status: 'calling' | 'done';
  label: string;
}

interface ThinkingPanelProps {
  steps: ThinkingStep[];
  isDone: boolean;
  elapsedSeconds?: number;
}

const TOOL_LABELS: Record<string, string> = {
  parse_scenario:    '情境解析',
  search_by_channel: '通路查詢',
  generate_reasons:  '理由生成',
};

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
            ? `思考完成（${elapsedSeconds}s）`
            : `思考中... ${doneCount}/${steps.length} 步驟`}
        </span>
        {isCollapsed
          ? <ChevronRight size={12} className="flex-shrink-0" />
          : <ChevronDown size={12} className="flex-shrink-0" />}
      </button>

      {/* Steps */}
      {!isCollapsed && steps.length > 0 && (
        <div className="px-3 pb-2.5 space-y-1">
          {steps.map((step, i) => (
            <div key={i} className="flex items-center gap-1.5">
              {step.status === 'calling' ? (
                <Loader2 size={11} className="flex-shrink-0 animate-spin" style={{ color: '#007C7C' }} />
              ) : (
                <CheckCircle2 size={11} className="flex-shrink-0" style={{ color: '#22c55e' }} />
              )}
              <span
                className="text-xs leading-relaxed"
                style={{ color: step.status === 'done' ? '#374151' : '#007C7C' }}
              >
                <span className="font-medium mr-1" style={{ color: '#6B7280' }}>
                  [{TOOL_LABELS[step.tool] ?? step.tool}]
                </span>
                {step.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
