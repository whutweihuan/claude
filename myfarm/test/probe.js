/* 探针：验证 file:// 页面在 run.js 的拦截策略下能否加载 ESM 版 three.js（CORS 问题排查） */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PAGE = 'file:///' + path.join(__dirname, 'probe.html').replace(/\\/g, '/');
const VENDOR = path.join(__dirname, 'vendor', 'three.module.js');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--window-size=640,400'],
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });
  page.on('requestfailed', r => errors.push('REQFAIL: ' + r.url() + ' ' + ((r.failure() || {}).errorText || '')));
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const u = request.url();
    if (u.startsWith('https://cdn.jsdelivr.net/npm/three@')) {
      await request.respond({ status: 200, contentType: 'application/javascript', headers: { 'access-control-allow-origin': '*' }, body: fs.readFileSync(VENDOR) });
    } else if (/^https?:/.test(u)) {
      await request.abort();
    } else {
      await request.continue();
    }
  });

  await page.goto(PAGE, { waitUntil: 'domcontentloaded', timeout: 30000 });
  try {
    await page.waitForFunction('window.__THREE_OK !== undefined', { timeout: 15000 });
    const rev = await page.evaluate(() => window.__THREE_OK);
    console.log('PASS  three ESM 加载成功, REVISION=' + rev);
  } catch {
    console.log('FAIL  three ESM 加载失败');
  }
  console.log('errors:');
  errors.forEach(e => console.log('  ' + e));
  await browser.close();
})().catch(e => { console.error('CRASH:', e.message); process.exit(2); });
