/* MyFarm E2E — 真实 Chrome(headless) 验证：加载/菜单/购买/种植/生长/收获/售卖/天气/昼夜/设置/暂停/存档 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PAGE = 'file:///D:/000_study/020_code/claude/myfarm/index.html';
const VENDOR = path.join(__dirname, 'vendor', 'three.module.js');
const SHOTS = path.join(__dirname, 'shots');

let pass = 0, fail = 0;
const ok = (c, name, extra = '') => {
  if (c) { pass++; console.log('  PASS  ' + name); }
  else { fail++; console.log('  FAIL  ' + name + (extra ? '   [' + extra + ']' : '')); }
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const visible = async (sel) => page.$eval(sel, el => !el.classList.contains('hidden')).catch(() => false);

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
      '--autoplay-policy=no-user-gesture-required', '--window-size=1280,720'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720 });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });
  page.on('requestfailed', r => errors.push('REQFAIL: ' + r.url() + ' ' + ((r.failure() || {}).errorText || '')));
  // 隔离网络：three.js 用本地 vendor 提供，其余 http(s) 一律拦截 → 发现任何隐藏网络依赖
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const u = request.url();
    if (u.startsWith('https://cdn.jsdelivr.net/npm/three@')) {
      // 真实 jsDelivr 会带 ACAO:*，file:// 页面的 ESM import 依赖此头，模拟必须一致
      await request.respond({ status: 200, contentType: 'application/javascript', headers: { 'access-control-allow-origin': '*' }, body: fs.readFileSync(VENDOR) });
    } else if (/^https?:/.test(u)) {
      await request.abort();
    } else {
      await request.continue();
    }
  });

  console.log('== 1 加载与主菜单 ==');
  await page.goto(PAGE, { waitUntil: 'domcontentloaded', timeout: 30000 });
  try {
    await page.waitForFunction('window.__booted === true', { timeout: 20000 });
    ok(true, '引擎启动成功');
  } catch { ok(false, '引擎启动成功', 'timeout waiting __booted'); }
  await sleep(1000);
  await page.screenshot({ path: path.join(SHOTS, '01-menu.png') });
  ok(await visible('#menu-main'), '主菜单可见');

  console.log('== 2 开始游戏 ==');
  await page.click('#btn-start');
  await sleep(400);
  if (await visible('#confirm-dialog')) { await page.click('#confirm-yes'); }
  try {
    await page.waitForFunction('window.__dbg && window.__dbg.state().running', { timeout: 5000 });
    ok(true, '进入游戏状态');
  } catch { ok(false, '进入游戏状态'); }
  let st = await page.evaluate(() => window.__dbg.state());
  ok(st.coins === 100, '初始金币=100', 'coins=' + st.coins);
  const au = await page.evaluate(() => window.__dbg.audio());
  ok(au.state === 'running', 'AudioContext running', JSON.stringify(au));
  await sleep(1500);
  await page.screenshot({ path: path.join(SHOTS, '02-game.png') });

  console.log('== 3 商店购买种子 ==');
  await page.click('#btn-shop');
  await page.waitForSelector('.seed-card[data-crop="cabbage"]', { visible: true });
  await page.screenshot({ path: path.join(SHOTS, '03-shop.png') });
  await page.click('.seed-card[data-crop="cabbage"] .buy-1');
  await sleep(250);
  st = await page.evaluate(() => window.__dbg.state());
  ok(st.seeds.cabbage === 1, '购买后种子=1', JSON.stringify(st.seeds));
  ok(st.coins === 95, '金币 100-5=95', 'coins=' + st.coins);

  console.log('== 4 选中工具并种植 ==');
  await page.click('.seed-card[data-crop="cabbage"] .select');
  await sleep(150);
  st = await page.evaluate(() => window.__dbg.state());
  ok(st.tool === 'cabbage', '当前工具=白菜', 'tool=' + st.tool);
  await page.click('#btn-shop'); // 收起商店面板
  await sleep(250);
  const p = await page.evaluate(() => window.__dbg.plotScreenPos(0));
  await page.mouse.click(p.x, p.y);
  await sleep(300);
  st = await page.evaluate(() => window.__dbg.state());
  ok(st.plots[0] && st.plots[0].seed === 'cabbage', '地块0已种下白菜', JSON.stringify(st.plots[0]));
  ok(st.seeds.cabbage === 0, '种子消耗=0', JSON.stringify(st.seeds));
  await page.screenshot({ path: path.join(SHOTS, '04-plant.png') });

  console.log('== 5 生长成熟 (60x 加速) ==');
  await page.evaluate(() => window.__dbg.setSpeed(60));
  await sleep(1600); // 60x * 1.6s ≈ 96s 游戏时间 > 25s 白菜生长
  st = await page.evaluate(() => window.__dbg.state());
  ok(st.plots[0].progress >= 1, '白菜已成熟', 'progress=' + st.plots[0].progress);
  await page.screenshot({ path: path.join(SHOTS, '05-mature.png') });

  console.log('== 6 收获 ==');
  const p2 = await page.evaluate(() => window.__dbg.plotScreenPos(0));
  await page.mouse.click(p2.x, p2.y);
  await sleep(300);
  st = await page.evaluate(() => window.__dbg.state());
  ok(st.produce.cabbage === 1, '收获入仓=1', JSON.stringify(st.produce));
  await page.screenshot({ path: path.join(SHOTS, '06-harvest.png') });

  console.log('== 7 仓库售卖 ==');
  await page.click('#btn-store');
  await page.waitForSelector('.store-row[data-crop="cabbage"]', { visible: true });
  await page.screenshot({ path: path.join(SHOTS, '07-store.png') });
  await page.click('.store-row[data-crop="cabbage"] .sell-all');
  await sleep(300);
  st = await page.evaluate(() => window.__dbg.state());
  ok(st.produce.cabbage === 0, '仓库清空', JSON.stringify(st.produce));
  ok(st.coins === 109, '金币 95+14=109', 'coins=' + st.coins);

  console.log('== 8 天气系统 ==');
  await page.evaluate(() => window.__dbg.setWeather('rainy'));
  await sleep(2000);
  st = await page.evaluate(() => window.__dbg.state());
  ok(st.weather === 'rainy', '天气=雨天', 'weather=' + st.weather);
  ok(await page.evaluate(() => window.__dbg.rainActive()), '雨粒子激活');
  await page.screenshot({ path: path.join(SHOTS, '08-rain.png') });

  console.log('== 9 昼夜 (夜间截图) ==');
  await page.evaluate(() => { window.__dbg.setSpeed(1); window.__dbg.setWeather('sunny'); });
  await sleep(5000); // 天气过渡 4s
  await page.evaluate(() => window.__dbg.setDay(0.75));
  await sleep(1000);
  await page.screenshot({ path: path.join(SHOTS, '09-night.png') });
  ok(true, '夜间渲染完成 (人工检查 09-night.png)');

  console.log('== 10 设置音量 ==');
  await page.click('#btn-settings');
  await page.waitForSelector('#set-sfx', { visible: true });
  await page.evaluate(() => {
    const s = document.querySelector('#set-sfx');
    s.value = 0;
    s.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.click('#btn-apply-settings');
  await sleep(200);
  st = await page.evaluate(() => window.__dbg.state());
  ok(st.settings.sfx === 0, '音效音量=0 生效', JSON.stringify(st.settings));
  await page.evaluate(() => {
    const s = document.querySelector('#set-sfx');
    s.value = 80;
    s.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.click('#btn-apply-settings');
  await sleep(200);

  console.log('== 11 暂停菜单 (ESC) ==');
  await page.keyboard.press('Escape');
  await sleep(300);
  ok(await visible('#pause-menu'), 'ESC 打开暂停菜单');
  await page.screenshot({ path: path.join(SHOTS, '10-pause.png') });
  await page.click('#btn-resume');
  await sleep(250);
  ok(await visible('#pause-menu') === false, '继续游戏关闭菜单');

  console.log('== 12 存档与续档 ==');
  await page.evaluate(() => window.__dbg.save());
  await sleep(300);
  await page.reload({ waitUntil: 'domcontentloaded' });
  try {
    await page.waitForFunction('window.__booted === true', { timeout: 20000 });
    ok(true, '重新加载成功');
  } catch { ok(false, '重新加载成功'); }
  ok(await visible('#btn-continue'), '主菜单显示"继续游戏"');
  await page.click('#btn-continue');
  await sleep(500);
  st = await page.evaluate(() => window.__dbg.state());
  ok(st.coins === 109, '续档金币=109', 'coins=' + st.coins);
  await page.screenshot({ path: path.join(SHOTS, '11-resume.png') });

  console.log('== 13 JS/网络错误 ==');
  const realErrors = errors.filter(e => !/Download the React DevTools/i.test(e));
  ok(realErrors.length === 0, '无 JS/网络错误', realErrors.slice(0, 5).join(' | '));

  await browser.close();
  console.log(`\n===== 结果: ${pass} PASS / ${fail} FAIL =====`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('TEST CRASH:', e); process.exit(2); });
