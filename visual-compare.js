const { chromium } = require('playwright');
const fs = require('fs');

const targets = [
  { name: 'reference', base: 'https://buildledger-wireframes.bright-tuna-4729.chatgpt.site', email: process.env.REF_EMAIL, password: process.env.REF_PASSWORD },
  { name: 'local', base: 'http://127.0.0.1:8000', email: process.env.LOCAL_EMAIL, password: process.env.LOCAL_PASSWORD },
];

(async () => {
  fs.mkdirSync('.visual-comparison', { recursive: true });
  const browser = await chromium.launch({ headless: true });
  for (const target of targets) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    await page.goto(target.name === 'reference' ? `${target.base}/` : `${target.base}/accounts/login/`, { waitUntil: 'networkidle', timeout: 60000 });
    if (target.name === 'reference') {
      await page.getByRole('button', { name: /employee login/i }).click();
      await page.waitForTimeout(500);
    }
    await page.screenshot({ path: `.visual-comparison/${target.name}-login.png`, fullPage: true });
    const inputs = page.locator('input');
    console.log(target.name, 'login', page.url(), await page.title(), 'inputs', await inputs.count());
    const userInput = page.locator('input[type="email"], input[name="username"], input[name="email"]').first();
    const passInput = page.locator('input[type="password"]').first();
    await userInput.fill(target.email);
    await passInput.fill(target.password);
    await page.locator('button[type="submit"], input[type="submit"]').first().click();
    await page.waitForLoadState('networkidle', { timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(3000);
    console.log(target.name, 'after-login', page.url(), await page.title());
    fs.writeFileSync(`.visual-comparison/${target.name}-page.html`, await page.content());
    await page.screenshot({ path: `.visual-comparison/${target.name}-dashboard.png`, fullPage: true });
    const metrics = await page.evaluate(() => {
      const pick = (selector) => {
        const el = document.querySelector(selector);
        if (!el) return null;
        const s = getComputedStyle(el), r = el.getBoundingClientRect();
        return { selector, text: el.textContent.trim().replace(/\s+/g, ' ').slice(0, 160), rect: [r.x, r.y, r.width, r.height].map(Math.round), font: s.fontFamily, fontSize: s.fontSize, color: s.color, background: s.backgroundColor };
      };
      return {
        body: pick('body'), sidebar: pick('aside, [class*="sidebar"]'), header: pick('header, [class*="topbar"]'), main: pick('main'), h1: pick('h1'), cards: document.querySelectorAll('article').length,
        shellDisplay: document.querySelector('.app-shell') && getComputedStyle(document.querySelector('.app-shell')).display,
        sheets: [...document.styleSheets].map(sheet => sheet.href),
        links: [...document.querySelectorAll('a')].slice(0, 30).map(a => ({ text: a.textContent.trim().replace(/\s+/g, ' '), href: a.href })),
      };
    });
    fs.writeFileSync(`.visual-comparison/${target.name}-metrics.json`, JSON.stringify(metrics, null, 2));
    await context.close();
  }
  await browser.close();
})();
