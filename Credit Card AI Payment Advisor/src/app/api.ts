/**
 * api.ts
 * ------
 * REST API client for CTBC Payment Advisor MCP Server.
 * All calls go to /api/* which Vite proxy forwards to the MCP Server.
 */

export interface CardMenuItem {
  card_id: string;
  card_name: string;
  bank_id: string;
  tags: string[];
}

export interface SearchResult {
  rank?: number;
  card_id: string;
  card_name: string;
  cashback_rate: number | null;
  cashback_type: string;
  cashback_description: string;
  estimated_cashback: number | null;
  max_cashback_per_period: number | null;
  valid_end: string | null;
  expiring_soon: boolean;
  conditions: string;
  data_source: string;
  is_fallback: boolean;
  merchant?: string;
  payment_method?: string;
  reason?: string;
}

export interface SearchResponse {
  channel_id: string;
  channel_name: string;
  query: string;
  amount: number;
  merchant_hint: string;
  results: SearchResult[];
  error: string | null;
}

export interface RecommendResponse {
  scenario: string;
  parsed: {
    channels: { name: string; channel_id: string }[];
    amount: number;
  };
  recommendations: {
    channel_name: string;
    channel_id: string;
    best_options: SearchResult[];
  }[];
  off_topic_message?: string;
  error: string | null;
}

/** GET /api/cards */
export async function fetchCards(): Promise<CardMenuItem[]> {
  const res = await fetch('/api/cards');
  const data = await res.json();
  return data.cards ?? [];
}

/** POST /api/search */
export async function searchByChannel(
  channel: string,
  cardsOwned: string[],
  amount: number = 0,
  topK: number = 3,
): Promise<SearchResponse> {
  const res = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      channel,
      cards_owned: cardsOwned,
      amount,
      top_k: topK,
    }),
  });
  return res.json();
}

/** POST /api/recommend */
export async function recommendPayment(
  scenario: string,
  cardsOwned: string[],
): Promise<RecommendResponse> {
  const res = await fetch('/api/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario, cards_owned: cardsOwned }),
  });
  return res.json();
}
