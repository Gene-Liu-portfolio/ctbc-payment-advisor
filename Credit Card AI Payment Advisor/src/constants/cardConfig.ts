// 1. 真實卡片圖片的路徑對應表
export const CARD_IMAGES: Record<string, string> = {
  ctbc_c_linepay: '/cards/ctbc_linepay.png',
  ctbc_c_uniopen: '/cards/ctbc_uniopen.png',
  ctbc_c_hanshin: '/cards/ctbc_hanshin.png',
  ctbc_c_cs: '/cards/ctbc_cs.png',
  ctbc_c_cal: '/cards/ctbc_cal.png',
  ctbc_c_cpc: '/cards/ctbc_cpc.png',
  fubon_c_j: '/cards/fubon_j.gif',
  fubon_c_j_travel: '/cards/fubon_j_travel.png',
  fubon_c_costco: '/cards/fubon_costco.png',
  fubon_c_diamond: '/cards/fubon_diamond.png',
  fubon_c_momo: '/cards/fubon_momo.png',
  fubon_b_lifestyle: '/cards/fubon_lifestyle.png',
  fubon_c_twm: '/cards/fubon_twm.png',
};

// 2. 原本的漸層色對應表 (當作沒有圖片時的備用方案)
export const CARD_COLORS: Record<string, string> = {
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

// 3. 銀行名稱對應表
export const BANK_NAMES: Record<string, string> = {
  ctbc:  '中國信託',
  fubon: '富邦銀行',
};

// 4. 輔助函式：取得卡片顏色
export function getCardColor(cardId: string): string {
  return CARD_COLORS[cardId] ?? 'from-[#AAA9AD] to-[#9A999D]';
}

// 5. 輔助函式：取得卡片類型標籤
export function getCardType(tags: string[]): string {
  return tags[0] ?? '信用卡';
}