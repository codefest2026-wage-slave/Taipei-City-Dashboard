/**
 * 韌性防災儀表板 — E2E 測試 (API + UI)
 *
 * 啟動環境後執行:
 *   cd e2e && npm install && npx playwright install chromium
 *   npx playwright test tests/disaster-prevention.spec.ts
 */
import { test, expect, APIRequestContext } from '@playwright/test';

const BASE = 'http://localhost:8080';
const EMAIL = process.env.DASHBOARD_EMAIL ?? 'test1234@gmail.com';
const PASS  = process.env.DASHBOARD_PASSWORD ?? 'test1234';

// ── Shared auth token ─────────────────────────────────────────
let authToken = '';

async function getToken(request: APIRequestContext): Promise<string> {
  if (authToken) return authToken;
  // Login uses HTTP Basic Auth: base64(email:password)
  const credentials = Buffer.from(`${EMAIL}:${PASS}`).toString('base64');
  const res = await request.post(`${BASE}/api/dev/auth/login`, {
    headers: { Authorization: `Basic ${credentials}` },
  });
  expect(res.status(), 'login should succeed').toBe(200);
  const body = await res.json();
  authToken = body.token ?? body.data?.token ?? '';
  expect(authToken, 'token should not be empty').toBeTruthy();
  return authToken;
}

// ── API Tests ─────────────────────────────────────────────────
test.describe('API: 韌性防災儀表板存在', () => {
  test('GET /dashboard/ should include disaster_prevention', async ({ request }) => {
    const token = await getToken(request);
    const res = await request.get(`${BASE}/api/dev/dashboard/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    // Response: { data: { public: [...], taipei: [...], metrotaipei: [...], personal: [...] } }
    const groups: Record<string, { index: string }[]> = body.data ?? {};
    const allDashboards = Object.values(groups).flat();
    const found = allDashboards.some((d) => d.index === 'disaster_prevention');
    expect(found, 'disaster_prevention dashboard should exist').toBe(true);
  });
});

test.describe('API: 城市切換 query_charts', () => {
  // Map component index → expected component id (inserted as 401-404)
  const components = [
    { name: 'flood_risk_map',          id: 401 },
    { name: 'rainfall_realtime_chart', id: 402 },
    { name: 'shelter_map',             id: 403 },
    { name: 'disaster_risk_kpi',       id: 404 },
  ] as const;
  const cities = ['metrotaipei', 'taipei'] as const;

  for (const { name, id } of components) {
    for (const city of cities) {
      test(`GET component/${id}/chart?city=${city} [${name}] returns data`, async ({ request }) => {
        const token = await getToken(request);
        const res = await request.get(
          `${BASE}/api/dev/component/${id}/chart?city=${city}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        // 200 or 204 (no data) are both acceptable — key is no 4xx/5xx
        expect(res.status(), `${name}/${city} should not error`).toBeLessThan(400);
        const body = await res.json();
        expect(body.status, `${name}/${city} status should be success`).toBe('success');
      });
    }
  }
});

test.describe('API: component config 存在 (IDs 401-404)', () => {
  test('all 4 disaster components should be retrievable', async ({ request }) => {
    const token = await getToken(request);
    for (const id of [401, 402, 403, 404]) {
      const res = await request.get(`${BASE}/api/dev/component/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(
        res.status(),
        `component id=${id} should be found`,
      ).toBeLessThan(400);
      const body = await res.json();
      expect(body.status, `component id=${id} status should be success`).toBe('success');
    }
  });
});

// ── UI Tests ──────────────────────────────────────────────────
test.describe('UI: 韌性防災儀表板', () => {
  test.beforeEach(async ({ page, request }) => {
    // Get JWT via API (avoids complex UI login flow with TaipeiPass/email toggle)
    const token = await getToken(request);
    // Navigate to app first so localStorage is accessible for the domain
    await page.goto(`${BASE}/`);
    // Inject token and dismiss welcome dialog flag
    await page.evaluate(({ tok }) => {
      localStorage.setItem('token', tok);
      localStorage.setItem('initialWarning', 'shown');
    }, { tok: token });
    // Reload so the app reads the injected token from localStorage
    await page.reload({ waitUntil: 'networkidle' });
  });

  test('should navigate to disaster prevention dashboard', async ({ page }) => {
    // Look for the dashboard in the sidebar
    const dashboardLink = page.getByText('韌性防災').first();
    await expect(dashboardLink).toBeVisible({ timeout: 15_000 });
    await dashboardLink.click();
    // URL uses query param: /dashboard?index=disaster_prevention
    await expect(page).toHaveURL(/disaster_prevention/, {
      timeout: 10_000,
    });
  });

  test('should show 4 disaster component tiles', async ({ page }) => {
    // Use sidebar navigation (same as 'navigate' test which passes)
    // Direct goto with ?index= query competes with async contentStore init
    await page.goto(`${BASE}/dashboard`);
    const dashboardLink = page.getByText('韌性防災').first();
    await expect(dashboardLink).toBeVisible({ timeout: 15_000 });
    await dashboardLink.click();
    await page.waitForURL(/disaster_prevention/, { timeout: 10_000 });
    const expectedComponents = [
      '淹水潛勢分級地圖',
      '即時雨量監測',
      '避難場所地圖',
      '防災資源 KPI',
    ];
    for (const name of expectedComponents) {
      await expect(
        page.getByText(name).first(),
        `Component "${name}" should be visible`,
      ).toBeVisible({ timeout: 15_000 });
    }
  });

  test('city switch metrotaipei → taipei should not error', async ({ page }) => {
    await page.goto(`${BASE}/dashboard`);
    const dashboardLink = page.getByText('韌性防災').first();
    await expect(dashboardLink).toBeVisible({ timeout: 15_000 });
    await dashboardLink.click();
    await page.waitForURL(/disaster_prevention/, { timeout: 10_000 });
    // Find city switcher and click taipei
    const taipeiBtn = page.getByRole('button', { name: /臺北市|taipei/i }).first();
    if (await taipeiBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await taipeiBtn.click();
      // Should not show any error toast
      await expect(page.getByText(/錯誤|error|failed/i)).not.toBeVisible({
        timeout: 5_000,
      });
    } else {
      test.skip(); // city switcher not visible, skip
    }
  });

  test('should have no console errors on dashboard load', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await page.goto(`${BASE}/dashboard`);
    const dashboardLink = page.getByText('韌性防災').first();
    await expect(dashboardLink).toBeVisible({ timeout: 15_000 });
    await dashboardLink.click();
    await page.waitForURL(/disaster_prevention/, { timeout: 10_000 });
    // Filter out known non-critical errors (e.g. map tile warnings)
    const critical = errors.filter(
      (e) => !e.includes('favicon') && !e.includes('mapbox') && !e.includes('tile'),
    );
    expect(critical, `Console errors: ${critical.join('\n')}`).toHaveLength(0);
  });
});
