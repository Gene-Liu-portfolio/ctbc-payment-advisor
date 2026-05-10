import { useState, useEffect, useRef } from 'react';
import { TopNavigation } from './components/TopNavigation';
import { LeftSidebar } from './components/LeftSidebar';
import { WelcomeSection } from './components/WelcomeSection';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { CardSelectionPage } from './components/CardSelectionPage';
import { ThinkingPanel } from './components/ThinkingPanel';
import type { ThinkingStep } from './components/ThinkingPanel';
import { fetchCards } from './api';
import type { CardMenuItem, SearchResult } from './api';

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
}

// Rank-based gradient colors
const RANK_COLORS = [
  'from-green-500 to-green-600',
  'from-amber-500 to-amber-600',
  'from-fuchsia-500 to-fuchsia-600',
];

function toRecommendation(r: SearchResult, rank: number, channel: string): Recommendation {
  const rate = r.cashback_rate != null ? `${(r.cashback_rate * 100).toFixed(1)}%` : '—';
  const est = r.estimated_cashback != null ? `NT$ ${r.estimated_cashback.toLocaleString()}` : '—';
  const cap = r.max_cashback_per_period != null
    ? `NT$ ${r.max_cashback_per_period.toLocaleString()}/期`
    : '無上限';
  const badges: string[] = [];
  if (rank === 1) badges.push('最高回饋');
  if (r.expiring_soon) badges.push('即將到期');
  if (r.is_fallback) badges.push('一般消費回饋');

  const conditions: string[] = [];
  if (r.conditions) conditions.push(r.conditions);
  if (r.cashback_description) conditions.push(r.cashback_description);

  return {
    cardId: r.card_id,
    rank,
    cardName: r.card_name,
    channel,
    rewardRate: `${rate} 回饋`,
    estimatedCashback: est,
    monthlyCap: cap,
    expirationDate: r.valid_end ?? '長期有效',
    conditions,
    reason: r.reason || r.cashback_description || `此卡在「${channel}」通路的回饋率為 ${rate}。`,
    color: RANK_COLORS[rank - 1] ?? RANK_COLORS[2],
    badges: badges.length > 0 ? badges : undefined,
  };
}

// Helper: update a single step in-place or append
function applyStepEvent(
  steps: ThinkingStep[],
  tool: string,
  status: 'calling' | 'done',
  label: string,
  channel?: string,
): ThinkingStep[] {
  const next = [...steps];
  if (status === 'done') {
    // Find last matching "calling" step for this tool (+ optional channel match)
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

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<'selection' | 'chat'>('selection');
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [showWelcome, setShowWelcome] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [allCards, setAllCards] = useState<CardMenuItem[]>([]);
  const [cardsLoading, setCardsLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const idCounter = useRef(0);

  // Fetch cards from API on mount
  useEffect(() => {
    fetchCards()
      .then(setAllCards)
      .catch((err) => console.error('Failed to fetch cards:', err))
      .finally(() => setCardsLoading(false));
  }, []);

  // Auto-scroll to bottom when new messages appear
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleCardToggle = (cardId: string) => {
    setSelectedCards((prev) =>
      prev.includes(cardId)
        ? prev.filter((id) => id !== cardId)
        : [...prev, cardId]
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
    setShowWelcome(false);

    const userId = ++idCounter.current;
    const assistantId = ++idCounter.current;

    // Add user message + assistant placeholder in one update
    setMessages((prev) => [
      ...prev,
      { id: userId, role: 'user', content: message },
      { id: assistantId, role: 'assistant', content: '', thinkingSteps: [], thinkingDone: false },
    ]);

    const updateAssistant = (updater: (m: Message) => Message) => {
      setMessages((prev) => prev.map((m) => (m.id === assistantId ? updater(m) : m)));
    };

    try {
      const response = await fetch('/api/recommend/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: message, cards_owned: selectedCards }),
      });

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const chunks = buffer.split('\n\n');
        buffer = chunks.pop() ?? '';

        for (const chunk of chunks) {
          const dataLine = chunk.split('\n').find((l) => l.startsWith('data:'));
          if (!dataLine) continue;
          try {
            const event = JSON.parse(dataLine.replace(/^data:\s*/, ''));

            if (event.type === 'tool_call') {
              updateAssistant((m) => ({
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
              updateAssistant((m) => ({
                ...m,
                thinkingDone: true,
                thinkingElapsed: event.elapsed_seconds,
              }));
            } else if (event.type === 'result') {
              const data = event.data;
              if (data.off_topic_message) {
                updateAssistant((m) => ({ ...m, content: data.off_topic_message }));
              } else if (data.error) {
                updateAssistant((m) => ({ ...m, content: `抱歉，查詢時發生錯誤：${data.error}` }));
              } else {
                // Each channel gets its best card first, then fill remaining slots
                const MAX_CARDS = 4;
                const recs: Recommendation[] = [];

                // Pass 1: one best card per channel
                for (const rec of data.recommendations) {
                  const best = rec.best_options?.[0];
                  if (best && recs.length < MAX_CARDS) {
                    recs.push(toRecommendation(best, recs.length + 1, rec.channel_name));
                  }
                }

                // Pass 2: fill remaining slots with 2nd-best cards
                for (const rec of data.recommendations) {
                  if (recs.length >= MAX_CARDS) break;
                  const second = rec.best_options?.[1];
                  if (second) {
                    recs.push(toRecommendation(second, recs.length + 1, rec.channel_name));
                  }
                }

                // Re-assign ranks sequentially
                recs.forEach((r, i) => { r.rank = i + 1; });
                const channelNames = data.recommendations.map((r: any) => r.channel_name).join('、');
                const amountText = data.parsed.amount > 0
                  ? `，消費 NT$ ${data.parsed.amount.toLocaleString()} 元`
                  : '';
                const summary = `系統識別出通路：${channelNames}${amountText}。以下是最佳付款選項：`;
                updateAssistant((m) => ({ ...m, content: summary, recommendations: recs }));
              }
            }
          } catch {
            // ignore malformed SSE lines
          }
        }
      }
    } catch {
      updateAssistant((m) => ({
        ...m,
        content: '抱歉，無法連線到伺服器，請確認後端是否已啟動（python -m mcp_server.http_app）。',
      }));
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
          <div ref={scrollRef} className="flex-1 overflow-y-auto">
            <div className="max-w-5xl mx-auto w-full pb-6">
              {showWelcome && <WelcomeSection onPromptClick={handlePromptClick} />}

              {messages.length > 0 && (
                <div className="p-6 space-y-6">
                  {messages.map((message) => (
                    <div key={message.id}>
                      {/* ThinkingPanel lives above assistant content, sharing the same row */}
                      {message.role === 'assistant' &&
                        message.thinkingSteps &&
                        message.thinkingSteps.length > 0 && (
                          <div className="flex gap-3 mb-1">
                            {/* Avatar — same as ChatMessage's assistant avatar */}
                            <div
                              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                              style={{ background: 'linear-gradient(135deg, #007C7C 0%, #005c5c 100%)' }}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>
                              </svg>
                            </div>
                            <div className="flex-1 min-w-0">
                              <ThinkingPanel
                                steps={message.thinkingSteps}
                                isDone={message.thinkingDone ?? false}
                                elapsedSeconds={message.thinkingElapsed}
                              />
                            </div>
                          </div>
                        )}

                      {/* Only render ChatMessage when there's actual content */}
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