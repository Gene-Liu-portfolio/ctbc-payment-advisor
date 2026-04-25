import { Trophy, TrendingUp, Calendar, AlertCircle, CheckCircle2, ChevronLeft, ChevronRight } from 'lucide-react';
import { Badge } from './ui/badge';
import { useRef } from 'react';
import { Button } from './ui/button';

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

interface RecommendationCarouselProps {
  recommendations: Recommendation[];
}

export function RecommendationCarousel({ recommendations }: RecommendationCarouselProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const scrollAmount = 400;
      scrollContainerRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  };

  const getRankBadge = (rank: number) => {
    const badges = {
      1: { text: '最佳推薦', color: 'text-white', style: { background: 'linear-gradient(90deg, #D4AF37 0%, #F4D03F 100%)' } },
      2: { text: '次佳選擇', color: 'bg-gradient-to-r from-slate-300 to-slate-400 text-gray-900', style: {} },
      3: { text: '第三選項', color: 'bg-gradient-to-r from-orange-400 to-orange-500 text-white', style: {} },
    };

    return badges[rank as keyof typeof badges] || badges[3];
  };

  return (
    <div className="relative group">
      {/* Navigation Buttons */}
      <Button
        variant="outline"
        size="icon"
        className="absolute left-0 top-1/2 -translate-y-1/2 z-10 h-10 w-10 rounded-full bg-white shadow-lg opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={() => scroll('left')}
      >
        <ChevronLeft className="w-5 h-5" />
      </Button>
      
      <Button
        variant="outline"
        size="icon"
        className="absolute right-0 top-1/2 -translate-y-1/2 z-10 h-10 w-10 rounded-full bg-white shadow-lg opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={() => scroll('right')}
      >
        <ChevronRight className="w-5 h-5" />
      </Button>

      {/* Scrollable Container */}
      <div
        ref={scrollContainerRef}
        className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide snap-x snap-mandatory"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {recommendations.map((rec) => {
          const rankBadge = getRankBadge(rec.rank);
          
          return (
            <div
              key={rec.rank}
              className="flex-shrink-0 w-[380px] bg-white rounded-xl border overflow-hidden hover:shadow-md transition-all snap-start"
              style={{ borderColor: 'rgba(44, 62, 80, 0.08)' }}
            >
              {/* Header */}
              <div className="p-5 border-b" style={{ backgroundColor: '#FAFBFB', borderColor: 'rgba(44, 62, 80, 0.06)' }}>
                <div className="flex items-start justify-between mb-3">
                  <div
                    className={`${rankBadge.color} px-3 py-1.5 rounded-full flex items-center gap-1.5 text-sm font-medium`}
                    style={rankBadge.style}
                  >
                    <Trophy className="w-3.5 h-3.5" />
                    <span>{rankBadge.text}</span>
                  </div>
                  <Badge variant="outline" className="text-xs font-medium">
                    {rec.channel}
                  </Badge>
                </div>

                <div className="flex items-center gap-3">
                  <div className={`w-12 h-7 rounded-md bg-gradient-to-r ${rec.color}`} />
                  <h3 className="text-base font-semibold" style={{ color: '#2C3E50' }}>
                    {rec.cardName}
                  </h3>
                </div>
              </div>

              {/* Key Metrics */}
              <div className="p-5 grid grid-cols-2 gap-4" style={{ backgroundColor: 'rgba(0, 124, 124, 0.03)' }}>
                <div>
                  <p className="text-xs mb-1" style={{ color: '#6B7280' }}>回饋率</p>
                  <p className="text-lg font-semibold" style={{ color: '#007C7C' }}>{rec.rewardRate}</p>
                </div>
                <div>
                  <p className="text-xs mb-1" style={{ color: '#6B7280' }}>預估回饋</p>
                  <p className="text-lg font-semibold" style={{ color: '#007C7C' }}>{rec.estimatedCashback}</p>
                </div>
                <div>
                  <p className="text-xs mb-1" style={{ color: '#6B7280' }}>每月上限</p>
                  <p className="text-sm font-medium" style={{ color: '#2C3E50' }}>{rec.monthlyCap}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5" style={{ color: '#6B7280' }} />
                  <div>
                    <p className="text-xs" style={{ color: '#6B7280' }}>有效期限</p>
                    <p className="text-xs font-medium" style={{ color: '#2C3E50' }}>{rec.expirationDate}</p>
                  </div>
                </div>
              </div>

              {/* Conditions */}
              <div className="p-5 border-t bg-white" style={{ borderColor: 'rgba(44, 62, 80, 0.06)' }}>
                <div className="flex items-center gap-2 mb-3">
                  <AlertCircle className="w-3.5 h-3.5" style={{ color: '#007C7C' }} />
                  <h4 className="font-medium text-xs" style={{ color: '#2C3E50' }}>使用條件</h4>
                </div>
                <ul className="space-y-2">
                  {rec.conditions.slice(0, 3).map((condition, index) => (
                    <li key={index} className="flex items-start gap-2 text-xs" style={{ color: '#6B7280' }}>
                      <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: '#007C7C' }} />
                      <span className="line-clamp-2">{condition}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Recommendation Reason */}
              <div className="p-5 border-t" style={{ backgroundColor: 'rgba(0, 124, 124, 0.02)', borderColor: 'rgba(44, 62, 80, 0.06)' }}>
                <div className="flex items-start gap-2">
                  <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5" style={{ backgroundColor: '#007C7C' }}>
                    <span className="text-white text-[10px] font-bold">AI</span>
                  </div>
                  <div>
                    <h4 className="font-medium text-xs mb-1.5" style={{ color: '#2C3E50' }}>推薦原因</h4>
                    <p className="text-xs leading-relaxed line-clamp-3" style={{ color: '#6B7280' }}>{rec.reason}</p>
                  </div>
                </div>
              </div>

              {/* Additional Badges */}
              {rec.badges && rec.badges.length > 0 && (
                <div className="px-4 pb-4 flex gap-2 flex-wrap">
                  {rec.badges.map((badge, idx) => (
                    <Badge key={idx} variant="secondary" className="text-xs">
                      {badge}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
