# -*- coding: utf-8 -*-
"""整局编排、事件、商店、UI 与集成冒烟测试。"""
import os
import tempfile
import unittest

import content
import core
import records


def force_node(run, node):
    """沿连线走到目标节点（途经普通战斗节点直接略过，不触发战斗）。"""
    if run.current is None:
        queue = [(eid, [eid]) for eid in run.map.entry_ids]
        seen = set(run.map.entry_ids)
    else:
        queue = [(run.current, [])]
        seen = {run.current}
    while queue:
        cur, path = queue.pop(0)
        if cur == node.id:
            for nid in path:
                run.go(nid)
                run.node_done = True
                run.visited.add(nid) if nid not in run.visited else None
            run.node_done = False
            run.pending = None
            return run.enter()
        for nxt in run.map.nodes[cur].next:
            if nxt not in seen and run.map.nodes[nxt].layer <= node.layer:
                seen.add(nxt)
                queue.append((nxt, path + [nxt]))
    raise AssertionError('node %s unreachable' % node.id)


def find_node(run, kind, layer=None):
    for n in run.map.nodes.values():
        if n.kind == kind and (layer is None or n.layer == layer):
            return n
    raise AssertionError('no %s node' % kind)


def resolve_pending(run):
    guard = 0
    while run.pending is not None and guard < 10:
        guard += 1
        if run.pending['relic_choices']:
            run.choose_relic(0)
        elif run.pending['card_choices']:
            run.skip_card()
        else:
            run.pending = None
    assert run.pending is None


def win_and_collect(run):
    for e in run.active.enemies:
        e.hp = 0
    run.active.status = 'win'
    run.combat_finished()
    resolve_pending(run)


