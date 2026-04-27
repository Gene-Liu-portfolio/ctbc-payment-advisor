import { CreditCard, ArrowRight, Loader2 } from 'lucide-react';
import { Checkbox } from './ui/checkbox';
import type { CardMenuItem } from '../api';

// card_id → gradient color mapping
const CARD_COLORS: Record<string, string> = {
  ctbc_c_hanshin:      'from-[#C9A961] to-[#B8935A]',
  ctbc_c_uniopen:      'from-[#D4AF77] to-[#C19A5B]',
  ctbc_c_cs:           'from-[#CD7F32] to-[#B87333]',
  ctbc_c_linepay:      'from-[#B76E79] to-[#A05D6A]',
  ctbc_c_cal:          'from-[#E6D5B8] to-[#D4C4A8]',
  ctbc_c_cpc:          'from-[#C4A485] to-[#B39476]',
  fubon_c_j:           'from-[#C0C0C0] to-[#A8A8A8]',
  fubon_c_j_travel:    'from-[#D4C5A9] to-[#C2B59B]',
  fubon_c_costco:      'from-[#B8956A] to-[#A68355]',
  fubon_c_diamond:     'from-[#B8B0A0] to-[#A89F90]',
  fubon_c_momo:        'from-[#C4A69D] to-[#B39587]',
  fubon_b_lifestyle:   'from-[#B8A890] to-[#A89880]',
  fubon_c_twm:         'from-[#E8DCC8] to-[#D8CCB8]',
};

const BANK_NAMES: Record<string, string> = {
  ctbc:  '中國信託',
  fubon: '富邦銀行',
};

function getCardColor(cardId: string): string {
  return CARD_COLORS[cardId] ?? 'from-[#AAA9AD] to-[#9A999D]';
}

function getCardType(tags: string[]): string {
  return tags[0] ?? '信用卡';
}

interface CardSelectionPageProps {
  selectedCards: string[];
  onCardToggle: (cardId: string) => void;
  onStart: () => void;
  cards: CardMenuItem[];
  loading: boolean;
}

export function CardSelectionPage({ selectedCards, onCardToggle, onStart, cards, loading }: CardSelectionPageProps) {
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

        {/* Card Grid */}
        {!loading && (
          <div className="grid grid-cols-4 gap-4 mb-12">
            {cards.map((card) => (
              <div
                key={card.card_id}
                onClick={() => onCardToggle(card.card_id)}
                className="bg-white rounded-xl p-5 border transition-all cursor-pointer hover:shadow-md group"
                style={{
                  borderColor: selectedCards.includes(card.card_id) ? '#007C7C' : 'rgba(44, 62, 80, 0.08)',
                  borderWidth: selectedCards.includes(card.card_id) ? '2px' : '1px',
                  boxShadow: selectedCards.includes(card.card_id) ? '0 4px 16px rgba(0, 124, 124, 0.12)' : '0 1px 2px rgba(0, 0, 0, 0.04)',
                }}
              >
                <div className="flex items-start gap-3 mb-3">
                  <Checkbox
                    checked={selectedCards.includes(card.card_id)}
                    onCheckedChange={() => onCardToggle(card.card_id)}
                    className="mt-1"
                  />
                  <div className={`w-12 h-8 rounded-md bg-gradient-to-r ${getCardColor(card.card_id)} flex-shrink-0`} />
                </div>

                <div className="space-y-1">
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
