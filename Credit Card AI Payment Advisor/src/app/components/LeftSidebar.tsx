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

interface CreditCardItem {
  id: string;
  name: string;
  bank: string;
  lastFour: string;
  type: string;
  color: string;
}

const mockCards: CreditCardItem[] = [
  // 中國信託銀行 (CTBC) - Premium gold palette
  { id: '1', bank: '中國信託', name: 'uniopen 聯名卡', lastFour: '4321', type: '多功能', color: 'from-[#C9A961] to-[#B8935A]' },
  { id: '2', bank: '中國信託', name: 'LINE Pay 信用卡', lastFour: '8765', type: '行動支付', color: 'from-[#B76E79] to-[#A05D6A]' },
  { id: '3', bank: '中國信託', name: 'foodpanda 聯名卡', lastFour: '2468', type: '外送', color: 'from-[#D4AF77] to-[#C19A5B]' },
  { id: '4', bank: '中國信託', name: 'ALL ME 卡', lastFour: '1357', type: '現金回饋', color: 'from-[#C4A485] to-[#B39476]' },
  { id: '5', bank: '中國信託', name: '現金回饋御璽卡', lastFour: '9753', type: '現金回饋', color: 'from-[#CD7F32] to-[#B87333]' },
  { id: '6', bank: '中國信託', name: '寰遊美國運通卡', lastFour: '8642', type: '旅遊', color: 'from-[#E6D5B8] to-[#D4C4A8]' },
  // 富邦銀行 - Premium gold palette
  { id: '7', bank: '富邦銀行', name: '富邦 J 卡', lastFour: '3698', type: '現金回饋', color: 'from-[#C0C0C0] to-[#A8A8A8]' },
  { id: '8', bank: '富邦銀行', name: '富邦 J Travel 卡', lastFour: '7412', type: '旅遊', color: 'from-[#D4C5A9] to-[#C2B59B]' },
  { id: '9', bank: '富邦銀行', name: '富邦 Costco 聯名卡', lastFour: '9517', type: '購物', color: 'from-[#B8956A] to-[#A68355]' },
  { id: '10', bank: '富邦銀行', name: '富邦鑽保卡', lastFour: '3571', type: '保險', color: 'from-[#B8B0A0] to-[#A89F90]' },
  { id: '11', bank: '富邦銀行', name: '富邦 momo 卡', lastFour: '1593', type: '電商', color: 'from-[#C4A69D] to-[#B39587]' },
  { id: '12', bank: '富邦銀行', name: '富利生活卡', lastFour: '7539', type: '生活消費', color: 'from-[#B8A890] to-[#A89880]' },
  { id: '13', bank: '富邦銀行', name: '台灣大哥大 Open Possible 聯名卡', lastFour: '8520', type: '電信', color: 'from-[#E8DCC8] to-[#D8CCB8]' },
  // Additional cards to make 16 - Premium gold palette
  { id: '14', bank: '中國信託', name: 'Home+ 聯名卡', lastFour: '6284', type: '購物', color: 'from-[#D4B5A0] to-[#C4A590]' },
  { id: '15', bank: '富邦銀行', name: '富邦數位生活卡', lastFour: '4159', type: '數位消費', color: 'from-[#E8E0D0] to-[#D8D0C0]' },
  { id: '16', bank: '中國信託', name: 'VISA 無限卡', lastFour: '2637', type: '頂級', color: 'from-[#AAA9AD] to-[#9A999D]' },
];

interface LeftSidebarProps {
  selectedCards: string[];
  onCardToggle: (cardId: string) => void;
  onScenarioClick: (scenario: string) => void;
  isCollapsed: boolean;
}

export function LeftSidebar({ selectedCards, onCardToggle, onScenarioClick, isCollapsed }: LeftSidebarProps) {
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
              {selectedCards.length}/{mockCards.length}
            </Badge>
          </div>

          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
            {mockCards.map((card) => (
              <div
                key={card.id}
                className="flex items-start gap-3 p-3 rounded-lg border bg-white hover:shadow-sm transition-all cursor-pointer"
                style={{ borderColor: 'rgba(44, 62, 80, 0.08)' }}
                onClick={() => onCardToggle(card.id)}
              >
                <Checkbox
                  checked={selectedCards.includes(card.id)}
                  onCheckedChange={() => onCardToggle(card.id)}
                  className="mt-0.5"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <div className={`w-8 h-5 rounded bg-gradient-to-r ${card.color}`} />
                    <span className="font-medium text-xs truncate" style={{ color: '#2C3E50' }}>
                      {card.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px]" style={{ color: '#6B7280' }}>{card.bank}</span>
                    <span className="text-[10px]" style={{ color: '#9CA3AF' }}>•••• {card.lastFour}</span>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                      {card.type}
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