class RunFlowTests(unittest.TestCase):

    def test_full_flow_to_boss(self):
        run = core.Run(123)
        prev_layer = 0
        for _ in range(30):
            self.assertFalse(run.finished)
            opts = run.choices()
            self.assertTrue(opts)
            run.go(opts[0])
            kind, _obj = run.enter()
            layer = run.map.nodes[run.current].layer
            self.assertEqual(layer, prev_layer + 1)
            prev_layer = layer
            if kind in ('combat', 'elite', 'boss'):
                win_and_collect(run)
            elif kind == 'campfire':
                if run.hero.hp < run.hero.max_hp:
                    run.campfire('sleep')
                else:
                    forge = run.campfire_options()[1]
                    run.campfire('forge', forge['cards'][0])
            elif kind == 'chest':
                run.take_chest(True)
            elif kind == 'event':
                run.finish_event()
            elif kind == 'shop':
                run.close_shop()
            if run.finished:
                self.assertEqual(kind, 'boss')
                break
            self.assertTrue(run.node_done)
        self.assertEqual(run.outcome, 'win')
        self.assertIn('crown', run.hero.relics)
        self.assertGreaterEqual(run.stats['kills'], 5)
        self.assertEqual(prev_layer, 11)

    def test_campfire_forge_upgrades_card(self):
        run = core.Run(5)
        node = find_node(run, 'campfire')
        self.assertEqual(force_node(run, node)[0], 'campfire')
        opts = run.campfire_options()
        slot = opts[1]['cards'][0]
        card_id = run.hero.deck[slot][0]
        run.campfire('forge', slot)
        self.assertEqual(run.hero.deck[slot], (card_id, True))
        self.assertTrue(run.node_done)

    def test_campfire_sharpen(self):
        run = core.Run(6)
        for _ in range(3):
            node = find_node(run, 'campfire')
            force_node(run, node)
            run.campfire('sharpen')
            self.assertTrue(run.node_done)
        self.assertEqual(run.hero.weapon_sharpen, 3)
        force_node(run, find_node(run, 'campfire'))
        lines = run.campfire('sharpen')
        self.assertTrue(any('上限' in l for l in lines))
        self.assertFalse(run.node_done)
        self.assertEqual(run.hero.weapon_sharpen, 3)
        mods = core.merged_mods(run.hero)
        self.assertEqual(mods['attack_bonus'],
                         content.WEAPONS[run.hero.weapon].attack_bonus + 3)

    def test_chest_gives_gear(self):
        run = core.Run(7)
        node = find_node(run, 'chest')
        kind, loot = force_node(run, node)
        self.assertEqual(kind, 'chest')
        self.assertTrue(20 <= loot['gold'] <= 40)
        self.assertIn(loot['kind'], ('weapon', 'armor'))
        gold_before = run.hero.gold
        weapon_before = run.hero.weapon
        run.take_chest(True)
        self.assertEqual(run.hero.gold, gold_before + loot['gold'])
        if loot['kind'] == 'weapon':
            self.assertEqual(run.hero.weapon, loot['id'])
            self.assertNotEqual(weapon_before, loot['id'])
        else:
            self.assertEqual(run.hero.armor, loot['id'])
        self.assertTrue(run.node_done)

    def test_campfire_edges(self):
        run = core.Run(8)
        force_node(run, find_node(run, 'campfire'))
        opts = run.campfire_options()
        self.assertFalse(opts[0]['available'])  # 满血睡觉不可用
        lines = run.campfire('sleep')
        self.assertTrue(lines)
        self.assertFalse(run.node_done)
        self.assertEqual(run.hero.hp, run.hero.max_hp)
        self.assertTrue(opts[1]['cards'])

    def test_death_ends_run(self):
        run = core.Run(9)
        node = run.map.nodes[run.choices()[0]]
        self.assertEqual(node.kind, 'combat')
        run.go(node.id)
        run.enter()
        run.active.status = 'lose'
        run.hero.hp = 0
        run.combat_finished()
        self.assertEqual(run.outcome, 'dead')
        self.assertTrue(run.finished)

    def test_pending_blocks_move(self):
        run = core.Run(10)
        run.go(run.choices()[0])
        run.enter()
        run.active.status = 'win'
        run.combat_finished()
        self.assertTrue(run.pending is not None)
        self.assertEqual(run.choices(), [])
        with self.assertRaises(ValueError):
            run.go(list(run.map.nodes)[5])
        run.skip_card()
        self.assertTrue(run.node_done)

    def test_seed_reproducibility(self):
        r1, r2 = core.Run(44), core.Run(44)
        self.assertEqual(
            [(n.layer, n.kind, tuple(n.next)) for n in r1.map.nodes.values()],
            [(n.layer, n.kind, tuple(n.next)) for n in r2.map.nodes.values()])
        for r in (r1, r2):
            r.go(r.choices()[0])
            r.enter()
            r.active.status = 'win'
            r.combat_finished()
        self.assertEqual(r1.pending['card_choices'], r2.pending['card_choices'])
        l1 = core.Run(55)
        l2 = core.Run(55)
        n1 = find_node(l1, 'chest')
        n2 = find_node(l2, 'chest')
        _, loot1 = force_node(l1, n1)
        _, loot2 = force_node(l2, n2)
        self.assertEqual(loot1, loot2)

    def test_events_no_repeat(self):
        run = core.Run(3)
        seen = []
        for node in [n for n in run.map.nodes.values() if n.kind == 'event']:
            kind, ev = force_node(run, node)
            self.assertEqual(kind, 'event')
            seen.append(ev.id)
            run.finish_event()
        self.assertEqual(len(seen), len(set(seen)))
        self.assertGreaterEqual(len(seen), 2)

    def test_relic_drop_auto_added_and_nugget_gold(self):
        run = core.Run(11)
        run.add_relic('nugget')
        self.assertIn('nugget', run.hero.relics)
        self.assertEqual(run.hero.gold, 30)
        run.add_relic('nugget')  # 同种遗物不再重复发钱（计划决定）
        self.assertEqual(run.hero.gold, 30)


def to_shop(run, seed=None):
    node = find_node(run, 'shop')
    kind, obj = force_node(run, node)
    assert kind == 'shop'
    return obj


