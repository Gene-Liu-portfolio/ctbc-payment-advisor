import { Bot, User } from 'lucide-react';
import { RecommendationCarousel } from './RecommendationCarousel';

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

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  recommendations?: Recommendation[];
}

export function ChatMessage({ role, content, recommendations }: ChatMessageProps) {
  const isUser = role === 'user';

  return (
    <div className="space-y-4">
      <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
        {!isUser && (
          <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: 'linear-gradient(135deg, #007C7C 0%, #005c5c 100%)' }}>
            <Bot className="w-4 h-4 text-white" />
          </div>
        )}

        <div
          className={`max-w-[70%] rounded-xl px-4 py-3 ${
            isUser
              ? 'text-white'
              : 'bg-white border'
          }`}
          style={isUser ? { backgroundColor: '#007C7C' } : { borderColor: 'rgba(44, 62, 80, 0.08)', color: '#2C3E50' }}
        >
          <p className="text-sm leading-relaxed">{content}</p>
        </div>

        {isUser && (
          <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ backgroundColor: '#E5E7EB' }}>
            <User className="w-4 h-4" style={{ color: '#6B7280' }} />
          </div>
        )}
      </div>

      {/* Recommendations Carousel - Only for assistant messages */}
      {!isUser && recommendations && recommendations.length > 0 && (
        <div className="ml-11">
          <div className="mb-4">
            <h3 className="text-sm font-semibold" style={{ color: '#2C3E50' }}>
              💳 推薦信用卡
            </h3>
          </div>
          <RecommendationCarousel recommendations={recommendations} />
        </div>
      )}
    </div>
  );
}