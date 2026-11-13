# -*- coding: utf-8 -*-
"""json_tool 纯函数的单元测试。"""
import unittest

from json_tool import format_json


class FormatJsonSuccessTests(unittest.TestCase):
    def test_prettify_object_with_two_space_indent(self):
        ok, out, err = format_json('{"a":1,"b":[1,2]}', indent=2)
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertEqual(out, '{\n  "a": 1,\n  "b": [\n    1,\n    2\n  ]\n}')

    def test_prettify_keeps_chinese_readable(self):
        ok, out, err = format_json('{"名字":"张三"}', indent=2)
        self.assertTrue(ok)
        self.assertIn('"名字": "张三"', out)
        self.assertNotIn("\\u", out)

    def test_minify_removes_all_insignificant_whitespace(self):
        ok, out, err = format_json('{ "a" : 1 , "b" : [ 1 , 2 ] }', indent=None)
        self.assertTrue(ok)
        self.assertEqual(out, '{"a":1,"b":[1,2]}')

    def test_scalar_json_is_valid(self):
        ok, out, err = format_json('42', indent=2)
        self.assertTrue(ok)
        self.assertEqual(out, '42')


class FormatJsonErrorTests(unittest.TestCase):
    def test_error_reports_line_and_column(self):
        ok, out, err = format_json('{"a": 1,\n  "b" }\n', indent=2)
        self.assertFalse(ok)
        self.assertEqual(out, "")
        self.assertIn("第 2 行", err)
        self.assertIn("第 7 列", err)

    def test_empty_input_is_reported_as_error(self):
        ok, out, err = format_json("", indent=2)
        self.assertFalse(ok)
        self.assertIn("第 1 行", err)


if __name__ == "__main__":
    unittest.main()