class ShopTests(unittest.TestCase):

    def test_shop_inventory_shape_and_price(self):
        run = core.Run(80)
        shop = to_shop(run)
        counts = {}
        for s in shop.slots:
            counts[s.kind] = counts.get(s.kind, 0) + 1
        self.assertEqual(counts, {'card': 2, 'weapon': 1, 'armor': 1,
                                  'relic': 1, 'potion': 2})
        for s in shop.slots:
            self.assertGreater(s.price, 0)
            self.assertFalse(s.sold)
        self.assertEqual(shop.remove_cost, 65)
        # hag_hat：同 rng 下现价为 8 折
        run2 = core.Run(80)
        run2.hero.relics.append('hag_hat')
        shop2 = to_shop(run2)
        for a, b in zip(shop.slots, shop2.slots):
            self.assertEqual(b.price, int(a.base_price * 0.8))

    def test_buy_and_spend_rules(self):
        run = core.Run(81)
        shop = to_shop(run)
        run.hero.gold = 1000
        wi = [i for i, s in enumerate(shop.slots) if s.kind == 'weapon'][0]
        wid = shop.slots[wi].content_id
        lines = core.buy(run, wi)
        self.assertEqual(run.hero.weapon, wid)
        self.assertTrue(shop.slots[wi].sold)
        lines2 = core.buy(run, wi)
        self.assertTrue(any('售罄' in l or '卖光' in l for l in lines2))
        # 金币不足
        run2 = core.Run(82)
        shop2 = to_shop(run2)
        run2.hero.gold = 0
        ri = [i for i, s in enumerate(shop2.slots) if s.kind == 'relic'][0]
        price = shop2.slots[ri].price
        lines3 = core.buy(run2, ri)
        self.assertTrue(any('金币' in l for l in lines3))
        self.assertFalse(shop2.slots[ri].sold)
        self.assertEqual(run2.hero.gold, 0)

    def test_remove_card_service(self):
        run = core.Run(83)
        to_shop(run)
        run.hero.gold = 100
        before = len(run.hero.deck)
        core.buy_removal(run, 0)
        self.assertEqual(len(run.hero.deck), before - 1)
        self.assertEqual(run.hero.gold, 100 - run.shop.remove_cost)

    def test_shop_edges(self):
        run = core.Run(84)
        shop = to_shop(run)
        run.hero.gold = 0
        for s in shop.slots:
            s.sold = True
        lines = core.buy(run, 0)
        self.assertTrue(any('售罄' in l or '卖光' in l for l in lines))

    def test_potion_in_and_out_of_combat(self):
        run = core.Run(85)
        node = None
        for n in run.map.nodes.values():
            if n.kind == 'combat':
                node = n
                break
        force_node(run, node)
        run.hero.potions = ['p_blood', 'p_energy', 'p_acid']
        run.hero.hp = 30
        lines = run.active.use_potion(0)
        self.assertEqual(run.hero.hp, 44)
        self.assertEqual(run.hero.potions, ['p_energy', 'p_acid'])
        e_before = run.active.energy
        run.active.use_potion(0)
        self.assertEqual(run.active.energy, e_before + 2)
        # 局外：治疗类可用，攻击/能量类不可
        run.hero.potions = ['p_acid', 'p_blood']
        bad = run.use_potion_outside(0)
        self.assertTrue(any('战斗中' in l for l in bad))
        self.assertEqual(len(run.hero.potions), 2)
        good = run.use_potion_outside(1)
        self.assertTrue(good)
        self.assertEqual(run.hero.potions, ['p_acid'])

    def test_potion_cap_three(self):
        run = core.Run(86)
        shop = to_shop(run)
        run.hero.gold = 1000
        run.hero.potions = ['p_blood', 'p_energy', 'p_fury']
        pi = [i for i, s in enumerate(shop.slots) if s.kind == 'potion'][0]
        lines = core.buy(run, pi)
        self.assertTrue(any('满' in l for l in lines))
        self.assertFalse(shop.slots[pi].sold)
        self.assertEqual(len(run.hero.potions), 3)


