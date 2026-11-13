# -*- coding: utf-8 -*-
"""整局编排、事件、商店与集成冒烟测试。"""
import unittest

import content
import core


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


if __name__ == '__main__':
    unittest.main()
