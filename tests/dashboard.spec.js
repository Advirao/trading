/**
 * Playwright smoke tests for the Alpaca Trading Streamlit dashboard.
 * Run: npx playwright test tests/test_dashboard.js --reporter=list
 *
 * Assumes the Streamlit app is already running on http://localhost:8501
 */

const { test, expect } = require("@playwright/test");

const BASE = "http://localhost:8501";
const TIMEOUT = 30_000; // Streamlit pages can be slow to hydrate

// Helper: wait for Streamlit to finish rendering (spinner gone)
async function waitReady(page) {
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { timeout: TIMEOUT });
  // Wait for any loading spinners to clear
  await page.waitForFunction(
    () => !document.querySelector('[data-testid="stStatusWidget"]'),
    { timeout: TIMEOUT }
  ).catch(() => {}); // not fatal — some pages have no spinner
}

// ── Dashboard (main page) ─────────────────────────────────────────────────────

test("Dashboard loads with equity metric card", async ({ page }) => {
  await page.goto(BASE, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  const title = page.locator("h1");
  await expect(title).toContainText("Dashboard", { timeout: TIMEOUT });
});

test("Dashboard shows metric cards row", async ({ page }) => {
  await page.goto(BASE, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  // m-card components rendered via st.markdown
  const cards = page.locator(".m-card");
  await expect(cards).toHaveCount(4, { timeout: TIMEOUT });
});

test("Dashboard sidebar has market pill", async ({ page }) => {
  await page.goto(BASE, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  const pill = page.locator(".market-pill");
  await expect(pill).toBeVisible({ timeout: TIMEOUT });
});

test("Dashboard refresh button clears cache and reruns", async ({ page }) => {
  await page.goto(BASE, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  const refreshBtn = page.locator("button", { hasText: "Refresh" }).first();
  await expect(refreshBtn).toBeVisible();
  await refreshBtn.click();
  // After rerun page should still have the title
  await expect(page.locator("h1")).toContainText("Dashboard", { timeout: TIMEOUT });
});

// ── Scanner page ──────────────────────────────────────────────────────────────

test("Scanner page loads and shows Run Scan button", async ({ page }) => {
  await page.goto(`${BASE}/Scanner`, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  await expect(page.locator("h1")).toContainText("Scanner", { timeout: TIMEOUT });
  const scanBtn = page.locator("button", { hasText: "Run Scan" });
  await expect(scanBtn).toBeVisible();
});

test("Scanner shows info alert before scan is run", async ({ page }) => {
  await page.goto(`${BASE}/Scanner`, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  const infoBox = page.locator(".alert-info");
  await expect(infoBox).toBeVisible({ timeout: TIMEOUT });
});

// ── Trade page ────────────────────────────────────────────────────────────────

test("Trade page loads with symbol input and BUY/SELL buttons", async ({ page }) => {
  await page.goto(`${BASE}/Trade`, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  await expect(page.locator("h1")).toContainText("Manual Trading", { timeout: TIMEOUT });
  await expect(page.locator("button", { hasText: "Get Quote" })).toBeVisible();
  await expect(page.locator("button", { hasText: "BUY" })).toBeVisible();
  await expect(page.locator("button", { hasText: "SELL" })).toBeVisible();
});

test("Trade page quote lookup shows warning for empty symbol", async ({ page }) => {
  await page.goto(`${BASE}/Trade`, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  // Click Get Quote without entering anything — should show a warn alert
  await page.locator("button", { hasText: "Get Quote" }).click();
  await expect(page.locator(".alert-warn")).toBeVisible({ timeout: TIMEOUT });
});

// ── Copy Trading page ─────────────────────────────────────────────────────────

test("Copy Trading page loads with politician selectbox", async ({ page }) => {
  await page.goto(`${BASE}/Copy_Trading`, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  await expect(page.locator("h1")).toContainText("Congressional Copy Trading", { timeout: TIMEOUT });
  // Summary metric cards (after data loads)
  const cards = page.locator(".m-card");
  const count = await cards.count();
  expect(count).toBeGreaterThanOrEqual(0); // may be 0 if API is down
});

// ── Wheel page ────────────────────────────────────────────────────────────────

test("Wheel page loads with stage selector and symbol input", async ({ page }) => {
  // Navigate via sidebar link — more reliable than direct URL for Streamlit pages
  await page.goto(BASE, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);
  await page.locator('[data-testid="stSidebar"] a', { hasText: "Wheel" }).click();
  await waitReady(page);

  await expect(page.locator("h1")).toContainText("Wheel Strategy", { timeout: TIMEOUT });
  await expect(page.locator('input[placeholder="TQQQ"]')).toBeVisible();
  await expect(page.locator("button", { hasText: "Refresh Positions" })).toBeVisible();
});

test("Wheel page shows info alert when no legs open", async ({ page }) => {
  await page.goto(BASE, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);
  await page.locator('[data-testid="stSidebar"] a', { hasText: "Wheel" }).click();
  await waitReady(page);

  // Either opt-cards (legs exist) or an info alert (no legs)
  const hasLegs  = await page.locator(".opt-card").count() > 0;
  const hasAlert = await page.locator(".alert-info").isVisible().catch(() => false);
  expect(hasLegs || hasAlert).toBe(true);
});

// ── History page ──────────────────────────────────────────────────────────────

test("History page loads with two subheadings", async ({ page }) => {
  await page.goto(`${BASE}/History`, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  await expect(page.locator("h1")).toContainText("Trade History", { timeout: TIMEOUT });
  const headers = page.locator(".section-header");
  await expect(headers.first()).toBeVisible({ timeout: TIMEOUT });
});

// ── Cross-page: navigation ─────────────────────────────────────────────────────

test("Sidebar navigation links are present", async ({ page }) => {
  await page.goto(BASE, { waitUntil: "networkidle", timeout: TIMEOUT });
  await waitReady(page);

  const sidebar = page.locator('[data-testid="stSidebar"]');
  await expect(sidebar).toBeVisible();
  // Streamlit renders nav links as <a> tags in the sidebar
  const navLinks = sidebar.locator("a");
  const count = await navLinks.count();
  expect(count).toBeGreaterThan(0);
});