class EventTests(unittest.TestCase):

    def goto_event(self, run):
        kind, ev = force_node(run, find_node(run, 'event'))
        assert kind == 'event'
        return ev

    def test_every_event_option_runs(self):
        for eid, ev in content.EVENTS.items():
            for oi in range(len(ev.options)):
                run = core.Run(3000 + oi * 7)
                obj = self.goto_event(run)
                lines, follow = core.apply_event(run, obj, oi)
                self.assertTrue(lines, (eid, oi))
                if follow is not None:
                    self.assertEqual(follow[0], 'combat')
                    self.assertFalse(run.node_done)
                    run.start_event_combat(follow[1])
                    self.assertTrue(run.active is not None)
                    win_and_collect(run)
                    self.assertTrue(run.node_done)

    def test_branch_deterministic_with_seed(self):
        ev = content.EVENTS['goblin_gambler']
        results = []
        for s in range(20):
            run = core.Run(4000 + s)
            self.goto_event(run)
            run.hero.gold = 30
            core.apply_event(run, ev, 0)  # 押 30
            results.append(run.hero.gold)
        first = []
        for _ in range(2):
            run = core.Run(4000)
            obj = self.goto_event(run)
            run.hero.gold = 30
            core.apply_event(run, obj, 0)
            first.append(run.hero.gold)
        self.assertEqual(first[0], first[1])
        self.assertIn(60, results)   # 押中：30-30+60
        self.assertIn(0, results)    # 押输：30-30

    def test_followup_combat_blocks_leave(self):
        run = core.Run(4001)
        ev = content.EVENTS['mimic_chest']
        self.goto_event(run)
        lines, follow = core.apply_event(run, ev, 1)  # 识破先手
        self.assertEqual(follow, ('combat', ['mimic']))
        self.assertEqual(run.choices(), [])
        with self.assertRaises(ValueError):
            run.go(list(run.map.nodes)[3])

    def test_altar_sacrifice_boundaries(self):
        run = core.Run(4002)
        ev = content.EVENTS['dark_altar']
        self.goto_event(run)
        run.hero.hp = 5
        self.assertFalse(core.event_option_available(run, ev, 0))
        lines, follow = core.apply_event(run, ev, 0)
        self.assertTrue(any('撑不住' in l for l in lines))
        self.assertEqual(run.hero.hp, 5)
        self.assertFalse(run.node_done)
        # 金币不足：赌博选项
        run2 = core.Run(4003)
        ev2 = content.EVENTS['goblin_gambler']
        self.goto_event(run2)
        run2.hero.gold = 10
        lines2, _ = core.apply_event(run2, ev2, 0)
        self.assertTrue(any('金币' in l for l in lines2))
        self.assertFalse(run2.node_done)

    def test_event_reward_effects_apply(self):
        run = core.Run(4004)
        ev = content.EVENTS['wounded_traveler']
        self.goto_event(run)
        run.hero.hp = 80
        lines, _ = core.apply_event(run, ev, 0)  # hp-3 + common 遗物
        self.assertEqual(run.hero.hp, 77)
        self.assertEqual(len(run.hero.relics), 1)
        self.assertTrue(run.node_done)
        # 骨之祠祈祷：强化一张牌
        run2 = core.Run(4005)
        ev2 = content.EVENTS['shrine_of_bones']
        self.goto_event(run2)
        before = list(run2.hero.deck)
        core.apply_event(run2, ev2, 0)
        self.assertNotEqual(before, list(run2.hero.deck))
        self.assertTrue(any(up for _c, up in run2.hero.deck))

    def test_potion_cap_via_event(self):
        run = core.Run(4006)
        ev = content.EVENTS['ruined_forge']
        self.goto_event(run)
        run.hero.potions = ['p_blood', 'p_energy', 'p_fury']
        lines, _ = core.apply_event(run, ev, 0)  # 分支可能给药水
        self.assertLessEqual(len(run.hero.potions), 3)


import ui


class FakeIO(object):
    def __init__(self, inputs):
        self.out = []
        self._it = iter(inputs)

    def write(self, s):
        self.out.append(s)

    def read(self):
        try:
            return next(self._it)
        except StopIteration:
            raise EOFError()

    def clear(self):
        pass


def ui_for(run, inputs):
    io = FakeIO(inputs)
    return ui.UI(run, write=io.write, read=io.read, clear=io.clear), io


