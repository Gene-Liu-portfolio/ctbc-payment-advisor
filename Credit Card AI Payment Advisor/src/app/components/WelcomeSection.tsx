import { Sparkles } from 'lucide-react';

interface WelcomeSectionProps {
  onPromptClick: (prompt: string) => void;
}

const examplePrompts = [
  "在餐廳用餐 1500 元，該用哪張卡？",
  "日本訂飯店最推薦哪張卡？",
  "線上購物 5000 元的最佳信用卡",
  "比較海外消費的回饋優惠",
];

export function WelcomeSection({ onPromptClick }: WelcomeSectionProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-8">
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6" style={{ background: 'linear-gradient(135deg, #007C7C 0%, #005c5c 100%)' }}>
        <Sparkles className="w-8 h-8 text-white" />
      </div>

      <h2 className="text-3xl font-semibold mb-3" style={{ color: '#2C3E50' }}>
        歡迎使用智能刷卡顧問
      </h2>
      <p className="text-center max-w-md mb-12" style={{ color: '#6B7280' }}>
        透過 AI 智能分析，為您的每筆消費推薦最適合的信用卡，
        讓您輕鬆享有最高回饋與優惠。
      </p>

      <div className="w-full max-w-2xl">
        <p className="text-sm font-medium mb-4" style={{ color: '#2C3E50' }}>試試看：</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {examplePrompts.map((prompt, index) => (
            <button
              key={index}
              onClick={() => onPromptClick(prompt)}
              className="p-5 rounded-xl border bg-white text-left transition-all group"
              style={{ borderColor: 'rgba(44, 62, 80, 0.08)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#007C7C';
                e.currentTarget.style.backgroundColor = 'rgba(0, 124, 124, 0.02)';
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 124, 124, 0.08)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(44, 62, 80, 0.08)';
                e.currentTarget.style.backgroundColor = '#ffffff';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <p className="text-sm group-hover:text-[#007C7C] transition-colors" style={{ color: '#2C3E50' }}>
                {prompt}
              </p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}