import { useState, useEffect, useRef } from 'react';
import { TopNavigation } from './components/TopNavigation';
import { LeftSidebar } from './components/LeftSidebar';
import { WelcomeSection } from './components/WelcomeSection';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { CardSelectionPage } from './components/CardSelectionPage';
import { ThinkingPanel } from './components/ThinkingPanel';
import type { ThinkingStep } from './components/ThinkingPanel';
import { fetchCards, streamChat } from './api';
import type { CardMenuItem, ChatHistoryItem } from './api';
import type { ToolCall } from './components/ChatMessage';

interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
  thinkingSteps?: ThinkingStep[];
  thinkingDone?: boolean;
  thinkingElapsed?: number;
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const idCounter = useRef(0);

  useEffect(() => {
    fetchCards()
      .then(setAllCards)
      .catch((err) => console.error('Failed to fetch cards:', err))
      .finally(() => setCardsLoading(false));
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

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

  const selectedCardInfos = () =>
    selectedCards
      .map((id) => {
        const card = allCards.find((x) => x.card_id === id);
        return card ? { card_id: card.card_id, card_name: card.card_name } : null;
      })
      .filter((x): x is { card_id: string; card_name: string } => x !== null);

  const buildHistory = (): ChatHistoryItem[] =>
    messages.map((m) => ({ role: m.role, content: m.content }));

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

    const userId = ++idCounter.current;
    const assistantId = ++idCounter.current;
    const historyForServer = buildHistory();

    setMessages((prev) => [
      ...prev,
      { id: userId, role: 'user', content: message },
      {
        id: assistantId,
        role: 'assistant',
        content: '',
        toolCalls: [],
        thinkingSteps: [],
        thinkingDone: false,
      },
    ]);
    setIsLoading(true);

    const updateAssistant = (updater: (m: Message) => Message) => {
      setMessages((prev) => prev.map((m) => (m.id === assistantId ? updater(m) : m)));
    };

    let textBuffer = '';
    const toolCalls: ToolCall[] = [];
    const startedAt = Date.now();

    try {
      await streamChat(
        message,
        selectedCardInfos(),
        historyForServer,
        {
          onText: (delta) => {
            textBuffer += delta;
            updateAssistant((m) => ({ ...m, content: textBuffer }));
          },
          onToolUse: (evt) => {
            toolCalls.push({ name: evt.tool_name, input: evt.input });
            updateAssistant((m) => ({
              ...m,
              toolCalls: [...toolCalls],
              thinkingSteps: applyStepEvent(
                m.thinkingSteps ?? [],
                evt.tool_name,
                'calling',
                `正在呼叫 ${evt.tool_name}`,
              ),
            }));
          },
          onToolResult: (evt) => {
            const lastToolName = toolCalls[toolCalls.length - 1]?.name ?? 'tool_result';
            updateAssistant((m) => ({
              ...m,
              thinkingSteps: applyStepEvent(
                m.thinkingSteps ?? [],
                lastToolName,
                'done',
                evt.summary || '工具查詢完成',
              ),
            }));
          },
          onDone: () => {
            updateAssistant((m) => ({
              ...m,
              thinkingDone: true,
              thinkingElapsed: Math.round((Date.now() - startedAt) / 1000),
            }));
          },
          onError: (msg) => {
            updateAssistant((m) => ({
              ...m,
              content: `抱歉，發生錯誤：${msg}`,
              thinkingDone: true,
            }));
          },
        },
      );
    } catch {
      updateAssistant((m) => ({
        ...m,
        content: '抱歉，無法連線到伺服器，請確認後端是否已啟動。',
        thinkingDone: true,
      }));
    } finally {
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
                      {message.role === 'assistant' &&
                        message.thinkingSteps &&
                        message.thinkingSteps.length > 0 && (
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
                              <ThinkingPanel
                                steps={message.thinkingSteps}
                                isDone={message.thinkingDone ?? false}
                                elapsedSeconds={message.thinkingElapsed}
                              />
                            </div>
                          </div>
                        )}

                      {(message.role === 'user' ||
                        message.content ||
                        (message.toolCalls && message.toolCalls.length > 0)) && (
                        <ChatMessage
                          role={message.role}
                          content={message.content}
                          toolCalls={message.toolCalls}
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