class UITests(unittest.TestCase):

    def test_map_screen_lists_choices(self):
        run = core.Run(201)
        u, io = ui_for(run, ['q', 'y'])
        result = u.play()
        self.assertEqual(result['outcome'], 'aborted')
        text = '\n'.join(io.out)
        for nid in run.map.entry_ids:
            self.assertIn('节点 %d' % nid, text)
        self.assertIn('战斗', text)

    def test_combat_screen_budget(self):
        run = core.Run(202)
        run.hero.deck = [('strike', False)] * 10
        run.hero.relics = ['horn']
        run.go(run.map.entry_ids[0])
        run.enter()
        combat = run.start_event_combat(['goblin', 'wolf', 'slime'])
        self.assertEqual(len(combat.hand), 7)
        io = FakeIO([])
        u = ui.UI(run, write=io.write, read=io.read, clear=io.clear)
        u._draw_combat(combat)
        self.assertLessEqual(len(io.out), 50)

    def test_scripted_win(self):
        run = core.Run(203)
        run.hero.deck = [('heavy', False)] * 10
        run.go(run.map.entry_ids[0])
        run.enter()
        # 单敌布阵，消除目标选择输入的歧义
        run.active.enemies = [core.EnemyInstance(content.ENEMIES['goblin'], 1)]
        u, io = ui_for(run, ['1', 'd', '1', '0', 'q', 'y'])
        result = u.play()
        text = '\n'.join(io.out)
        self.assertIn('战斗胜利', text)
        self.assertIsNone(run.pending)
        self.assertTrue(run.node_done)
        self.assertEqual(result['outcome'], 'aborted')

    def test_invalid_inputs_reprompt(self):
        run = core.Run(204)
        run.go(run.map.entry_ids[0])
        combat = run.enter()[1]
        u, io = ui_for(run, ['zzz', '', '99', 'd'])
        result = u.play()
        text = '\n'.join(io.out)
        reprompts = text.count('请重新')
        self.assertGreaterEqual(reprompts, 3)
        self.assertEqual(combat.turn, 2)
        self.assertEqual(result['outcome'], 'aborted')

    def test_eof_exits_gracefully(self):
        run = core.Run(205)
        u, io = ui_for(run, [])
        result = u.play()
        self.assertEqual(result['outcome'], 'aborted')

    def test_event_and_campfire_menus(self):
        run = core.Run(206)
        node = find_node(run, 'event')
        # 走到事件节点：手动定位一条可行入口路径
        force_node(run, node)
        u, io = ui_for(run, ['1', 'q', 'y'])
        result = u.play()
        self.assertGreater(len(io.out), 5)
        self.assertEqual(result['outcome'], 'aborted')


class Bot(object):
    """自动玩家：贪心出牌 + 简单路线偏好，用于整局冒烟。"""

    def __init__(self, run):
        self.run = run

    def play_run(self):
        run = self.run
        guard = 0
        while not run.finished and guard < 500:
            guard += 1
            if run.active is not None:
                self.fight(run.active)
                run.combat_finished()
            elif run.pending is not None:
                self.resolve_pending()
            elif run.current is None or run.node_done:
                nid = self.pick_move(run.choices())
                run.go(nid)
                kind, obj = run.enter()
                self.handle_node(kind, obj)
            else:
                kind = run.map.nodes[run.current].kind
                self.handle_node(kind, run.node_obj)
        return run

    def pick_move(self, opts):
        run = self.run
        score = {'campfire': 4, 'shop': 3, 'chest': 2, 'event': 1,
                 'combat': 0, 'elite': -1, 'boss': 0}
        if run.hero.hp >= run.hero.max_hp * 0.75:
            score['elite'] = 5
        best = max(opts, key=lambda nid: (
            score[run.map.nodes[nid].kind], -nid))
        return best

    def fight(self, combat):
        guard = 0
        while combat.status == 'playing' and guard < 200:
            guard += 1
            if combat.hero.hp < 20 and 'p_blood' in combat.hero.potions:
                combat.use_potion(combat.hero.potions.index('p_blood'))
                continue
            played = self.play_best(combat)
            if not played:
                combat.end_turn()

    def card_value(self, cid, combat):
        card = content.CARDS[cid]
        value = 0
        for eff in combat.effects_for(cid, False)[0]:
            if eff[0] in ('damage', 'pierce'):
                value += eff[1]
            elif eff[0] == 'damage_all':
                value += eff[1] * sum(1 for e in combat.enemies if e.alive)
            elif eff[0] == 'execute':
                value += eff[2]
            elif eff[0] == 'block' and combat.hero.hp < 50:
                value += eff[1]
            elif eff[0] == 'heal':
                value += eff[1] * (1 if combat.hero.hp < 40 else 0)
        if card.kind == 'power':
            value += 6
        return value

    def play_best(self, combat):
        playable = []
        for i, (cid, up) in enumerate(combat.hand):
            cost = combat._card_cost(content.CARDS[cid])
            if cost <= combat.energy:
                playable.append((self.card_value(cid, combat), i, cid))
        if not playable:
            return False
        playable.sort(reverse=True)
        _v, idx, cid = playable[0]
        target = None
        if content.CARDS[cid].kind == 'attack':
            alive = [(e.hp, j) for j, e in enumerate(combat.enemies)
                     if e.alive]
            if len(alive) > 1:
                target = min(alive)[1]
        combat.play_card(idx, target)
        return True

    def resolve_pending(self):
        p = self.run.pending
        if p['relic_choices']:
            self.run.choose_relic(0)
        elif p['card_choices']:
            self.run.take_card(0)
        else:
            self.run.pending = None

    def handle_node(self, kind, obj):
        run = self.run
        if kind in ('combat', 'elite', 'boss'):
            return
        if kind == 'campfire':
            opts = run.campfire_options()
            if not opts:
                return
            if run.hero.hp < run.hero.max_hp * 0.6:
                run.campfire('sleep')
            elif opts[1]['cards']:
                run.campfire('forge', opts[1]['cards'][0])
            elif opts[2]['available']:
                run.campfire('sharpen')
            else:
                run.campfire('leave')
        elif kind == 'event':
            for i in range(len(obj.options)):
                if core.event_option_available(run, obj, i):
                    lines, follow = core.apply_event(run, obj, i)
                    if follow is not None:
                        run.start_event_combat(follow[1])
                    break
        elif kind == 'chest':
            run.take_chest(True)
        elif kind == 'shop':
            self.shop()

    def shop(self):
        run = self.run
        if run.shop is None:
            run.close_shop()
            return
        want_potion = not any(p.startswith('p_') for p in
                              run.hero.potions)

        def power_of(kind, cid):
            if kind == 'weapon':
                return content.WEAPONS[cid].attack_bonus
            if kind == 'armor':
                return sum(v for k, v in content.ARMORS[cid].mods.items()
                           if k in ('start_block', 'thorns', 'heal'))
            if kind == 'relic':
                return {'common': 2, 'uncommon': 3, 'rare': 5}[
                    content.RELICS[cid].rarity]
            if kind == 'potion':
                return 2
            if kind == 'card':
                return content.CARDS[cid].cost + 1
            return 1

        buys = []
        for i, slot in enumerate(run.shop.slots):
            if slot.sold:
                continue
            if (slot.kind == 'weapon'
                    and power_of('weapon', slot.content_id)
                    <= core.merged_mods(run.hero)['attack_bonus']):
                continue
            if slot.kind == 'potion' and not want_potion:
                continue
            buys.append((power_of(slot.kind, slot.content_id), i))
        buys.sort(reverse=True)
        for power, i in buys:
            slot = run.shop.slots[i]
            if run.hero.gold >= slot.price + 20:
                core.buy(run, i)
                break
        run.close_shop()


