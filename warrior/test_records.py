# -*- coding: utf-8 -*-
"""战绩存档安全测试（审查重点 3 全在此）。"""
import glob
import json
import os
import tempfile
import unittest
from unittest import mock

import records


class RecordsTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'records.json')

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_returns_defaults(self):
        data, status = records.load_records(self.path)
        self.assertEqual(status, 'missing')
        self.assertEqual(data, records.default_records())

    def test_roundtrip_ok(self):
        data, _ = records.load_records(self.path)
        data['runs'] = 3
        self.assertEqual(records.save_records(self.path, data), 'ok')
        loaded, status = records.load_records(self.path)
        self.assertEqual(status, 'ok')
        self.assertEqual(loaded['runs'], 3)

    def test_corrupt_json_renamed_and_defaults(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write('{not json!!')
        data, status = records.load_records(self.path)
        self.assertEqual(status, 'corrupt')
        self.assertEqual(data, records.default_records())
        corrupted = glob.glob(os.path.join(self.tmp.name,
                                          'records.corrupt-*.json'))
        self.assertEqual(len(corrupted), 1)
        with open(corrupted[0], encoding='utf-8') as f:
            self.assertEqual(f.read(), '{not json!!')
        self.assertFalse(os.path.exists(self.path))

    def test_permission_error_does_not_overwrite(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write('{"runs": 42}')
        original = open(self.path, 'rb').read()
        with mock.patch('records.os.replace',
                        side_effect=PermissionError('locked')):
            status = records.save_records(self.path, {'runs': 1})
        self.assertEqual(status, 'io_error')
        self.assertEqual(open(self.path, 'rb').read(), original)

    def test_io_error_on_read_is_not_corruption(self):
        # PermissionError 读取失败不能走"损坏改名"路径，原文件必须原样存在
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'runs': 7}))
        real_open = open

        def denied(path, *a, **kw):
            if path == self.path:
                raise PermissionError('locked')
            return real_open(path, *a, **kw)

        with mock.patch('builtins.open', side_effect=denied):
            data, status = records.load_records(self.path)
        self.assertEqual(status, 'io_error')
        self.assertEqual(data, records.default_records())
        self.assertEqual(json.loads(real_open(self.path,
                                              encoding='utf-8').read())
                         ['runs'], 7)
        self.assertEqual(glob.glob(os.path.join(self.tmp.name,
                                                'records.corrupt-*')), [])

    def test_update_records_counters(self):
        data = records.default_records()
        for i in range(12):
            outcome = 'win' if i % 4 == 0 else 'dead'
            data = records.update_records(
                data, {'outcome': outcome, 'depth': i, 'seed': 100 + i,
                       'kills': 5})
        self.assertEqual(data['runs'], 12)
        self.assertEqual(data['wins'], 3)
        self.assertEqual(data['deaths'], 9)
        self.assertEqual(data['best_layer'], 11)
        self.assertEqual(data['total_kills'], 60)
        self.assertEqual(len(data['history']), 10)
        self.assertEqual(data['last_seed'], 111)
        for item in data['history']:
            self.assertIn('date', item)
            self.assertIn('outcome', item)


if __name__ == '__main__':
    unittest.main()
