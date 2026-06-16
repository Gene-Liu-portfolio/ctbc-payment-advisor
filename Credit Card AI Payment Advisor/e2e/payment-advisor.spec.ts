import { expect, test, type Page } from '@playwright/test';

test('card selection loads cards with bank names', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: '選擇您持有的信用卡' })).toBeVisible();
  await expect(page.getByText('LINE Pay信用卡')).toBeVisible();
  await expect(page.getByText('富邦J卡')).toBeVisible();
  await expect(page.getByText('中國信託').first()).toBeVisible();
  await expect(page.getByText('富邦銀行').first()).toBeVisible();
  await expect(page.getByText('undefined')).toHaveCount(0);
});

test('general recommendation shows non-cash calculation trace', async ({ page }) => {
  await mockStructuredRecommendation(page, [
    { type: 'thinking_start' },
    { type: 'tool_call', tool: 'parse_scenario', status: 'calling', label: '解析消費情境中...' },
    {
      type: 'tool_call',
      tool: 'parse_scenario',
      status: 'done',
      label: '識別通路：家樂福，金額：NT$ 2,000',
      channels: ['家樂福'],
      amount: 2000,
    },
    {
      type: 'tool_call',
      tool: 'search_by_channel',
      status: 'calling',
      label: '查詢「超市／量販」通路最佳卡片...',
      channel: '超市／量販',
    },
    {
      type: 'tool_call',
      tool: 'search_by_channel',
      status: 'done',
      label: '「超市／量販」找到 1 張卡，最高回饋：LINE Pay信用卡',
      channel: '超市／量販',
      result_count: 1,
    },
    {
      type: 'tool_result',
      tool: 'search_by_channel',
      status: 'success',
      summary: '回傳 1 張候選卡，最高回饋為 LINE Pay信用卡',
      data: {},
    },
    {
      type: 'mcp_calculation',
      tool: 'search_by_channel',
      channel: '超市／量販',
      candidates: [
        {
          card_id: 'ctbc_c_linepay',
          card_name: 'LINE Pay信用卡',
          cashback_rate: 0.05,
          estimated_cashback: null,
          formula: '非現金回饋不換算 NT$ 預估',
          data_source: 'microsite',
          is_fallback: false,
        },
      ],
      winner: {
        card_id: 'ctbc_c_linepay',
        card_name: 'LINE Pay信用卡',
        cashback_rate: 0.05,
        estimated_cashback: null,
        formula: '非現金回饋不換算 NT$ 預估',
      },
      ranking_summary: 'LINE Pay信用卡 —',
    },
    { type: 'thinking_done', elapsed_seconds: 0.2 },
    {
      type: 'result',
      data: {
        scenario: '去家樂福買菜 2000 元',
        parsed: { channels: [{ name: '家樂福', channel_id: 'supermarket' }], amount: 2000 },
        amount_info: { amount_display: 'NT$ 2,000' },
        recommendations: [
          {
            channel_name: '超市／量販',
            channel_id: 'supermarket',
            best_options: [
              searchResult({
                card_id: 'ctbc_c_linepay',
                card_name: 'LINE Pay信用卡',
                cashback_rate: 0.05,
                cashback_type: 'points',
                estimated_cashback: null,
                cashback_description: 'LINE POINTS 5% 回饋',
                conditions: 'LINE POINTS 非現金回饋',
              }),
            ],
          },
        ],
        error: null,
      },
    },
  ]);

  await chooseCardsAndStart(page, ['LINE Pay信用卡']);
  await sendChatMessage(page, '去家樂福買菜 2000 元');

  await expect(page.getByText('LINE Pay信用卡').last()).toBeVisible();
  await expect(page.getByText('—').first()).toBeVisible();
  await ensurePanelTextVisible(page, '非現金回饋不換算 NT$ 預估');
});

test('general recommendation shows high speed rail best card and formula', async ({ page }) => {
  await mockStructuredRecommendation(page, [
    { type: 'thinking_start' },
    { type: 'tool_call', tool: 'parse_scenario', status: 'calling', label: '解析消費情境中...' },
    {
      type: 'tool_call',
      tool: 'parse_scenario',
      status: 'done',
      label: '識別通路：高鐵，金額：NT$ 1,500',
      channels: ['高鐵'],
      amount: 1500,
    },
    {
      type: 'tool_call',
      tool: 'search_by_channel',
      status: 'calling',
      label: '查詢「交通」通路最佳卡片...',
      channel: '交通',
    },
    {
      type: 'tool_call',
      tool: 'search_by_channel',
      status: 'done',
      label: '「交通」找到 3 張卡，最高回饋：富邦Costco聯名卡',
      channel: '交通',
      result_count: 3,
    },
    {
      type: 'tool_result',
      tool: 'search_by_channel',
      status: 'success',
      summary: '回傳 3 張候選卡，最高回饋為 富邦Costco聯名卡',
      data: {},
    },
    {
      type: 'mcp_calculation',
      tool: 'search_by_channel',
      channel: '交通',
      candidates: [
        {
          card_id: 'fubon_c_costco',
          card_name: '富邦Costco聯名卡',
          cashback_rate: 0.08,
          estimated_cashback: 120,
          formula: 'min(1500 × 8%, 550) = 120',
          data_source: 'manual',
          is_fallback: false,
        },
      ],
      winner: {
        card_id: 'fubon_c_costco',
        card_name: '富邦Costco聯名卡',
        cashback_rate: 0.08,
        estimated_cashback: 120,
        formula: 'min(1500 × 8%, 550) = 120',
      },
      ranking_summary: '富邦Costco聯名卡 NT$ 120',
    },
    { type: 'thinking_done', elapsed_seconds: 0.2 },
    {
      type: 'result',
      data: {
        scenario: '高鐵車票 1500 元',
        parsed: { channels: [{ name: '高鐵', channel_id: 'transport' }], amount: 1500 },
        amount_info: { amount_display: 'NT$ 1,500' },
        recommendations: [
          {
            channel_name: '交通',
            channel_id: 'transport',
            best_options: [
              searchResult({
                card_id: 'fubon_c_costco',
                card_name: '富邦Costco聯名卡',
                cashback_rate: 0.08,
                cashback_type: 'cash',
                estimated_cashback: 120,
                max_cashback_per_period: 550,
                cashback_description: '高鐵最高 8% 現金回饋',
                conditions: '每期上限 NT$550',
              }),
            ],
          },
        ],
        error: null,
      },
    },
  ]);

  await chooseCardsAndStart(page, ['富邦Costco聯名卡', '富邦momo聯名卡', 'LINE Pay信用卡']);
  await sendChatMessage(page, '高鐵車票 1500 元');

  await expect(page.getByText('富邦Costco聯名卡').last()).toBeVisible();
  await expect(page.getByText('NT$ 120', { exact: true })).toBeVisible();
  await ensurePanelTextVisible(page, 'min(1500 × 8%, 550) = 120');
});