class FullRunSimTests(unittest.TestCase):

    def run_bot(self, seed):
        run = core.Run(seed)
        Bot(run).play_run()
        return run

    def test_20_seeds_no_crash(self):
        reached_boss = 0
        for s in range(20):
            run = self.run_bot(5000 + s)
            self.assertTrue(run.finished, s)
            if run.depth_reached >= 11:
                reached_boss += 1
        self.assertGreaterEqual(reached_boss, 18)

    def test_fixed_seed_winnable(self):
        run = self.run_bot(900018)
        self.assertEqual(run.outcome, 'win', run.stats)

    def test_low_hp_endings_settle(self):
        dead_seen = 0
        for s in range(3):
            run = core.Run(6001 + s)
            run.hero.hp = 8
            Bot(run).play_run()
            self.assertTrue(run.finished)
            self.assertIn(run.outcome, ('win', 'dead'))
            self.assertIn('depth', run.stats)
            self.assertIn('kills', run.stats)
            merged = records.update_records(
                records.default_records(),
                dict(run.stats, outcome=run.outcome))
            self.assertEqual(merged['runs'], 1)
            if run.outcome == 'dead':
                dead_seen += 1
        self.assertGreaterEqual(dead_seen, 1)

    def test_main_module_smoke(self):
        import main as main_mod
        inputs = iter(['q', 'y', 'n'])
        outs = []
        d = tempfile.mkdtemp()
        result = main_mod.session(
            seed=987, read=lambda: next(inputs),
            write=outs.append,
            records_path=os.path.join(d, 'records.json'))
        self.assertEqual(result, 'exited')
        # aborted 局不计入战绩（计划决定）：战绩文件根本不产生
        self.assertFalse(os.path.exists(os.path.join(d, 'records.json')))


if __name__ == '__main__':
    unittest.main()
