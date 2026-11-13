# -*- coding: utf-8 -*-
"""JSON 字符串格式化的纯逻辑，供界面和测试共用。"""
import json


def format_json(text, indent=2):
    """解析并重新输出 JSON 字符串。

    返回 (ok, 输出文本, 错误信息)。失败时输出文本为空串。
    indent=None 表示压缩为单行。
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, "", "第 %d 行 第 %d 列:%s" % (exc.lineno, exc.colno, exc.msg)
    except (ValueError, TypeError) as exc:
        return False, "", str(exc)
    if indent is None:
        out = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        out = json.dumps(data, ensure_ascii=False, indent=indent)
    return True, out, ""
