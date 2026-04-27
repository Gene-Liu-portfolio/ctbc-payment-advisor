import { useState } from 'react';
import { CreditCard, SlidersHorizontal, ChevronDown } from 'lucide-react';
import { Checkbox } from './ui/checkbox';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Input } from './ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import type { CardMenuItem } from '../api';

// Reuse the same color map from CardSelectionPage
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

interface LeftSidebarProps {
  selectedCards: string[];
  onCardToggle: (cardId: string) => void;
  onScenarioClick: (scenario: string) => void;
  isCollapsed: boolean;
  cards: CardMenuItem[];
}

export function LeftSidebar({ selectedCards, onCardToggle, onScenarioClick, isCollapsed, cards }: LeftSidebarProps) {
  const [showFilters, setShowFilters] = useState(true);

  if (isCollapsed) return null;

  return (
    <div className="w-80 h-full bg-white border-r flex flex-col overflow-hidden" style={{ borderColor: 'rgba(44, 62, 80, 0.08)' }}>
      <div className="flex-1 overflow-y-auto">
        {/* Owned Credit Cards */}
        <div className="p-5 border-b" style={{ borderColor: 'rgba(44, 62, 80, 0.06)' }}>
          <div className="flex items-center gap-2 mb-3">
            <CreditCard className="w-4 h-4" style={{ color: '#007C7C' }} />
            <h2 className="font-semibold text-sm" style={{ color: '#2C3E50' }}>我的信用卡</h2>
            <Badge variant="secondary" className="ml-auto text-xs">
              {selectedCards.length}/{cards.length}
            </Badge>
          </div>

          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
            {cards.map((card) => (
              <div
                key={card.card_id}
                className="flex items-start gap-3 p-3 rounded-lg border bg-white hover:shadow-sm transition-all cursor-pointer"
                style={{ borderColor: 'rgba(44, 62, 80, 0.08)' }}
                onClick={() => onCardToggle(card.card_id)}
              >
                <Checkbox
                  checked={selectedCards.includes(card.card_id)}
                  onCheckedChange={() => onCardToggle(card.card_id)}
                  className="mt-0.5"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <div className={`w-8 h-5 rounded bg-gradient-to-r ${CARD_COLORS[card.card_id] ?? 'from-[#AAA9AD] to-[#9A999D]'}`} />
                    <span className="font-medium text-xs truncate" style={{ color: '#2C3E50' }}>
                      {card.card_name}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px]" style={{ color: '#6B7280' }}>
                      {BANK_NAMES[card.bank_id] ?? card.bank_id}
                    </span>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                      {card.tags[0] ?? '信用卡'}
                    </Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Advanced Filters */}
        <div className="p-5 border-t" style={{ borderColor: 'rgba(44, 62, 80, 0.06)' }}>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center justify-between w-full mb-4"
          >
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4" style={{ color: '#007C7C' }} />
              <h2 className="font-semibold text-sm" style={{ color: '#2C3E50' }}>進階篩選</h2>
            </div>
            <ChevronDown
              className={`w-4 h-4 text-gray-500 transition-transform ${
                showFilters ? 'rotate-180' : ''
              }`}
            />
          </button>

          {showFilters && (
            <div className="space-y-4">
              <div>
                <Label className="text-xs mb-2 block" style={{ color: '#2C3E50' }}>消費金額</Label>
                <Input type="number" placeholder="請輸入金額" className="h-10" />
              </div>

              <div>
                <Label className="text-xs mb-2 block" style={{ color: '#2C3E50' }}>交易類型</Label>
                <Select defaultValue="all">
                  <SelectTrigger className="h-10">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部交易</SelectItem>
                    <SelectItem value="domestic">國內交易</SelectItem>
                    <SelectItem value="overseas">海外交易</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-xs mb-2 block" style={{ color: '#2C3E50' }}>排序方式</Label>
                <Select defaultValue="reward">
                  <SelectTrigger className="h-10">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="reward">最高回饋</SelectItem>
                    <SelectItem value="cashback">最多現金回饋</SelectItem>
                    <SelectItem value="points">最多紅利點數</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button variant="outline" className="w-full h-10 text-sm">
                套用篩選
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}