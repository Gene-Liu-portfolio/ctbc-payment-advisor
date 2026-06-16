import type { SearchResult } from './api';

export interface Recommendation {
  cardId: string;
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

const RANK_COLORS = [
  'from-green-500 to-green-600',
  'from-amber-500 to-amber-600',
  'from-fuchsia-500 to-fuchsia-600',
];

export function toRecommendation(result: SearchResult, rank: number, channel: string): Recommendation {
  const rate = result.cashback_rate != null ? `${(result.cashback_rate * 100).toFixed(1)}%` : '—';
  const estimated = result.estimated_cashback != null
    ? `NT$ ${result.estimated_cashback.toLocaleString()}`
    : '—';
  const cap = result.max_cashback_per_period != null
    ? `NT$ ${result.max_cashback_per_period.toLocaleString()}/期`
    : '無上限';
  const badges: string[] = [];
  if (rank === 1) badges.push('最高回饋');
  if (result.expiring_soon) badges.push('即將到期');
  if (result.is_fallback) badges.push('一般消費回饋');

  const conditions: string[] = [];
  if (result.conditions) conditions.push(result.conditions);
  if (result.cashback_description) conditions.push(result.cashback_description);
  for (const highlight of result.detail_highlights ?? []) {
    if (highlight && !conditions.includes(highlight)) conditions.push(highlight);
  }
  for (const alert of result.promotion_alerts ?? []) {
    if (alert && !conditions.includes(alert)) conditions.push(`活動提醒：${alert}`);
  }

  return {
    cardId: result.card_id,
    rank,
    cardName: result.card_name,
    channel,
    rewardRate: `${rate} 回饋`,
    estimatedCashback: estimated,
    monthlyCap: cap,
    expirationDate: result.valid_end ?? '長期有效',
    conditions,
    reason: result.reason || result.cashback_description || `此卡在「${channel}」通路的回饋率為 ${rate}。`,
    color: RANK_COLORS[rank - 1] ?? RANK_COLORS[2],
    badges: badges.length > 0 ? badges : undefined,
  };
}

export function recommendationsFromStructuredData(
  data: {
    recommendations?: Array<{
      channel_name?: string;
      best_options?: SearchResult[];
    }>;
  } | null | undefined,
): Recommendation[] {
  const recommendations: Recommendation[] = [];
  const maxCards = 4;

  for (const rec of data?.recommendations ?? []) {
    const channelName = rec.channel_name ?? '推薦結果';
    for (const option of rec.best_options ?? []) {
      if (recommendations.length >= maxCards) return recommendations;
      recommendations.push(toRecommendation(option, recommendations.length + 1, channelName));
    }
  }

  return recommendations;
}
