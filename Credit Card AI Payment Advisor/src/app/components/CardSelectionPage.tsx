import { useState } from 'react';
import { CreditCard, ArrowRight } from 'lucide-react';
import { Checkbox } from './ui/checkbox';

interface CreditCardItem {
  id: string;
  name: string;
  bank: string;
  type: string;
  color: string;
}

const allCards: CreditCardItem[] = [
  // 中國信託銀行 (CTBC) - Premium gold palette
  { id: '1', bank: '中國信託', name: 'uniopen 聯名卡', type: '多功能', color: 'from-[#C9A961] to-[#B8935A]' }, // Champagne gold
  { id: '2', bank: '中國信託', name: 'LINE Pay 信用卡', type: '行動支付', color: 'from-[#B76E79] to-[#A05D6A]' }, // Rose gold
  { id: '3', bank: '中國信託', name: 'foodpanda 聯名卡', type: '外送', color: 'from-[#D4AF77] to-[#C19A5B]' }, // Light gold
  { id: '4', bank: '中國信託', name: 'ALL ME 卡', type: '現金回饋', color: 'from-[#C4A485] to-[#B39476]' }, // Warm beige gold
  { id: '5', bank: '中國信託', name: '現金回饋御璽卡', type: '現金回饋', color: 'from-[#CD7F32] to-[#B87333]' }, // Bronze gold
  { id: '6', bank: '中國信託', name: '寰遊美國運通卡', type: '旅遊', color: 'from-[#E6D5B8] to-[#D4C4A8]' }, // Cream gold
  // 富邦銀行 - Premium gold palette
  { id: '7', bank: '富邦銀行', name: '富邦 J 卡', type: '現金回饋', color: 'from-[#C0C0C0] to-[#A8A8A8]' }, // Soft platinum
  { id: '8', bank: '富邦銀行', name: '富邦 J Travel 卡', type: '旅遊', color: 'from-[#D4C5A9] to-[#C2B59B]' }, // Pale gold
  { id: '9', bank: '富邦銀行', name: '富邦 Costco 聯名卡', type: '購物', color: 'from-[#B8956A] to-[#A68355]' }, // Antique gold
  { id: '10', bank: '富邦銀行', name: '富邦鑽保卡', type: '保險', color: 'from-[#B8B0A0] to-[#A89F90]' }, // Warm gray gold
  { id: '11', bank: '富邦銀行', name: '富邦 momo 卡', type: '電商', color: 'from-[#C4A69D] to-[#B39587]' }, // Dusty rose gold
  { id: '12', bank: '富邦銀行', name: '富利生活卡', type: '生活消費', color: 'from-[#B8A890] to-[#A89880]' }, // Sage gold
  { id: '13', bank: '富邦銀行', name: '台灣大哥大 Open Possible 聯名卡', type: '電信', color: 'from-[#E8DCC8] to-[#D8CCB8]' }, // Pearl gold
  // Additional cards to make 16 - Premium gold palette
  { id: '14', bank: '中國信託', name: 'Home+ 聯名卡', type: '購物', color: 'from-[#D4B5A0] to-[#C4A590]' }, // Blush gold
  { id: '15', bank: '富邦銀行', name: '富邦數位生活卡', type: '數位消費', color: 'from-[#E8E0D0] to-[#D8D0C0]' }, // Ivory gold
  { id: '16', bank: '中國信託', name: 'VISA 無限卡', type: '頂級', color: 'from-[#AAA9AD] to-[#9A999D]' }, // Silver platinum
];

interface CardSelectionPageProps {
  selectedCards: string[];
  onCardToggle: (cardId: string) => void;
  onStart: () => void;
}

export function CardSelectionPage({ selectedCards, onCardToggle, onStart }: CardSelectionPageProps) {
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

        {/* Card Grid */}
        <div className="grid grid-cols-4 gap-4 mb-12">
          {allCards.map((card) => (
            <div
              key={card.id}
              onClick={() => onCardToggle(card.id)}
              className="bg-white rounded-xl p-5 border transition-all cursor-pointer hover:shadow-md group"
              style={{
                borderColor: selectedCards.includes(card.id) ? '#007C7C' : 'rgba(44, 62, 80, 0.08)',
                borderWidth: selectedCards.includes(card.id) ? '2px' : '1px',
                boxShadow: selectedCards.includes(card.id) ? '0 4px 16px rgba(0, 124, 124, 0.12)' : '0 1px 2px rgba(0, 0, 0, 0.04)',
              }}
            >
              <div className="flex items-start gap-3 mb-3">
                <Checkbox
                  checked={selectedCards.includes(card.id)}
                  onCheckedChange={() => onCardToggle(card.id)}
                  className="mt-1"
                />
                <div className={`w-12 h-8 rounded-md bg-gradient-to-r ${card.color} flex-shrink-0`} />
              </div>

              <div className="space-y-1">
                <h3 className="font-semibold text-sm leading-tight" style={{ color: '#2C3E50' }}>
                  {card.name}
                </h3>
                <p className="text-xs" style={{ color: '#6B7280' }}>
                  {card.bank}
                </p>
                <div className="inline-block px-2 py-0.5 rounded-full text-xs" style={{ backgroundColor: '#F0F2F1', color: '#2C3E50' }}>
                  {card.type}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Start Button */}
        <div className="text-center">
          <button
            onClick={onStart}
            disabled={selectedCards.length === 0}
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
