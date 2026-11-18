'use strict';
/* 共享测试 harness：vm 执行 index.html 内嵌 <script>，以 DOM/localStorage/window 桩
 * 模拟真实启动路径（readyState=complete → Game.init 立即执行）。
 * 桥接导出采用宽容模式：只导出已定义的模块，便于增量开发时新旧测试并存。 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function makeEl(id) {
  const el = {
    id: String(id),
    textContent: '',
    title: '',
    disabled: false,
    checked: false,
    offsetWidth: 0,
    dataset: {},
    style: { setProperty() {} },
    children: [],
    parentNode: null,
    listeners: {},
  };
  /* 浏览器语义：innerHTML 置空即移除全部子节点（非空字符串仅记录，不做解析） */
  el._html = '';
  Object.defineProperty(el, 'innerHTML', {
    get() { return el._html; },
    set(v) {
      el._html = String(v);
      if (el._html === '') el.children.length = 0;
    },
  });
  el.classList = {
    _s: new Set(),
    add(c) { this._s.add(c); },
    remove(c) { this._s.delete(c); },
    contains(c) { return this._s.has(c); },
    toggle(c, force) {
      if (force === undefined) { this._s.has(c) ? this._s.delete(c) : this._s.add(c); }
      else if (force) this._s.add(c);
      else this._s.delete(c);
      return this._s.has(c);
    },
  };
  /* 浏览器语义：className 与 classList 是同一组 token 的两个视图 */
  Object.defineProperty(el, 'className', {
    get() { return Array.from(el.classList._s).join(' '); },
    set(v) {
      el.classList._s.clear();
      String(v).split(/\s+/).forEach(c => { if (c) el.classList._s.add(c); });
    },
  });
  el.addEventListener = (t, f) => { (el.listeners[t] = el.listeners[t] || []).push(f); };
  el.setAttribute = () => {};
  el.getAttribute = () => null;
  el.appendChild = (ch) => { el.children.push(ch); ch.parentNode = el; return ch; };
  el.remove = () => {
    if (el.parentNode && el.parentNode.children) {
      const i = el.parentNode.children.indexOf(el);
      if (i >= 0) el.parentNode.children.splice(i, 1);
    }
  };
  Object.defineProperty(el, 'firstChild', { get() { return el.children[0] || null; } });
  return el;
}

const BASE_EXPORTS = ['GameConfig', 'GameState', 'NumberFormat', 'Rates', 'SaveSystem', 'GameEngine',
  'CultivationSystem', 'UpgradeSystem', 'QuestSystem', 'AchievementSystem', 'Effects', 'UI', 'Game',
  'addCult', 'addStone', 'spendStone', 'addLog'];
const V2_EXPORTS = ['ResourceSystem', 'BuffSystem', 'RootSystem', 'TechniqueSystem', 'ExpeditionSystem', 'AlchemySystem'];

function createSandbox({ tabs = ['cave', 'quest', 'achv', 'log'], extraExports = V2_EXPORTS } = {}) {
  const elements = {};
  const tabEls = tabs.map(k => {
    const t = makeEl('tab-' + k);
    t.dataset.tab = k;
    return t;
  });
  const documentStub = {
    readyState: 'complete',
    hidden: false,
    getElementById(id) { return elements[id] || (elements[id] = makeEl(id)); },
    createElement(tag) { return makeEl(tag); },
    createDocumentFragment() { return makeEl('fragment'); },
    querySelectorAll(sel) { return sel === '.tab-btn' ? tabEls : []; },
    addEventListener() {},
  };
  const store = {};
  const localStorageStub = {
    getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    setItem(k, v) { store[k] = String(v); },
    removeItem(k) { delete store[k]; },
  };
  const windowStub = { addEventListener() {} };
  const sandbox = {
    document: documentStub,
    localStorage: localStorageStub,
    window: windowStub,
    setTimeout, clearTimeout, setInterval, clearInterval,
    Date, Math, Number, JSON, console,
    __exports: null,
  };
  const allNames = BASE_EXPORTS.concat(extraExports);
  const bridge = '\n;__exports = {}; ' +
    allNames.map(n => `if (typeof ${n} !== 'undefined') __exports.${n} = ${n};`).join(' ');
  vm.createContext(sandbox);
  const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  const m = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!m) throw new Error('未找到 <script> 块');
  vm.runInContext(m[1] + bridge, sandbox, { filename: 'xian-inline.js' });
  return {
    G: sandbox.__exports,
    elements, store,
    documentStub, localStorageStub, windowStub, tabs: tabEls,
  };
}

module.exports = { makeEl, createSandbox, BASE_EXPORTS, V2_EXPORTS };
