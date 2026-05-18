import { useState, useEffect, useRef } from 'react';
import { TopNavigation } from './components/TopNavigation';
import { LeftSidebar } from './components/LeftSidebar';
import { WelcomeSection } from './components/WelcomeSection';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { CardSelectionPage } from './components/CardSelectionPage';
import { ThinkingPanel } from './components/ThinkingPanel';
import type { CalculationCandidate, ThinkingStep, ToolResultTrace } from './components/ThinkingPanel';
import { AgentThinkingPanel } from './components/AgentThinkingPanel';
import type { AgentEvent } from './components/AgentThinkingPanel';
import { fetchCards, streamChat } from './api';
import type { CardMenuItem, ChatHistoryItem, SearchResult } from './api';

interface Recommendation {
  cardId: string;
  rank: number;
  cardName: string;
  channel: string;
  rewardRate: string;
  estimatedCashback: string;
  monthlyCap: string;
  expirationDate: string;
  conditions: string[];
  reason: string;
  color: string;
  badges?: string[];
}

interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  recommendations?: Recommendation[];
  thinkingSteps?: ThinkingStep[];
  thinkingDone?: boolean;
  thinkingElapsed?: number;
  agentEvents?: AgentEvent[];
  preferStructuredResult?: boolean;
}

const RANK_COLORS = [
  'from-green-500 to-green-600',
  'from-amber-500 to-amber-600',
  'from-fuchsia-500 to-fuchsia-600',
];

const TOOL_TRACE_STEP_DELAY_MS = 220;

function toRecommendation(result: SearchResult, rank: number, channel: string): Recommendation {
  const rate = result.cashback_rate != null ? `${(result.cashback_rate * 100).toFixed(1)}%` : '—';
  const estimated = result.estimated_cashback != null
    ? `NT$ ${result.estimated_cashback.toLocaleString()}`
    : '—';
  const cap = result.max_cashback_per_period != null
    ? `NT$ ${result.max_cashback_per_period.toLocaleString()}/期`
    : '無上限';
  const badges: string[] = [];
  if (rank === 1) badges.push('最高回饋');
  if (result.expiring_soon) badges.push('即將到期');
  if (result.is_fallback) badges.push('一般消費回饋');

  const conditions: string[] = [];
  if (result.conditions) conditions.push(result.conditions);
  if (result.cashback_description) conditions.push(result.cashback_description);
  for (const highlight of result.detail_highlights ?? []) {
    if (highlight && !conditions.includes(highlight)) conditions.push(highlight);
  }
  for (const alert of result.promotion_alerts ?? []) {
    if (alert && !conditions.includes(alert)) conditions.push(`活動提醒：${alert}`);
  }

  return {
    cardId: result.card_id,
    rank,
    cardName: result.card_name,
    channel,
    rewardRate: `${rate} 回饋`,
    estimatedCashback: estimated,
    monthlyCap: cap,
    expirationDate: result.valid_end ?? '長期有效',
    conditions,
    reason: result.reason || result.cashback_description || `此卡在「${channel}」通路的回饋率為 ${rate}。`,
    color: RANK_COLORS[rank - 1] ?? RANK_COLORS[2],
    badges: badges.length > 0 ? badges : undefined,
  };
}

function applyStepEvent(
  steps: ThinkingStep[],
  tool: string,
  status: 'calling' | 'done',
  label: string,
  channel?: string,
): ThinkingStep[] {
  const next = [...steps];
  if (status === 'done') {
    let idx = -1;
    for (let i = next.length - 1; i >= 0; i--) {
      if (next[i].tool === tool && next[i].status === 'calling') {
        if (!channel || next[i].label.includes(channel)) {
          idx = i;
          break;
        }
      }
    }
    if (idx !== -1) {
      next[idx] = { tool, status: 'done', label };
      return next;
    }
  }
  return [...next, { tool, status, label }];
}

function applyCalculationEvent(
  steps: ThinkingStep[],
  channel: string,
  candidates: CalculationCandidate[],
  winner: CalculationCandidate | null,
  rankingSummary: string,
): ThinkingStep[] {
  return [
    ...steps,
    {
      tool: 'mcp_calculation',
      status: 'done',
      kind: 'calculation',
      channel,
      candidates,
      winner,
      rankingSummary,
      label: `MCP 完成「${channel}」候選卡計算`,
    },
  ];
}

function applyToolResultEvent(
  steps: ThinkingStep[],
  result: ToolResultTrace,
): ThinkingStep[] {
  return [
    ...steps,
    {
      tool: result.tool,
      status: 'done',
      kind: 'tool_result',
      channel: result.channel ?? undefined,
      label: `MCP 工具回傳：${result.tool}`,
      toolResult: result,
    },
  ];
}

