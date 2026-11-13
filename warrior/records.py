# -*- coding: utf-8 -*-
"""战绩记录：原子写 + 三路径读取（不存在/损坏/I-O 错误分开处理）。"""
import json
import os
import time

DEFAULT_PATH = 'records.json'

FIELDS = ('runs', 'wins', 'deaths', 'best_layer', 'total_kills',
          'last_seed', 'history')


def default_records():
    return {
        'runs': 0,
        'wins': 0,
        'deaths': 0,
        'best_layer': 0,
        'total_kills': 0,
        'last_seed': None,
        'history': [],
    }


_INT_FIELDS = ('runs', 'wins', 'deaths', 'best_layer', 'total_kills')


def _validate_shape(data):
    """合法 JSON 也要过类型关：类型不符按损坏处理，避免 update 阶段崩溃。"""
    if not isinstance(data, dict):
        raise ValueError('not a dict')
    for key in _INT_FIELDS:
        value = data.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError('bad field %s' % key)
    seed = data.get('last_seed', 0)
    if seed is not None and (isinstance(seed, bool)
                             or not isinstance(seed, int)):
        raise ValueError('bad last_seed')
    history = data.get('history', [])
    if not isinstance(history, list) \
            or any(not isinstance(item, dict) for item in history):
        raise ValueError('bad history')


def load_records(path=DEFAULT_PATH):
    """返回 (records, status)；status ∈ ok/missing/corrupt/io_error。

    corrupt：原文件改名 records.corrupt-<时间戳>.json，返回空记录。
    io_error：文件读不到（占用等），绝不改名、绝不视为损坏。
    """
    try:
        with open(path, encoding='utf-8') as f:
            raw = f.read()
    except FileNotFoundError:
        return default_records(), 'missing'
    except OSError:
        return default_records(), 'io_error'
    try:
        data = json.loads(raw)
        _validate_shape(data)
    except ValueError:
        stamp = time.strftime('%Y%m%d-%H%M%S')
        target = os.path.join(os.path.dirname(os.path.abspath(path)),
                              'records.corrupt-%s.json' % stamp)
        try:
            os.rename(path, target)
        except OSError:
            pass
        return default_records(), 'corrupt'
    merged = default_records()
    for key in FIELDS:
        if key in data:
            merged[key] = data[key]
    return merged, 'ok'


def save_records(path, data):
    """临时文件 + os.replace 原子替换。返回 ok/io_error。"""
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return 'io_error'
    return 'ok'


def update_records(current, stats):
    """纯函数：把一局结算并入累计记录。history 只留最近 10 局。"""
    data = dict(current)
    data['history'] = list(data.get('history', []))
    data['runs'] = data.get('runs', 0) + 1
    outcome = stats.get('outcome', 'dead')
    if outcome == 'win':
        data['wins'] = data.get('wins', 0) + 1
    else:
        data['deaths'] = data.get('deaths', 0) + 1
    data['best_layer'] = max(data.get('best_layer', 0),
                             stats.get('depth', 0))
    data['total_kills'] = data.get('total_kills', 0) + stats.get('kills', 0)
    data['last_seed'] = stats.get('seed')
    data['history'].append({
        'date': time.strftime('%Y-%m-%d %H:%M'),
        'outcome': outcome,
        'depth': stats.get('depth', 0),
        'seed': stats.get('seed'),
    })
    data['history'] = data['history'][-10:]
    return data
