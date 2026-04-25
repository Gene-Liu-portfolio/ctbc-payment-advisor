import { useState, useEffect, useRef } from 'react';
import { TopNavigation } from './components/TopNavigation';
import { LeftSidebar } from './components/LeftSidebar';
import { WelcomeSection } from './components/WelcomeSection';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { CardSelectionPage } from './components/CardSelectionPage';

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

const mockRecommendations: Recommendation[] = [
  {
    rank: 1,
    cardName: '中信 LINE Pay 信用卡',
    channel: '餐飲',
    rewardRate: '5% 回饋',
    estimatedCashback: 'NT$ 75',
    monthlyCap: 'NT$ 1,000/月',
    expirationDate: '2026/12/31',
    conditions: [
      '適用於所有餐廳及咖啡廳消費',
      '單筆消費需滿 NT$ 500',
      '需事先登錄餐飲類別',
    ],
    reason: '此卡在您所選的信用卡中提供最高的餐飲回饋率。透過 5% 現金回饋，您將在此次消費中獲得最大化的優惠。',
    color: 'from-green-500 to-green-600',
    badges: ['最高回饋'],
  },
  {
    rank: 2,
    cardName: '中信現金回饋御璽卡',
    channel: '全通路',
    rewardRate: '2% 回饋',
    estimatedCashback: 'NT$ 30',
    monthlyCap: '無上限',
    expirationDate: '2026/12/31',
    conditions: [
      '適用於所有國內消費',
      '無最低消費金額限制',
      '自動回饋，無需登錄',
    ],
    reason: '穩定的備選方案，所有類別都有 2% 現金回饋。沒有上限或複雜的要求，任何消費都很可靠。',
    color: 'from-amber-500 to-amber-600',
  },
  {
    rank: 3,
    cardName: '富邦 momo 卡',
    channel: '線上購物',
    rewardRate: '1.5% 回饋',
    estimatedCashback: 'NT$ 22.5',
    monthlyCap: 'NT$ 800/月',
    expirationDate: '2026/06/30',
    conditions: [
      '僅適用於線上交易',
      '不包含外送服務',
      '需事先登錄線上購物類別',
    ],
    reason: '雖然專為線上購物設計，但此卡對實體餐飲消費的回饋較低。建議用於線上訂餐。',
    color: 'from-fuchsia-500 to-fuchsia-600',
    badges: ['即將到期'],
  },
];

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<'selection' | 'chat'>('selection');
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [showWelcome, setShowWelcome] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

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
    // Map scenarios to prompts
    const scenarioMap: Record<string, string> = {
      '🍽️ 餐廳用餐': '在餐廳用餐 1500 元，該用哪張卡？',
      '🏠  國內旅遊': '國內旅遊訂飯店 3000 元，推薦哪張卡？',
      '🗾 日本旅遊': '我在日本旅遊刷卡 5000 元，該用哪張卡？',
      '🛒  線上購物': '線上購物 2000 元，哪張卡回饋最高？',
      '✈️ 訂房/機票': '訂機票 12000 元，推薦哪張卡？',
      '🎬 娛樂消費': '看電影買票 800 元，該用哪張卡？',
    };

    const prompt = scenarioMap[scenario] || scenario;
    // Fill the input box but don't send
    setInputValue(prompt);
  };

  const handlePromptClick = (prompt: string) => {
    // Fill the input box but don't send
    setInputValue(prompt);
  };

  const handleSendMessage = (message: string) => {
    setShowWelcome(false);

    // Auto-detect and check cards mentioned in the message
    autoDetectAndCheckCards(message);

    const userMessage: Message = { role: 'user', content: message };
    setMessages((prev) => [...prev, userMessage]);

    // Simulate AI response with recommendations
    setTimeout(() => {
      const assistantMessage: Message = {
        role: 'assistant',
        content: `根據您的問題「${message}」以及您所選擇的信用卡，我已為您分析出最佳的付款選項。以下是依整體價值排序的前 3 名推薦：`,
        recommendations: mockRecommendations,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    }, 1000);
  };

  const autoDetectAndCheckCards = (message: string) => {
    // Define all available cards with their detection patterns
    const cardPatterns = [
      { id: '1', patterns: ['uniopen', 'uni open', 'uniopen 聯名卡'] },
      { id: '2', patterns: ['LINE Pay', 'LINE Pay 信用卡', 'line pay'] },
      { id: '3', patterns: ['foodpanda', 'food panda', 'foodpanda 聯名卡', '熊貓'] },
      { id: '4', patterns: ['ALL ME', 'all me', 'ALL ME 卡', 'allme'] },
      { id: '5', patterns: ['現金回饋御璽卡', '御璽卡', '御璽', '現金回饋御璽'] },
      { id: '6', patterns: ['寰遊美國運通卡', '寰遊', '美國運通', '運通卡'] },
      { id: '7', patterns: ['富邦 J 卡', 'J 卡', '富邦j卡', '富邦J'] },
      { id: '8', patterns: ['富邦 J Travel', 'J Travel', 'j travel', '富邦j travel'] },
      { id: '9', patterns: ['富邦 Costco', 'Costco', 'costco', '好市多'] },
      { id: '10', patterns: ['富邦鑽保卡', '鑽保卡', '鑽保'] },
      { id: '11', patterns: ['富邦 momo', 'momo 卡', 'momo', '富邦momo'] },
      { id: '12', patterns: ['富利生活卡', '富利生活', '富利'] },
      { id: '13', patterns: ['台灣大哥大 Open Possible', 'Open Possible', 'open possible', '台哥大'] },
      { id: '14', patterns: ['Home+', 'home+', 'Home+ 聯名卡'] },
      { id: '15', patterns: ['富邦數位生活卡', '數位生活卡', '數位生活'] },
      { id: '16', patterns: ['VISA 無限卡', '無限卡', 'visa 無限'] },
    ];

    const detectedCardIds: string[] = [];
    const lowerMessage = message.toLowerCase();

    // Check each card pattern against the message
    cardPatterns.forEach(({ id, patterns }) => {
      const isMatched = patterns.some(pattern => {
        const lowerPattern = pattern.toLowerCase();
        return lowerMessage.includes(lowerPattern) || message.includes(pattern);
      });

      if (isMatched) {
        detectedCardIds.push(id);
      }
    });

    // Auto-check detected cards if they're not already selected
    if (detectedCardIds.length > 0) {
      setSelectedCards(prev => {
        const newSelection = [...prev];
        detectedCardIds.forEach(cardId => {
          if (!newSelection.includes(cardId)) {
            newSelection.push(cardId);
          }
        });
        return newSelection;
      });
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
        onStart={handleStartChat}
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
          onScenarioClick={handleScenarioClick}
          isCollapsed={isSidebarCollapsed}
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