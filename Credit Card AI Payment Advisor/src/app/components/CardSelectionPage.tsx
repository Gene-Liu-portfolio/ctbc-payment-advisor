import { CreditCard, ArrowRight, Loader2 } from 'lucide-react';
import { Checkbox } from './ui/checkbox';
import type { CardMenuItem } from '../api';
import { CARD_IMAGES, BANK_NAMES, getCardColor, getCardType } from '../../constants/cardConfig';

interface CardSelectionPageProps {
  selectedCards: string[];
  onCardToggle: (cardId: string) => void;
  onSelectAll: (cardIds: string[]) => void;
  onStart: () => void;
  cards: CardMenuItem[];
  loading: boolean;
}

export function CardSelectionPage({ selectedCards, onCardToggle, onSelectAll, onStart, cards, loading }: CardSelectionPageProps) {
  const isAllSelected = cards.length > 0 && selectedCards.length === cards.length;
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8" style={{ backgroundColor: '#F7F9F8' }}>
      <div className="w-full max-w-6xl">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl mb-6 shadow-lg" style={{ background: 'linear-gradient(135deg, #007C7C 0%, #005c5c 100%)' }}>
            <CreditCard className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold mb-3" style={{ color: '#2C3E50' }}>
            選擇您持有的信用卡
          </h1>
          <p className="text-lg" style={{ color: '#6B7280' }}>
            請勾選您目前擁有的信用卡，系統將為您推薦最適合的付款方式
          </p>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin" style={{ color: '#007C7C' }} />
            <span className="ml-3 text-lg" style={{ color: '#6B7280' }}>載入卡片資料中...</span>
          </div>
        )}

        {/* Card Grid 區域 */}
        {!loading && (
          <div className="grid grid-cols-4 gap-4 mb-12">
            
            {/* 👇 這是特製的「全選卡片」，放在網格的第一格 */}
            <div
              onClick={() => {
                if (isAllSelected) {
                  onSelectAll([]); // 如果已經全選了，就清空
                } else {
                  onSelectAll(cards.map(c => c.card_id)); // 否則就全選
                }
              }}
              className="bg-white rounded-xl p-5 border transition-all cursor-pointer hover:shadow-md flex flex-col justify-center"
              style={{
                borderColor: isAllSelected ? '#007C7C' : 'rgba(44, 62, 80, 0.08)',
                borderWidth: isAllSelected ? '2px' : '1px',
                boxShadow: isAllSelected ? '0 4px 16px rgba(0, 124, 124, 0.12)' : '0 1px 2px rgba(0, 0, 0, 0.04)',
                backgroundColor: isAllSelected ? 'rgba(0, 124, 124, 0.02)' : '#ffffff'
              }}
            >
              <div className="flex items-center gap-3 mb-3">
                <Checkbox
                  checked={isAllSelected}
                  // 點擊 Checkbox 也是觸發外層的 onClick
                  className="mt-0.5 relative z-10" 
                />
                <h3 className="font-semibold text-base" style={{ color: '#2C3E50' }}>
                  {isAllSelected ? '取消全選' : '全選所有卡片'}
                </h3>
              </div>
              <div className="mt-auto">
                <div className="inline-block px-3 py-1 rounded-full text-xs font-medium" style={{ backgroundColor: 'rgba(0, 124, 124, 0.1)', color: '#007C7C' }}>
                  已選擇 {selectedCards.length} / {cards.length}
                </div>
              </div>
            </div>

            {/* 👇 原本的卡片列表，接在全選卡片後面 */}
            {cards.map((card) => (
              <div
                key={card.card_id}
                onClick={() => onCardToggle(card.card_id)}
                className="bg-white rounded-xl p-5 border transition-all cursor-pointer hover:shadow-md group relative overflow-hidden"
                style={{
                  borderColor: selectedCards.includes(card.card_id) ? '#007C7C' : 'rgba(44, 62, 80, 0.08)',
                  borderWidth: selectedCards.includes(card.card_id) ? '2px' : '1px',
                  boxShadow: selectedCards.includes(card.card_id) ? '0 4px 16px rgba(0, 124, 124, 0.12)' : '0 1px 2px rgba(0, 0, 0, 0.04)',
                }}
              >
                <div className="flex items-start gap-3 mb-3">
                  <Checkbox
                  checked={isAllSelected}
                  onClick={(e) => e.stopPropagation()} 
                  onCheckedChange={(checked) => {
                    if (checked) {
                      onSelectAll(cards.map(c => c.card_id)); // 打勾：全選
                    } else {
                      onSelectAll([]); // 取消打勾：清空
                    }
                  }}
                  className="mt-0.5 relative z-10 cursor-pointer" 
                  />
                  
                  {/* 真實圖片渲染邏輯保持不變 */}
                  <div className="w-[56px] h-[36px] rounded flex-shrink-0 relative overflow-hidden shadow-sm border border-gray-100">
                    {CARD_IMAGES[card.card_id] ? (
                      <img 
                        src={CARD_IMAGES[card.card_id]} 
                        alt={card.card_name} 
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className={`w-full h-full bg-gradient-to-r ${getCardColor(card.card_id)}`} />
                    )}
                  </div>
                </div>

                <div className="space-y-1 relative z-10">
                  <h3 className="font-semibold text-sm leading-tight" style={{ color: '#2C3E50' }}>
                    {card.card_name}
                  </h3>
                  <p className="text-xs" style={{ color: '#6B7280' }}>
                    {BANK_NAMES[card.bank_id] ?? card.bank_id}
                  </p>
                  <div className="inline-block px-2 py-0.5 rounded-full text-xs" style={{ backgroundColor: '#F0F2F1', color: '#2C3E50' }}>
                    {getCardType(card.tags)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Start Button */}
        <div className="text-center">
          <button
            onClick={onStart}
            disabled={selectedCards.length === 0 || loading}
            className="inline-flex items-center gap-3 px-8 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: selectedCards.length > 0 ? '#007C7C' : '#d4d4d4',
              color: '#ffffff',
            }}
            onMouseEnter={(e) => {
              if (selectedCards.length > 0) {
                e.currentTarget.style.backgroundColor = '#005c5c';
              }
            }}
            onMouseLeave={(e) => {
              if (selectedCards.length > 0) {
                e.currentTarget.style.backgroundColor = '#007C7C';
              }
            }}
          >
            <span>開始使用</span>
            <ArrowRight className="w-5 h-5" />
          </button>

          {selectedCards.length > 0 && (
            <p className="mt-4 text-sm" style={{ color: '#6B7280' }}>
              已選擇 {selectedCards.length} 張信用卡
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
