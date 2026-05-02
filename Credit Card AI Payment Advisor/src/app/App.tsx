import { useState, useEffect, useRef } from 'react';
import { TopNavigation } from './components/TopNavigation';
import { LeftSidebar } from './components/LeftSidebar';
import { WelcomeSection } from './components/WelcomeSection';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { CardSelectionPage } from './components/CardSelectionPage';
import { fetchCards, recommendPayment } from './api';
import type { CardMenuItem, SearchResult } from './api';

interface Recommendation {
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
  role: 'user' | 'assistant';
  content: string;
  recommendations?: Recommendation[];
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
    rank,
    cardName: r.card_name,
    channel,
    rewardRate: `${rate} 回饋`,
    estimatedCashback: est,
    monthlyCap: cap,
    expirationDate: r.valid_end ?? '長期有效',
    conditions,
    reason: r.cashback_description || `此卡在「${channel}」通路的回饋率為 ${rate}。`,
    color: RANK_COLORS[rank - 1] ?? RANK_COLORS[2],
    badges: badges.length > 0 ? badges : undefined,
  };
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

  const handleSendMessage = async (message: string) => {
    setShowWelcome(false);

    const userMessage: Message = { role: 'user', content: message };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const data = await recommendPayment(message, selectedCards);

      if (data.error) {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: `抱歉，查詢時發生錯誤：${data.error}` },
        ]);
        return;
      }

      // Convert API response to Recommendation[]
      const recs: Recommendation[] = [];
      let globalRank = 1;
      for (const rec of data.recommendations) {
        const results = rec.best_options ?? [];
        for (const r of results) {
          if (globalRank > 3) break;
          recs.push(toRecommendation(r, globalRank, rec.channel_name));
          globalRank++;
        }
        if (globalRank > 3) break;
      }

      const channelNames = data.recommendations.map((r) => r.channel_name).join('、');
      const amountText = data.parsed.amount > 0 ? `消費 NT$ ${data.parsed.amount.toLocaleString()} 元` : '';
      const summary = `根據您的問題「${message}」，系統識別出通路：${channelNames}${amountText ? `，${amountText}` : ''}。以下是最佳付款選項：`;

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: summary, recommendations: recs },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '抱歉，無法連線到伺服器，請確認 MCP Server 是否已啟動。' },
      ]);
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
                      recommendations={message.recommendations}
                    />
                  ))}

                  {isLoading && (
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