(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.TigerEngine = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const SYMBOLS = Object.freeze([
    { id: 's_banana', name: '小香蕉', odds: 4, tier: 'small' },
    { id: 's_mango', name: '小芒果', odds: 6, tier: 'small' },
    { id: 'apple', name: '苹果', odds: 8, tier: 'small' },
    { id: 'banana', name: '香蕉', odds: 12, tier: 'big' },
    { id: 'mango', name: '芒果', odds: 15, tier: 'big' },
    { id: 'watermelon', name: '西瓜', odds: 20, tier: 'big' },
    { id: 'star', name: '双星', odds: 30, tier: 'big' },
    { id: 'seven', name: '双七', odds: 40, tier: 'big' },
    { id: 'bar', name: 'BAR', odds: 50, tier: 'big' },
  ]);

  // 24 个灯位，6 个 LUCK；其余符号的灯数按概率大致分布。
  const RING = Object.freeze([
    's_banana', 's_mango', 'apple', 'luck', 'banana', 's_banana',
    'mango', 'apple', 's_mango', 'luck', 's_banana', 'watermelon',
    'banana', 's_mango', 'apple', 's_banana', 'luck', 'star',
    's_banana', 'seven', 'luck', 'bar', 'luck', 'luck',
  ]);

  const FEATURES = Object.freeze([
    { id: 'smallThree', name: '小三元', weight: 40, symbols: ['s_banana', 's_mango', 'apple'] },
    { id: 'bigThree', name: '大三元', weight: 17, symbols: ['watermelon', 'star', 'seven'] },
    { id: 'train', name: '开火车', weight: 30 },
    { id: 'gate', name: '天门', weight: 13 },
  ]);

  const GATE_WHEEL = Object.freeze([
    { label: '小天门', multiplier: 5, weight: 65 },
    { label: '天门', multiplier: 10, weight: 30 },
    { label: '大天门', multiplier: 50, weight: 5 },
  ]);

  const INITIAL_COINS = 1000;
  const MAX_BET = 99;
  const MAX_GUESSES = 3;
  const PITY_SPINS = 60;
  const JACKPOT = 99999;

  const SYMBOL_SHARE = 0.8;
  const FEATURE_PROB = 0.03;
  const SYMBOL_PROB = Object.freeze(SYMBOLS.map((s) => SYMBOL_SHARE / s.odds));
  const SYMBOL_PROB_SUM = SYMBOL_PROB.reduce((a, b) => a + b, 0);
  const LUCK_PROB = 1 - SYMBOL_PROB_SUM - FEATURE_PROB;

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function createGame(options = {}) {
    const rng = options.rng || Math.random;
    let coins = options.coins == null ? INITIAL_COINS : options.coins;

    const bets = {};
    for (const sym of SYMBOLS) bets[sym.id] = 0;

    let pendingWin = 0;
    let spinsSinceFeature = 0;
    let guessCount = 0;
    let jackpotArmed = true;
    let lastResult = null;

    function totalBet() {
      let total = 0;
      for (const sym of SYMBOLS) total += bets[sym.id];
      return total;
    }

    function canSpin() {
      const bet = totalBet();
      return pendingWin === 0 && bet > 0 && coins >= bet;
    }

    function bet(symbolId, delta) {
      if (pendingWin > 0) return { ok: false, error: 'ROUND_ACTIVE' };
      const sym = SYMBOLS.find((s) => s.id === symbolId);
      if (!sym) return { ok: false, error: 'INVALID_SYMBOL' };
      if (!Number.isInteger(delta) || delta === 0) {
        return { ok: false, error: 'INVALID_DELTA' };
      }

      const current = bets[symbolId];
      let next = current + delta;
      if (next < 0) next = 0;
      if (next > MAX_BET) return { ok: false, error: 'MAX_BET' };

      if (next > current) {
        const extra = next - current;
        if (totalBet() + extra > coins) {
          return { ok: false, error: 'INSUFFICIENT_COINS' };
        }
      }

      bets[symbolId] = next;
      return { ok: true };
    }

    function clearBets() {
      if (pendingWin > 0) return { ok: false, error: 'ROUND_ACTIVE' };
      for (const sym of SYMBOLS) bets[sym.id] = 0;
      return { ok: true };
    }

    function betAll(unit) {
      if (pendingWin > 0) return { ok: false, error: 'ROUND_ACTIVE' };
      if (!Number.isInteger(unit) || unit <= 0) {
        return { ok: false, error: 'INVALID_DELTA' };
      }

      let added = 0;
      for (const sym of SYMBOLS) {
        const room = Math.min(unit, MAX_BET - bets[sym.id], coins - totalBet());
        if (room <= 0) break;
        bets[sym.id] += room;
        added += room;
      }
      return { ok: true, added };
    }

    function insertCoin(amount = 100) {
      if (!Number.isInteger(amount) || amount <= 0) {
        return { ok: false, error: 'INVALID_AMOUNT' };
      }
      coins += amount;
      return { ok: true, coins };
    }

    function getState() {
      return {
        coins,
        bets: { ...bets },
        totalBet: totalBet(),
        pendingWin,
        spinsSinceFeature,
        guessCount,
        jackpotArmed,
        lastResult,
        canSpin: canSpin(),
      };
    }

    return {
      bet,
      clearBets,
      betAll,
      insertCoin,
      getState,
    };
  }

  return {
    SYMBOLS,
    RING,
    FEATURES,
    GATE_WHEEL,
    INITIAL_COINS,
    MAX_BET,
    MAX_GUESSES,
    PITY_SPINS,
    JACKPOT,
    SYMBOL_SHARE,
    SYMBOL_PROB,
    SYMBOL_PROB_SUM,
    LUCK_PROB,
    FEATURE_PROB,
    createGame,
    mulberry32,
  };
});
