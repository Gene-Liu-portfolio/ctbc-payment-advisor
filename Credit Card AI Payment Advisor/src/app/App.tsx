import { useState, useEffect, useRef } from 'react';
import { TopNavigation } from './components/TopNavigation';
import { LeftSidebar } from './components/LeftSidebar';
import { WelcomeSection } from './components/WelcomeSection';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { CardSelectionPage } from './components/CardSelectionPage';
import { fetchCards, streamChat } from './api';
import type { CardMenuItem, ChatHistoryItem } from './api';
import type { ToolCall } from './components/ChatMessage';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
}

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<'selection' | 'chat'>('selection');
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [showWelcome, setShowWelcome] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [allCards, setAllCards] = useState<CardMenuItem[]>([]);
  const [cardsLoading, setCardsLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

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
      '🍽️ 餐廳用餐': '在餐廳用餐 1500 元，該用哪張卡？',
      '🏠  國內旅遊': '國內旅遊訂飯店 3000 元，推薦哪張卡？',
      '🗾 日本旅遊': '我在日本旅遊刷卡 5000 元，該用哪張卡？',
      '🛒  線上購物': '線上購物 2000 元，哪張卡回饋最高？',
      '✈️ 訂房/機票': '訂機票 12000 元，推薦哪張卡？',
      '🎬 娛樂消費': '看電影買票 800 元，該用哪張卡？',
    };
    setInputValue(scenarioMap[scenario] || scenario);
  };

  const handlePromptClick = (prompt: string) => {
    setInputValue(prompt);
  };

  const selectedCardInfos = () =>
    selectedCards
      .map((id) => {
        const c = allCards.find((x) => x.card_id === id);
        return c ? { card_id: c.card_id, card_name: c.card_name } : null;
      })
      .filter((x): x is { card_id: string; card_name: string } => x !== null);

  const buildHistory = (): ChatHistoryItem[] =>
    messages.map((m) => ({ role: m.role, content: m.content }));

  const handleSendMessage = async (message: string) => {
    if (selectedCards.length === 0) {
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: message },
        { role: 'assistant', content: '請先在左側選擇您持有的信用卡，我才能為您推薦最適合的刷卡選擇。' },
      ]);
      return;
    }

    setShowWelcome(false);
    const userMessage: Message = { role: 'user', content: message };
    const historyForServer = buildHistory();

    setMessages((prev) => [...prev, userMessage, { role: 'assistant', content: '', toolCalls: [] }]);
    setIsLoading(true);

    const assistantIndex = messages.length + 1;
    let textBuffer = '';
    const toolCalls: ToolCall[] = [];

    try {
      await streamChat(
        message,
        selectedCardInfos(),
        historyForServer,
        {
          onText: (delta) => {
            textBuffer += delta;
            setMessages((prev) => {
              const next = [...prev];
              if (next[assistantIndex]) {
                next[assistantIndex] = { ...next[assistantIndex], content: textBuffer };
              }
              return next;
            });
          },
          onToolUse: (evt) => {
            toolCalls.push({ name: evt.tool_name, input: evt.input });
            setMessages((prev) => {
              const next = [...prev];
              if (next[assistantIndex]) {
                next[assistantIndex] = { ...next[assistantIndex], toolCalls: [...toolCalls] };
              }
              return next;
            });
          },
          onError: (msg) => {
            setMessages((prev) => {
              const next = [...prev];
              if (next[assistantIndex]) {
                next[assistantIndex] = {
                  ...next[assistantIndex],
                  content: `抱歉，發生錯誤：${msg}`,
                };
              }
              return next;
            });
          },
        },
      );
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        if (next[assistantIndex]) {
          next[assistantIndex] = {
            ...next[assistantIndex],
            content: '抱歉，無法連線到伺服器，請確認後端是否已啟動。',
          };
        }
        return next;
      });
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
                  {messages.map((message, index) => (
                    <ChatMessage
                      key={index}
                      role={message.role}
                      content={message.content}
                      toolCalls={message.toolCalls}
                    />
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
