import { Globe, RotateCcw, Menu, Sparkles } from 'lucide-react';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';

interface TopNavigationProps {
  onToggleSidebar: () => void;
  isSidebarCollapsed: boolean;
  agentMode: boolean;
  onAgentModeChange: (next: boolean) => void;
}

export function TopNavigation({
  onToggleSidebar,
  isSidebarCollapsed: _isSidebarCollapsed,
  agentMode,
  onAgentModeChange,
}: TopNavigationProps) {
  return (
    <div className="h-16 border-b bg-white flex items-center justify-between px-6" style={{ borderColor: 'rgba(44, 62, 80, 0.08)' }}>
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleSidebar}
          className="h-10 w-10"
        >
          <Menu className="w-5 h-5" style={{ color: '#2C3E50' }} />
        </Button>

        <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #007C7C 0%, #005c5c 100%)' }}>
          <span className="text-white font-bold text-lg">智</span>
        </div>
        <div>
          <h1 className="font-semibold text-lg" style={{ color: '#2C3E50' }}>智能刷卡顧問</h1>
          <p className="text-xs" style={{ color: '#6B7280' }}>AI 信用卡推薦系統</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <label
          className="flex items-center gap-2 px-3 py-1.5 rounded-full border cursor-pointer transition-colors"
          style={{
            borderColor: agentMode ? '#007C7C' : 'rgba(44, 62, 80, 0.15)',
            backgroundColor: agentMode ? '#F0FAFA' : 'transparent',
          }}
          title="開啟後，由 Claude 自行決定要呼叫哪些 MCP 工具（較慢但更靈活）"
        >
          <Sparkles
            className="w-4 h-4"
            style={{ color: agentMode ? '#007C7C' : '#6B7280' }}
          />
          <span
            className="text-xs font-medium"
            style={{ color: agentMode ? '#007C7C' : '#6B7280' }}
          >
            Agent 模式
          </span>
          <Switch
            checked={agentMode}
            onCheckedChange={onAgentModeChange}
            className="data-[state=checked]:bg-[#007C7C]"
          />
        </label>

        <Button variant="ghost" size="sm" className="gap-2">
          <Globe className="w-4 h-4" />
          <span>繁中</span>
        </Button>

        <Button variant="outline" size="sm" className="gap-2">
          <RotateCcw className="w-4 h-4" />
          <span>重置</span>
        </Button>

        <Avatar className="w-9 h-9">
          <AvatarImage src="https://api.dicebear.com/7.x/avataaars/svg?seed=user" />
          <AvatarFallback>用戶</AvatarFallback>
        </Avatar>
      </div>
    </div>
  );
}
