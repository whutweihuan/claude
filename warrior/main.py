# -*- coding: utf-8 -*-
"""勇士冒险入口：python main.py 即玩。"""
import os
import time

import core
import records
import ui

HERE = os.path.dirname(os.path.abspath(__file__))
RECORDS_PATH = os.path.join(HERE, 'records.json')


def _default_seed():
    return time.time_ns() % 1000000


def session(seed=None, read=None, write=None, records_path=None,
            clear=None):
    """一局接一局的会话。返回 'exited'。IO 参数可注入（测试用）。"""
    read = read or input
    write = write or print
    records_path = records_path or RECORDS_PATH

    def w(s=''):
        write(str(s))

    data, status = records.load_records(records_path)
    can_save = True
    if status == 'io_error':
        w('战绩文件暂时读不到（可能被占用），本次不会写盘，原文件保持不动。')
        can_save = False
    elif status == 'corrupt':
        w('发现损坏的战绩文件，已隔离为 records.corrupt-*.json，从新记录。')

    while True:
        if seed is None:
            seed = _default_seed()
        run = core.Run(seed)
        game = ui.UI(run, write=w, read=read, clear=clear)
        result = game.play()
        if can_save and result.get('outcome') in ('win', 'dead'):
            data = records.update_records(data, result)
            if records.save_records(records_path, data) == 'io_error':
                w('战绩写入失败：本局结果未被记录（原文件未被破坏）。')
        w('战绩：%(runs)d 局 · %(wins)d 胜 · 最远第 %(best_layer)d 层 · '
          '总击杀 %(total_kills)d' % data)
        w('再来一局？(y=继续，其他=离开山道)')
        try:
            answer = read()
        except EOFError:
            return 'exited'
        if answer.strip().lower() != 'y':
            return 'exited'


def main():
    print('输入随机种子（回车=随机，可分享给朋友复现同一张地图）：')
    try:
        raw = input().strip()
    except EOFError:
        raw = ''
    seed = int(raw) if raw.isdigit() else None
    if seed is None:
        seed = _default_seed()
        print('本次种子：%d' % seed)

    def _clear():
        try:
            os.system('cls')
        except Exception:
            pass

    session(seed=seed, clear=_clear)
    print('勇士收剑。下次山道再见。')


if __name__ == '__main__':
    main()
