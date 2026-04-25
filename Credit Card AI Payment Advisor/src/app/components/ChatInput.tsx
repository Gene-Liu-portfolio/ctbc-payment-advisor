import { useState, useRef } from 'react';
import { Send, Plus, Image as ImageIcon, Paperclip, Mic } from 'lucide-react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  value?: string;
  onChange?: (value: string) => void;
}

export function ChatInput({ onSend, disabled, value: externalValue, onChange }: ChatInputProps) {
  const [internalInput, setInternalInput] = useState('');
  const [isComposing, setIsComposing] = useState(false);

  const input = externalValue !== undefined ? externalValue : internalInput;
  const setInput = onChange || setInternalInput;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !disabled && !isComposing) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Only submit if Enter is pressed, NOT during IME composition, and without Shift
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleCompositionStart = () => {
    setIsComposing(true);
  };

  const handleCompositionEnd = () => {
    setIsComposing(false);
  };

  return (
    <form onSubmit={handleSubmit} className="p-6 bg-white border-t" style={{ borderColor: 'rgba(44, 62, 80, 0.08)' }}>
      <div className="max-w-4xl mx-auto">
        <div className="flex items-end gap-3">
          {/* Plus Button with Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="h-[52px] w-[52px] rounded-xl flex-shrink-0 border bg-white hover:bg-gray-50 inline-flex items-center justify-center transition-colors"
                style={{ borderColor: 'rgba(44, 62, 80, 0.12)' }}
              >
                <Plus className="w-5 h-5" style={{ color: '#2C3E50' }} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-48">
              <DropdownMenuItem className="gap-2 cursor-pointer">
                <ImageIcon className="w-4 h-4" />
                <span>上傳圖片</span>
              </DropdownMenuItem>
              <DropdownMenuItem className="gap-2 cursor-pointer">
                <Paperclip className="w-4 h-4" />
                <span>上傳檔案</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Input Field */}
          <div className="flex-1 relative">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onCompositionStart={handleCompositionStart}
              onCompositionEnd={handleCompositionEnd}
              placeholder="請輸入您的消費情境，例如：我在日本旅遊刷卡 5000 元"
              className="resize-none min-h-[52px] max-h-[120px] rounded-xl pr-24 text-sm border"
              style={{ borderColor: 'rgba(44, 62, 80, 0.12)' }}
              disabled={disabled}
            />

            {/* Microphone Button */}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute right-12 bottom-2 h-9 w-9 rounded-lg hover:bg-gray-50"
            >
              <Mic className="w-4 h-4" style={{ color: '#6B7280' }} />
            </Button>

            {/* Send Button Inside Input */}
            <Button
              type="submit"
              disabled={!input.trim() || disabled}
              size="icon"
              className="absolute right-2 bottom-2 h-9 w-9 rounded-lg disabled:bg-gray-300"
              style={{
                backgroundColor: !input.trim() || disabled ? undefined : '#007C7C',
              }}
              onMouseEnter={(e) => {
                if (input.trim() && !disabled) {
                  e.currentTarget.style.backgroundColor = '#005c5c';
                }
              }}
              onMouseLeave={(e) => {
                if (input.trim() && !disabled) {
                  e.currentTarget.style.backgroundColor = '#007C7C';
                }
              }}
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <p className="text-xs mt-3 ml-[62px]" style={{ color: '#9CA3AF' }}>
          按 Enter 送出，Shift + Enter 換行
        </p>
      </div>
    </form>
  );
}