test('agent mode renders MCP tool use and result without reload tool', async ({ page }) => {
  await page.route('**/api/chat', async (route) => {
    const result = {
      channel_id: 'transport',
      channel_name: '交通',
      results: [
        searchResult({
          card_id: 'fubon_c_costco',
          card_name: '富邦Costco聯名卡',
          cashback_rate: 0.08,
          cashback_type: 'cash',
          estimated_cashback: 120,
          max_cashback_per_period: 550,
          cashback_description: '高鐵最高 8% 現金回饋',
          conditions: '每期上限 NT$550',
        }),
      ],
      error: null,
    };

    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: namedSse([
        {
          event: 'tool_use',
          data: {
            id: 'toolu_1',
            tool_name: 'search_by_channel',
            server_name: 'ctbc-payment-advisor',
            input: { channel: '高鐵', cards_owned: ['fubon_c_costco'], amount: 1500 },
          },
        },
        {
          event: 'tool_result',
          data: {
            tool_use_id: 'toolu_1',
            tool_name: 'search_by_channel',
            input: { channel: '高鐵', cards_owned: ['fubon_c_costco'], amount: 1500 },
            is_error: false,
            summary: JSON.stringify(result),
            data: {
              source_tool: 'search_by_channel',
              recommendations: [
                {
                  channel_name: '交通',
                  channel_id: 'transport',
                  best_options: result.results,
                },
              ],
            },
          },
        },
        { event: 'done', data: { stop_reason: 'end_turn' } },
      ]),
    });
  });

  await chooseCardsAndStart(page, ['富邦Costco聯名卡']);
  await page.getByText('Agent 模式').click();
  await sendChatMessage(page, '高鐵車票 1500 元');

  await expect(page.getByText('Claude 決定呼叫 MCP 工具')).toBeVisible();
  await expect(page.getByText('search_by_channel').first()).toBeVisible();
  await expect(page.getByText('MCP 已回傳資料')).toBeVisible();
  await expect(page.getByText('富邦Costco聯名卡').last()).toBeVisible();
  await expect(page.getByText('reload_data')).toHaveCount(0);
});

async function chooseCardsAndStart(page: Page, cardNames: string[]) {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '選擇您持有的信用卡' })).toBeVisible();
  for (const cardName of cardNames) {
    await page.getByText(cardName, { exact: true }).click();
  }
  await page.getByRole('button', { name: '開始使用' }).click();
  await expect(page.getByPlaceholder('請輸入您的消費情境，例如：我在日本旅遊刷卡 5000 元')).toBeVisible();
}

async function sendChatMessage(page: Page, message: string) {
  const input = page.getByPlaceholder('請輸入您的消費情境，例如：我在日本旅遊刷卡 5000 元');
  await input.fill(message);
  await input.press('Enter');
}

async function ensurePanelTextVisible(page: Page, text: string) {
  const locator = page.getByText(text).first();
  try {
    await expect(locator).toBeVisible({ timeout: 1_000 });
  } catch {
    await page.getByRole('button', { name: /工具執行完成/ }).click();
    await expect(locator).toBeVisible();
  }
}

async function mockStructuredRecommendation(page: Page, events: Record<string, unknown>[]) {
  await page.route('**/api/recommend/stream', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: dataSse(events),
    });
  });
}

function searchResult(overrides: Record<string, unknown>) {
  return {
    rank: 1,
    card_id: 'test_card',
    card_name: '測試卡',
    cashback_rate: 0.01,
    cashback_type: 'cash',
    cashback_description: '',
    estimated_cashback: 0,
    max_cashback_per_period: null,
    valid_end: null,
    expiring_soon: false,
    conditions: '',
    data_source: 'test',
    is_fallback: false,
    ...overrides,
  };
}

function dataSse(events: Record<string, unknown>[]) {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('');
}

function namedSse(events: Array<{ event: string; data: Record<string, unknown> }>) {
  return events
    .map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join('');
}