function recommendationsFromStructuredData(
  data: {
    recommendations?: Array<{
      channel_name?: string;
      best_options?: SearchResult[];
    }>;
  } | null | undefined,
): Recommendation[] {
  const recommendations: Recommendation[] = [];
  const maxCards = 4;

  for (const rec of data?.recommendations ?? []) {
    const channelName = rec.channel_name ?? '推薦結果';
    for (const option of rec.best_options ?? []) {
      if (recommendations.length >= maxCards) return recommendations;
      recommendations.push(toRecommendation(option, recommendations.length + 1, channelName));
    }
  }

  return recommendations;
}

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<'selection' | 'chat'>('selection');
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [showWelcome, setShowWelcome] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [allCards, setAllCards] = useState<CardMenuItem[]>([]);
  const [cardsLoading, setCardsLoading] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const idCounter = useRef(0);

  useEffect(() => {
    fetchCards()
      .then(setAllCards)
      .catch((err) => console.error('Failed to fetch cards:', err))
      .finally(() => setCardsLoading(false));
  }, []);

  useEffect(() => {
    if (scrollRef.current && shouldAutoScrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleChatScroll = () => {
    const el = scrollRef.current;
    if (!el) return;

    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom < 80;
  };

  const handleCardToggle = (cardId: string) => {
    setSelectedCards((prev) =>
      prev.includes(cardId)
        ? prev.filter((id) => id !== cardId)
        : [...prev, cardId],
    );
  };

  const handleScenarioClick = (scenario: string) => {
    const scenarioMap: Record<string, string> = {
      '餐廳用餐': '在餐廳用餐 1500 元，該用哪張卡？',
      '國內旅遊': '國內旅遊訂飯店 3000 元，推薦哪張卡？',
      '日本旅遊': '我在日本旅遊刷卡 5000 元，該用哪張卡？',
      '線上購物': '線上購物 2000 元，哪張卡回饋最高？',
      '訂房/機票': '訂機票 12000 元，推薦哪張卡？',
      '娛樂消費': '看電影買票 800 元，該用哪張卡？',
    };
    setInputValue(scenarioMap[scenario] || scenario);
  };

  const handlePromptClick = (prompt: string) => {
    setInputValue(prompt);
  };

  const handleSendMessage = async (message: string) => {
    if (selectedCards.length === 0) {
      const userId = ++idCounter.current;
      const assistantId = ++idCounter.current;
      setMessages((prev) => [
        ...prev,
        { id: userId, role: 'user', content: message },
        {
          id: assistantId,
          role: 'assistant',
          content: '請先在左側選擇您持有的信用卡，我才能為您推薦最適合的刷卡選擇。',
        },
      ]);
      return;
    }

    setShowWelcome(false);
    shouldAutoScrollRef.current = true;

    const userId = ++idCounter.current;
    const assistantId = ++idCounter.current;
    const startedAt = Date.now();

    setMessages((prev) => [
      ...prev,
      { id: userId, role: 'user', content: message },
      agentMode
        ? {
            id: assistantId,
            role: 'assistant',
            content: '',
            agentEvents: [],
            thinkingDone: false,
          }
        : {
            id: assistantId,
            role: 'assistant',
            content: '',
            thinkingSteps: [],
            thinkingDone: false,
          },
    ]);
    setIsLoading(true);

    const updateAssistant = (updater: (m: Message) => Message) => {
      setMessages((prev) => prev.map((m) => (m.id === assistantId ? updater(m) : m)));
    };

    const assistantUpdateQueue: Array<(m: Message) => Message> = [];
    let isProcessingAssistantQueue = false;
    let queueDrainResolve: (() => void) | null = null;

    const flushAssistantUpdateQueue = () => {
      const next = assistantUpdateQueue.shift();
      if (!next) {
        isProcessingAssistantQueue = false;
        queueDrainResolve?.();
        queueDrainResolve = null;
        return;
      }

      updateAssistant(next);
      window.setTimeout(flushAssistantUpdateQueue, TOOL_TRACE_STEP_DELAY_MS);
    };

    const enqueueAssistantUpdate = (updater: (m: Message) => Message) => {
      assistantUpdateQueue.push(updater);
      if (!isProcessingAssistantQueue) {
        isProcessingAssistantQueue = true;
        flushAssistantUpdateQueue();
      }
    };

    const waitForAssistantUpdateQueue = () => new Promise<void>((resolve) => {
      if (!isProcessingAssistantQueue && assistantUpdateQueue.length === 0) {
        resolve();
        return;
      }
      queueDrainResolve = resolve;
    });

    if (agentMode) {
      const cardsOwned = selectedCards
        .map((id) => {
          const card = allCards.find((c) => c.card_id === id);
          return card ? { card_id: card.card_id, card_name: card.card_name } : null;
        })
        .filter((c): c is { card_id: string; card_name: string } => c !== null);

      const history: ChatHistoryItem[] = messages
        .filter((m) => m.content && m.content.trim() !== '')
        .map((m) => ({ role: m.role, content: m.content }));

      try {
        await streamChat(message, cardsOwned, history, {
          onText: (delta) => {
            updateAssistant((m) => (
              m.preferStructuredResult ? m : { ...m, content: m.content + delta }
            ));
          },
          onToolUse: (evt) => {
            updateAssistant((m) => ({
              ...m,
              agentEvents: [
                ...(m.agentEvents ?? []),
                {
                  kind: 'tool_use',
                  id: evt.id,
                  tool_name: evt.tool_name,
                  input: evt.input,
                },
              ],
            }));
          },
          onToolResult: (evt) => {
            const structuredRecommendations = recommendationsFromStructuredData(evt.data);
            updateAssistant((m) => ({
              ...m,
              agentEvents: [
                ...(m.agentEvents ?? []),
                {
                  kind: 'tool_result',
                  tool_use_id: evt.tool_use_id,
                  summary: evt.summary,
                  is_error: evt.is_error,
                },
              ],
              ...(structuredRecommendations.length > 0
                ? {
                    content: '已根據 MCP 工具回傳整理成推薦卡片：',
                    recommendations: structuredRecommendations,
                    preferStructuredResult: true,
                  }
                : {}),
            }));
          },
          onDone: () => {
            updateAssistant((m) => ({
              ...m,
              thinkingDone: true,
              thinkingElapsed: Math.round((Date.now() - startedAt) / 1000),
            }));
          },
          onError: (err) => {
            updateAssistant((m) => ({
              ...m,
              agentEvents: [
                ...(m.agentEvents ?? []),
                {
                  kind: 'error',
                  type: err.type,
                  message: err.message,
                  status_code: err.status_code,
                },
              ],
              content: m.content || '抱歉，處理過程中發生錯誤，請參考上方錯誤訊息。',
              thinkingDone: true,
              thinkingElapsed: Math.round((Date.now() - startedAt) / 1000),
            }));
          },
        });
      } catch {
        updateAssistant((m) => ({
          ...m,
          content: '抱歉，無法連線到伺服器，請確認後端是否已啟動。',
          thinkingDone: true,
        }));
      } finally {
        setIsLoading(false);
      }
      return;
    }

    try {
      const response = await fetch('/api/recommend/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: message, cards_owned: selectedCards }),
      });

      if (!response.ok || !response.body) {
        updateAssistant((m) => ({
          ...m,
          content: `抱歉，發生錯誤：HTTP ${response.status}`,
          thinkingDone: true,
        }));
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const chunks = buffer.split('\n\n');
        buffer = chunks.pop() ?? '';

        for (const chunk of chunks) {
          const dataLine = chunk.split('\n').find((line) => line.startsWith('data:'));
          if (!dataLine) continue;

          try {
            const event = JSON.parse(dataLine.replace(/^data:\s*/, ''));

            if (event.type === 'tool_call') {
              enqueueAssistantUpdate((m) => ({
                ...m,
                thinkingSteps: applyStepEvent(
                  m.thinkingSteps ?? [],
                  event.tool,
                  event.status,
                  event.label,
                  event.channel,
                ),
              }));
            } else if (event.type === 'thinking_done') {
              enqueueAssistantUpdate((m) => ({
                ...m,
                thinkingDone: true,
                thinkingElapsed: event.elapsed_seconds,
              }));
            } else if (event.type === 'mcp_calculation') {
              enqueueAssistantUpdate((m) => ({
                ...m,
                thinkingSteps: applyCalculationEvent(
                  m.thinkingSteps ?? [],
                  event.channel,
                  event.candidates ?? [],
                  event.winner ?? null,
                  event.ranking_summary ?? '',
                ),
              }));
            } else if (event.type === 'tool_result') {
              enqueueAssistantUpdate((m) => ({
                ...m,
                thinkingSteps: applyToolResultEvent(
                  m.thinkingSteps ?? [],
                  {
                    tool: event.tool,
                    channel: event.channel ?? null,
                    status: event.status === 'error' ? 'error' : 'success',
                    summary: event.summary ?? '',
                    data: event.data ?? {},
                  },
                ),
              }));
            } else if (event.type === 'result') {
              const data = event.data;
              if (data.off_topic_message) {
                enqueueAssistantUpdate((m) => ({ ...m, content: data.off_topic_message }));
              } else if (data.error) {
                enqueueAssistantUpdate((m) => ({ ...m, content: `抱歉，查詢時發生錯誤：${data.error}` }));
              } else {
                const maxCards = 4;
                const recommendations: Recommendation[] = [];

                for (const rec of data.recommendations ?? []) {
                  for (const option of rec.best_options ?? []) {
                    if (recommendations.length >= maxCards) break;
                    recommendations.push(
                      toRecommendation(option, recommendations.length + 1, rec.channel_name),
                    );
                  }
                  if (recommendations.length >= maxCards) break;
                }

                const channelNames = (data.recommendations ?? [])
                  .map((rec: { channel_name: string }) => rec.channel_name)
                  .join('、');
                const amount = data.parsed?.amount ?? 0;
                const amountText = amount > 0
                  ? `，消費 ${data.amount_info?.amount_display ?? `NT$ ${amount.toLocaleString()} 元`}`
                  : '';
                const summary = recommendations.length > 0
                  ? `系統識別出通路：${channelNames}${amountText}。以下是最佳付款選項：`
                  : '目前沒有找到符合條件的推薦卡片。';

                enqueueAssistantUpdate((m) => ({
                  ...m,
                  content: summary,
                  recommendations,
                }));
              }
            }
          } catch {
            // Ignore malformed SSE events.
          }
        }
      }
    } catch {
      updateAssistant((m) => ({
        ...m,
        content: '抱歉，無法連線到伺服器，請確認後端是否已啟動。',
        thinkingDone: true,
      }));
    } finally {
      await waitForAssistantUpdateQueue();
      setIsLoading(false);
    }
  };

  const handleStartChat = () => {
    setCurrentScreen('chat');
  };

  if (currentScreen === 'selection') {
    return (
      <CardSelectionPage
        selectedCards={selectedCards}
        onCardToggle={handleCardToggle}
        onSelectAll={(cardIds) => setSelectedCards(cardIds)}
        onStart={handleStartChat}
        cards={allCards}
        loading={cardsLoading}
      />
    );
  }

  return (
    <div className="h-screen flex flex-col" style={{ backgroundColor: '#F7F9F8' }}>
      <TopNavigation
        onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        isSidebarCollapsed={isSidebarCollapsed}
        agentMode={agentMode}
        onAgentModeChange={setAgentMode}
      />

      <div className="flex-1 flex overflow-hidden min-h-0">
        <LeftSidebar
          selectedCards={selectedCards}
          onCardToggle={handleCardToggle}
          onSelectAll={(cardIds) => setSelectedCards(cardIds)}
          onScenarioClick={handleScenarioClick}
          isCollapsed={isSidebarCollapsed}
          cards={allCards}
        />

        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          <div ref={scrollRef} onScroll={handleChatScroll} className="flex-1 overflow-y-auto">
            <div className="max-w-5xl mx-auto w-full pb-6">
              {showWelcome && <WelcomeSection onPromptClick={handlePromptClick} />}

              {messages.length > 0 && (
                <div className="p-6 space-y-6">
                  {messages.map((message) => (
                    <div key={message.id}>
                      {message.role === 'assistant' &&
                        ((message.thinkingSteps && message.thinkingSteps.length > 0) ||
                          (message.agentEvents && message.agentEvents.length > 0) ||
                          (message.agentEvents && !message.thinkingDone)) && (
                          <div className="flex gap-3 mb-1">
                            <div
                              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                              style={{ background: 'linear-gradient(135deg, #007C7C 0%, #005c5c 100%)' }}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M12 8V4H8" />
                                <rect width="16" height="12" x="4" y="8" rx="2" />
                                <path d="M2 14h2" />
                                <path d="M20 14h2" />
                                <path d="M15 13v2" />
                                <path d="M9 13v2" />
                              </svg>
                            </div>
                            <div className="flex-1 min-w-0">
                              {message.agentEvents ? (
                                <AgentThinkingPanel
                                  events={message.agentEvents}
                                  isDone={message.thinkingDone ?? false}
                                  elapsedSeconds={message.thinkingElapsed}
                                />
                              ) : (
                                <ThinkingPanel
                                  steps={message.thinkingSteps ?? []}
                                  isDone={message.thinkingDone ?? false}
                                  elapsedSeconds={message.thinkingElapsed}
                                />
                              )}
                            </div>
                          </div>
                        )}

                      {(message.role === 'user' ||
                        message.content ||
                        (message.recommendations && message.recommendations.length > 0)) && (
                        <ChatMessage
                          role={message.role}
                          content={message.content}
                          recommendations={message.recommendations}
                        />
                      )}
                    </div>
                  ))}

                  {isLoading && messages[messages.length - 1]?.content === '' && (
                    <div className="flex items-center gap-3 px-4 py-3">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: '#007C7C' }}>
                        <span className="text-white text-xs font-bold">AI</span>
                      </div>
                      <div className="flex gap-1">
                        <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: '#007C7C', animationDelay: '0ms' }} />
                        <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: '#007C7C', animationDelay: '150ms' }} />
                        <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: '#007C7C', animationDelay: '300ms' }} />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex-shrink-0">
            <ChatInput
              onSend={handleSendMessage}
              value={inputValue}
              onChange={setInputValue}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
