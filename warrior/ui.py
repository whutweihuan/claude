# -*- coding: utf-8 -*-
"""终端渲染与输入循环。IO 全部注入，便于脚本化测试。"""
import content

KIND_ICON = {'combat': '战', 'elite': '精', 'campfire': '火',
             'event': '事', 'shop': '店', 'chest': '宝', 'boss': '魔'}
KIND_NAME = {'combat': '战斗', 'elite': '精英', 'campfire': '火堆',
             'event': '事件', 'shop': '商店', 'chest': '宝箱',
             'boss': '魔王'}


class _Abort(Exception):
    pass


def _parse_int(s):
    """isdigit() 为真不代表 int() 可用（①/² 等），统一安全解析。"""
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


class UI(object):

    def __init__(self, run, write=None, read=None, clear=None):
        self.run = run
        self._write = write or print
        self._readline = read or input
        self._clear = clear
        self._last_event = None

    # ---------- 基础 IO ----------

    def w(self, s=''):
        self._write(s)

    def r(self):
        return self._readline().strip()

    def _screen(self):
        if self._clear:
            self._clear()

    def _ask_confirm_quit(self):
        self.w('放弃本局并离开山道？(y=确认)')
        if self.r().lower() == 'y':
            raise _Abort()

    # ---------- 主循环 ----------

    def play(self):
        try:
            self._title()
            run = self.run
            while not run.finished:
                if run.active is not None:
                    self._handle_combat(run.active)
                elif run.pending is not None:
                    self._handle_rewards()
                elif run.current is None or run.node_done:
                    node_id = self._map_and_choose()
                    run.go(node_id)
                    kind, obj = run.enter()
                    self._handle_node(kind, obj)
                else:
                    kind = run.map.nodes[run.current].kind
                    self._handle_node(kind, run.node_obj)
            return self._final_screen()
        except EOFError:
            self.w('（输入流结束了，先离开山道。）')
            return {'outcome': 'aborted', 'seed': self.run.seed,
                    'depth': self.run.depth_reached,
                    'kills': self.run.kills}
        except _Abort:
            return {'outcome': 'aborted', 'seed': self.run.seed,
                    'depth': self.run.depth_reached,
                    'kills': self.run.kills}

    def _title(self):
        self._screen()
        self.w('=' * 42)
        self.w('        勇 士 冒 险  (种子 %s)' % self.run.seed)
        self.w('   纯文字 roguelike · 目标：打到顶层的魔王')
        self.w('=' * 42)

    def _final_screen(self):
        run = self.run
        self._screen()
        stats = dict(run.stats)
        if run.outcome == 'win':
            self.w('*** 魔王倒下了。山道尽头透出晨光。***')
        else:
            self.w('你倒在了第 %d 层。勇士的传说还没有讲完。'
                   % stats.get('depth', 0))
        self.w('深度 %d · 击杀 %d · 累计金币 %d · 种子 %s'
               % (stats.get('depth', 0), stats.get('kills', 0),
                  stats.get('gold_earned', 0), stats.get('seed')))
        stats['outcome'] = run.outcome
        return stats

    # ---------- 地图 ----------

    def _map_and_choose(self):
        run = self.run
        while True:
            self._screen()
            self._status_bar()
            self._draw_map()
            opts = run.choices()
            self.w('---')
            for i, nid in enumerate(opts):
                node = run.map.nodes[nid]
                self.w('  %d. 节点 %d（%s）' % (i + 1, nid,
                                               KIND_NAME[node.kind]))
            self.w('输入编号移动；s=查看行囊；q=放弃本局')
            raw = self.r()
            if raw == 'q':
                self._ask_confirm_quit()  # 反悔则继续重打菜单
                continue
            if raw == 's':
                self._details()
                continue
            try:
                pick = int(raw)
            except ValueError:
                self.w('看不懂，请重新输入编号。')
                continue
            if 1 <= pick <= len(opts):
                return opts[pick - 1]
            self.w('没有这个编号，请重新输入。')

    def _draw_map(self):
        run = self.run
        layers = {}
        for node in run.map.nodes.values():
            layers.setdefault(node.layer, []).append(node)
        for layer in sorted(layers, reverse=True):
            cells = []
            for node in layers[layer]:
                icon = KIND_ICON[node.kind]
                if node.id == run.current:
                    mark = '[你:%s]' % icon
                elif node.id in run.visited:
                    mark = ' ×%s ' % icon
                elif node.id in run.choices():
                    mark = '(%d:%s)' % (node.id, icon)
                else:
                    mark = ' %s ' % icon
                cells.append(mark)
            self.w('L%-2d %s' % (layer, ' '.join(cells)))
        self.w('图例: 战=战斗 精=精英 火=火堆 事=事件 店=商店 宝=宝箱 魔=魔王')

    def _status_bar(self):
        hero = self.run.hero
        armor = content.ARMORS[hero.armor].name if hero.armor else '无'
        self.w('生命 %d/%d  金币 %d  武器【%s%s】 防具【%s】 遗物 %d 药水 %d/3'
               % (hero.hp, hero.max_hp, hero.gold,
                  content.WEAPONS[hero.weapon].name,
                  '+%d' % hero.weapon_sharpen if hero.weapon_sharpen else '',
                  armor, len(hero.relics), len(hero.potions)))

    def _details(self):
        hero = self.run.hero
        self.w('--- 行囊 ---')
        if hero.relics:
            for rid in hero.relics:
                self.w('遗物 ·【%s】%s' % (content.RELICS[rid].name,
                                           content.RELICS[rid].text))
        else:
            self.w('遗物：无')
        for pid in hero.potions:
            self.w('药水 ·【%s】%s' % (content.POTIONS[pid].name,
                                       content.POTIONS[pid].text))
        counts = {}
        for cid, up in hero.deck:
            key = (cid, up)
            counts[key] = counts.get(key, 0) + 1
        self.w('卡组 %d 张：%s' % (
            len(hero.deck),
            '、'.join('%s%s×%d' % (content.CARDS[cid].name,
                                   '+' if up else '', n)
                      for (cid, up), n in sorted(counts.items()))))

    # ---------- 节点处理 ----------

    def _handle_node(self, kind, obj):
        if kind in ('combat', 'elite', 'boss'):
            return  # 主循环会处理 active
        if kind == 'campfire':
            self._handle_campfire()
        elif kind == 'event':
            self._handle_event(obj)
        elif kind == 'chest':
            self._handle_chest(obj)
        elif kind == 'shop':
            self._handle_shop(obj)

    # ---------- 战斗 ----------

    def _draw_combat(self, combat):
        snap = combat.snapshot()
        self._screen()
        self.w('生命 %d/%d (格挡%d)  能量 %d  金币 %d  第%d回合'
               % (snap['hp'], snap['max_hp'], snap['block'],
                  snap['energy'], snap['gold'], snap['turn']))
        hero_stats = []
        if combat.strength:
            hero_stats.append('力量+%d' % combat.strength)
        if combat.vulnerable:
            hero_stats.append('易伤%d' % combat.vulnerable)
        if combat.poison:
            hero_stats.append('毒%d' % combat.poison)
        if hero_stats:
            self.w('你的状态: ' + '  '.join(hero_stats))
        alive = [(i, e) for i, e in enumerate(snap['enemies'])
                 if e['alive']]
        for i, e in alive:
            extra = []
            if e['block']:
                extra.append('格挡%d' % e['block'])
            if e['vulnerable']:
                extra.append('易伤%d' % e['vulnerable'])
            if e['poison']:
                extra.append('毒%d' % e['poison'])
            self.w('  %d.%s %d/%d  [%s]%s'
                   % (i + 1, e['name'], e['hp'], e['max_hp'],
                      e['intent'] or '…',
                      (' ' + '/'.join(extra)) if extra else ''))
        self.w('---')
        for card in snap['hand']:
            mark = ' ' if card['playable'] else '✗'
            star = '+' if card['upgraded'] else ''
            self.w('%s%d.【%s%s】费%d %s' % (mark, card['idx'] + 1,
                                           card['name'], star,
                                           card['cost'], card['text']))
        self.w('牌堆%d 弃牌%d' % (snap['draw_count'], snap['discard_count']))
        self.w('命令: 编号=出牌 d=结束 p=药水 i=详情')

    def _handle_combat(self, combat):
        run = self.run
        self.w('--- 遭遇 %s！---' % '、'.join(
            e.name for e in combat.enemies))
        while combat.status == 'playing':
            self._draw_combat(combat)
            raw = self.r()
            if raw == 'd':
                lines = combat.end_turn()
                self._echo(lines)
            elif raw == 'p':
                self._use_potion(combat)
            elif raw == 'i':
                self._details()
            else:
                try:
                    idx = int(raw) - 1
                except ValueError:
                    self.w('看不懂，请重新输入。')
                    continue
                if not (0 <= idx < len(combat.hand)):
                    self.w('没有这张牌，请重新选择。')
                    continue
                card_id, _up = combat.hand[idx]
                target = None
                card = content.CARDS[card_id]
                if card.kind == 'attack' \
                        and sum(1 for e in combat.enemies if e.alive) > 1:
                    target = self._pick_target(combat)
                lines = combat.play_card(idx, target)
                self._echo(lines)
        if combat.status == 'win':
            self.w('*** 战斗胜利！***')
            run.combat_finished()
        elif combat.status == 'lose':
            self.w('……视野暗了下去。')
            run.combat_finished()

    def _echo(self, lines):
        for l in lines:
            self.w(l)

    def _pick_target(self, combat):
        while True:
            self.w('选择目标编号（0=自动）：')
            raw = self.r()
            if raw == '0':
                return None
            try:
                idx = int(raw) - 1
            except ValueError:
                self.w('看不懂，请重新选择。')
                continue
            if 0 <= idx < len(combat.enemies) and combat.enemies[idx].alive:
                return idx
            self.w('没有这个目标，请重新选择。')

    def _use_potion(self, combat):
        hero = combat.hero
        if not hero.potions:
            self.w('没有药水。')
            return
        for i, pid in enumerate(hero.potions):
            self.w(' %d.【%s】%s' % (i + 1, content.POTIONS[pid].name,
                                     content.POTIONS[pid].text))
        self.w('编号使用，0=取消')
        raw = self.r()
        if raw == '0':
            return
        try:
            slot = int(raw) - 1
        except ValueError:
            self.w('看不懂，请重新输入。')
            return
        if not (0 <= slot < len(hero.potions)):
            self.w('没有这瓶药水。')
            return
        pid = hero.potions[slot]
        target = None
        if content.POTIONS[pid].targeted \
                and sum(1 for e in combat.enemies if e.alive) > 1:
            target = self._pick_target(combat)
        self._echo(combat.use_potion(slot, target))

    # ---------- 奖励 ----------

    def _handle_rewards(self):
        run = self.run
        p = run.pending
        self._echo(p['lines'])
        if p['relic_choices']:
            while run.pending is not None:
                self.w('拾取遗物（0=不拿）：')
                for i, rid in enumerate(p['relic_choices']):
                    relic = content.RELICS[rid]
                    self.w(' %d.【%s】%s' % (i + 1, relic.name, relic.text))
                raw = self.r()
                if raw == '0':
                    self._echo(run.skip_relic())
                else:
                    pick = _parse_int(raw)
                    if pick is not None and 1 <= pick <= len(p['relic_choices']):
                        self._echo(run.choose_relic(pick - 1))
                    else:
                        self.w('看不懂，请重新选择。')
            return
        if p['card_choices']:
            while run.pending is not None:
                self.w('三选一（0=跳过）：')
                for i, (cid, up) in enumerate(p['card_choices']):
                    card = content.CARDS[cid]
                    text = card.upgrade['text'] if up else card.text
                    self.w(' %d.【%s%s】费%d %s'
                           % (i + 1, card.name, '+' if up else '',
                              card.cost, text))
                raw = self.r()
                if raw == '0':
                    self._echo(run.skip_card())
                else:
                    pick = _parse_int(raw)
                    if pick is not None and 1 <= pick <= len(p['card_choices']):
                        self._echo(run.take_card(pick - 1))
                    else:
                        self.w('看不懂，请重新选择。')

    # ---------- 火堆 ----------

    def _handle_campfire(self):
        run = self.run
        self.w('火堆噼啪作响。')
        while not run.node_done and not run.finished:
            opts = run.campfire_options()
            for i, o in enumerate(opts):
                tail = '' if o['available'] else '（不可用）'
                self.w(' %d. %s%s' % (i + 1, o['text'], tail))
            self.w(' 4. 什么也不做，继续赶路')
            raw = self.r()
            if raw == '4':
                self._echo(run.campfire('leave'))
            elif raw == '1':
                self._echo(run.campfire('sleep'))
            elif raw == '2':
                slots = opts[1]['cards']
                if not slots:
                    self.w('没有可以锻造的牌。')
                    continue
                self.w('锻造哪张牌？（编号=卡组位置，0=取消）')
                for slot in slots:
                    cid, _up = run.hero.deck[slot]
                    self.w('  %d.【%s】' % (slot + 1,
                                            content.CARDS[cid].name))
                pick = self.r()
                if pick == '0':
                    continue
                pick_n = _parse_int(pick)
                if pick_n is not None and pick_n - 1 in slots:
                    self._echo(run.campfire('forge', int(pick) - 1))
                else:
                    self.w('看不懂，请重新输入。')
            elif raw == '3':
                self._echo(run.campfire('sharpen'))
            else:
                self.w('看不懂，请重新选择。')

    # ---------- 事件 ----------

    def _handle_event(self, event):
        run = self.run
        if event is None:
            run.finish_event()
            return
        self._last_event = event
        self.w('【%s】' % event.title)
        self.w(event.text)
        while True:
            for i, opt in enumerate(event.options):
                tail = '' if core_avail(run, event, i) else '（现在不行）'
                self.w(' %d. %s%s' % (i + 1, opt.label, tail))
            raw = self.r()
            pick = _parse_int(raw)
            if pick is None or not (1 <= pick <= len(event.options)):
                self.w('看不懂，请重新选择。')
                continue
            lines, follow = core_apply(run, event, pick - 1)
            self._echo(lines)
            if follow is None and run.node_done:
                return
            if follow is not None:
                run.start_event_combat(follow[1])
                return

    # ---------- 宝箱 ----------

    def _handle_chest(self, loot):
        run = self.run
        if loot is None:
            self.w('宝箱已经打开过了。')
            run.finish_event()
            return
        gear = (content.WEAPONS.get(loot['id'])
                or content.ARMORS.get(loot['id']))
        self.w('宝箱里有 %d 金币和【%s】：%s' % (loot['gold'], gear.name,
                                               gear.text))
        while not run.node_done and not run.finished:
            self.w(' 1. 装备/穿上   2. 只拿金币走人')
            raw = self.r()
            if raw == '1':
                self._echo(run.take_chest(True))
            elif raw == '2':
                self._echo(run.take_chest(False))
            else:
                self.w('看不懂，请重新选择。')

    # ---------- 商店 ----------

    def _handle_shop(self, shop):
        run = self.run
        self.w('“随便看，不还价。”')
        while not run.node_done and not run.finished:
            for i, slot in enumerate(shop.slots):
                if slot.sold:
                    self.w(' %d. ——已售罄——' % (i + 1))
                    continue
                name = item_name(slot.kind, slot.content_id)
                self.w(' %d.【%s】%d 金币' % (i + 1, name, slot.price))
            self.w(' r. 删一张牌（%d 金币）  d. 离开' % shop.remove_cost)
            raw = self.r()
            if raw == 'd':
                run.close_shop()
            elif raw == 'r':
                self.w('删哪张？（卡组位置编号，0=取消）')
                for j, (cid, up) in enumerate(run.hero.deck):
                    self.w('  %d.【%s%s】' % (j + 1,
                                             content.CARDS[cid].name,
                                             '+' if up else ''))
                pick = _parse_int(self.r())
                if pick is not None and pick >= 1:
                    self._echo(core_buy_removal(run, pick - 1))
            else:
                pick = _parse_int(raw)
                if pick is not None and 1 <= pick <= len(shop.slots):
                    self._echo(core_buy(run, pick - 1))
                    continue
                self.w('看不懂，请重新选择。')


# 惰性引用 core，避免循环依赖
import core as _core

core_avail = _core.event_option_available
core_apply = _core.apply_event
core_buy = _core.buy
core_buy_removal = _core.buy_removal


def item_name(kind, cid):
    if kind == 'card':
        return content.CARDS[cid].name
    if kind == 'weapon':
        return content.WEAPONS[cid].name
    if kind == 'armor':
        return content.ARMORS[cid].name
    if kind == 'relic':
        return content.RELICS[cid].name
    return content.POTIONS[cid].name
