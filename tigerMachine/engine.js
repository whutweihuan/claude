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

  const RING_INDICES_BY_SYMBOL = {};
  const LUCK_INDICES = [];
  RING.forEach((id, index) => {
    if (id === 'luck') {
      LUCK_INDICES.push(index);
    } else {
      if (!RING_INDICES_BY_SYMBOL[id]) RING_INDICES_BY_SYMBOL[id] = [];
      RING_INDICES_BY_SYMBOL[id].push(index);
    }
  });

  // 开火车车厢：每个图案的总权重 = 1/赔率，再平摊到它的每个灯位；
  // 空车权重 0.43，使空车概率为 0.43 / (0.82 + 0.43) = 34.4%。
  const TRAIN_TABLE = [];
  RING.forEach((id, index) => {
    if (id === 'luck') return;
    const sym = SYMBOLS.find((s) => s.id === id);
    const count = RING_INDICES_BY_SYMBOL[id].length;
    TRAIN_TABLE.push({
      symbolId: id,
      stopIndex: index,
      weight: (1 / sym.odds) / count,
    });
  });
  TRAIN_TABLE.push({
    symbolId: null,
    stopIndex: LUCK_INDICES[0],
    weight: 0.43,
    empty: true,
  });
  const TRAIN_TOTAL_WEIGHT = TRAIN_TABLE.reduce((sum, entry) => sum + entry.weight, 0);

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
    let forced = null;

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

    function pickFrom(list) {
      return list[Math.floor(rng() * list.length)];
    }

    function randomLuckIndex() {
      return pickFrom(LUCK_INDICES);
    }

    function pickSymbol() {
      const roll = rng() * SYMBOL_PROB_SUM;
      let acc = 0;
      for (let i = 0; i < SYMBOLS.length; i++) {
        acc += SYMBOL_PROB[i];
        if (roll < acc) return SYMBOLS[i].id;
      }
      return SYMBOLS[SYMBOLS.length - 1].id;
    }

    function pickFeatureId() {
      const total = FEATURES.reduce((sum, f) => sum + f.weight, 0);
      const roll = rng() * total;
      let acc = 0;
      for (const feature of FEATURES) {
        acc += feature.weight;
        if (roll < acc) return feature.id;
      }
      return FEATURES[FEATURES.length - 1].id;
    }

    function pickRingIndexForSymbol(symbolId) {
      return pickFrom(RING_INDICES_BY_SYMBOL[symbolId]);
    }

    function pickGateWheel() {
      const total = GATE_WHEEL.reduce((sum, w) => sum + w.weight, 0);
      const roll = rng() * total;
      let acc = 0;
      for (const wheel of GATE_WHEEL) {
        acc += wheel.weight;
        if (roll < acc) return wheel;
      }
      return GATE_WHEEL[GATE_WHEEL.length - 1];
    }

    function drawCarriage() {
      const roll = rng() * TRAIN_TOTAL_WEIGHT;
      let acc = 0;
      for (const entry of TRAIN_TABLE) {
        acc += entry.weight;
        if (roll >= acc) continue;
        if (entry.empty) {
          return {
            symbolId: null,
            stopIndex: entry.stopIndex,
            win: 0,
            empty: true,
          };
        }
        const sym = SYMBOLS.find((s) => s.id === entry.symbolId);
        return {
          symbolId: entry.symbolId,
          stopIndex: entry.stopIndex,
          win: bets[entry.symbolId] * sym.odds,
          empty: false,
        };
      }
      const last = TRAIN_TABLE[TRAIN_TABLE.length - 1];
      return { symbolId: null, stopIndex: last.stopIndex, win: 0, empty: true };
    }

    function buildFeature(featureId) {
      const feature = FEATURES.find((f) => f.id === featureId);

      if (featureId === 'smallThree' || featureId === 'bigThree') {
        const symbols = feature.symbols.map((id) => {
          const sym = SYMBOLS.find((s) => s.id === id);
          const bet = bets[id];
          return {
            id,
            name: sym.name,
            odds: sym.odds,
            bet,
            win: bet * sym.odds,
            indices: RING_INDICES_BY_SYMBOL[id].slice(),
          };
        });
        const win = symbols.reduce((sum, item) => sum + item.win, 0);
        return {
          type: featureId,
          name: feature.name,
          symbols,
          win,
          stopIndex: randomLuckIndex(),
        };
      }

      if (featureId === 'train') {
        const carriages = [];
        for (let i = 0; i < 5; i++) carriages.push(drawCarriage());
        const win = carriages.reduce((sum, carriage) => sum + carriage.win, 0);
        return {
          type: 'train',
          name: feature.name,
          carriages,
          win,
          stopIndex: randomLuckIndex(),
        };
      }

      if (featureId === 'gate') {
        const wheel = pickGateWheel();
        const win = totalBet() * wheel.multiplier;
        return {
          type: 'gate',
          name: feature.name,
          wheel: { label: wheel.label, multiplier: wheel.multiplier, win },
          win,
          stopIndex: randomLuckIndex(),
        };
      }

      throw new Error('INVALID_FEATURE');
    }

    function forceNextSymbol(symbolId) {
      if (!SYMBOLS.some((s) => s.id === symbolId)) throw new Error('INVALID_SYMBOL');
      forced = { kind: 'symbol', symbolId };
    }

    function forceNextLuck() {
      forced = { kind: 'luck' };
    }

    function forceNextFeature(featureId) {
      if (!FEATURES.some((f) => f.id === featureId)) throw new Error('INVALID_FEATURE');
      forced = { kind: 'feature', featureId };
    }

    function spin() {
      if (pendingWin > 0) throw new Error('ROUND_ACTIVE');
      const stake = totalBet();
      if (stake <= 0) throw new Error('NO_BET');
      if (coins < stake) throw new Error('INSUFFICIENT_COINS');
      coins -= stake;

      let outcome;
      if (forced) {
        outcome = forced;
        forced = null;
      } else if (spinsSinceFeature >= PITY_SPINS) {
        outcome = { kind: 'feature', featureId: pickFeatureId() };
      } else {
        const roll = rng();
        if (roll < FEATURE_PROB) {
          outcome = { kind: 'feature', featureId: pickFeatureId() };
        } else if (roll < FEATURE_PROB + SYMBOL_PROB_SUM) {
          outcome = { kind: 'symbol', symbolId: pickSymbol() };
        } else {
          outcome = { kind: 'luck' };
        }
      }

      let result;
      if (outcome.kind === 'symbol') {
        const sym = SYMBOLS.find((s) => s.id === outcome.symbolId);
        const stopIndex = pickFrom(RING_INDICES_BY_SYMBOL[sym.id]);
        const win = bets[sym.id] * sym.odds;
        pendingWin = win;
        guessCount = 0;
        result = {
          kind: 'symbol',
          stopIndex,
          symbolId: sym.id,
          feature: null,
          win,
          pendingWin,
          message: win > 0
            ? `${sym.name} ${sym.odds}×，赢 ${win} 分`
            : `停在${sym.name}，没有押中`,
        };
      } else if (outcome.kind === 'luck') {
        pendingWin = 0;
        result = {
          kind: 'luck',
          stopIndex: randomLuckIndex(),
          symbolId: null,
          feature: null,
          win: 0,
          pendingWin: 0,
          message: '跑空',
        };
      } else {
        const feature = buildFeature(outcome.featureId);
        pendingWin = feature.win;
        guessCount = 0;
        result = {
          kind: 'feature',
          stopIndex: feature.stopIndex,
          symbolId: null,
          feature,
          win: feature.win,
          pendingWin,
          message: feature.name,
        };
      }

      if (outcome.kind === 'feature') spinsSinceFeature = 0;
      else spinsSinceFeature += 1;

      lastResult = result;
      return result;
    }

    function maybeJackpot() {
      if (coins < 90000) jackpotArmed = true;
      if (jackpotArmed && coins >= JACKPOT) {
        jackpotArmed = false;
        return true;
      }
      return false;
    }

    function collect() {
      if (pendingWin <= 0) return { collected: 0, jackpot: false };
      const amount = pendingWin;
      coins += amount;
      pendingWin = 0;
      guessCount = 0;
      return { collected: amount, jackpot: maybeJackpot() };
    }

    function guess(choice) {
      if (pendingWin <= 0) throw new Error('NO_PENDING_WIN');
      if (choice !== 'small' && choice !== 'big') throw new Error('INVALID_CHOICE');
      if (guessCount >= MAX_GUESSES) throw new Error('GUESS_LIMIT');

      const number = 1 + Math.floor(rng() * 13);
      const correct = (choice === 'small' && number >= 1 && number <= 6)
        || (choice === 'big' && number >= 8 && number <= 13);
      guessCount += 1;

      if (correct) {
        pendingWin *= 2;
      } else {
        pendingWin = 0;
      }

      let collected = 0;
      let autoCollected = false;
      if (guessCount >= MAX_GUESSES && pendingWin > 0) {
        collected = pendingWin;
        coins += pendingWin;
        pendingWin = 0;
        autoCollected = true;
      }

      return {
        number,
        correct,
        pendingWin,
        collected,
        autoCollected,
        guessCount,
        jackpot: maybeJackpot(),
      };
    }

    return {
      bet,
      clearBets,
      betAll,
      insertCoin,
      getState,
      spin,
      collect,
      guess,
      forceNextSymbol,
      forceNextLuck,
      forceNextFeature,
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
