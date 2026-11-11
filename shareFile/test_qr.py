import unittest

import share_qr


def _format_value(matrix):
    size = len(matrix)
    bits = []
    for i in range(6):
        bits.append(matrix[i][8])
    bits.append(matrix[7][8])
    bits.append(matrix[8][8])
    bits.append(matrix[8][7])
    for i in range(9, 15):
        bits.append(matrix[8][14 - i])
    value = 0
    for index, bit in enumerate(bits):
        if bit:
            value |= 1 << index
    return value


def _function_map(version):
    size = 17 + 4 * version
    dummy = [[False] * size for _ in range(size)]
    _, function = share_qr._new_matrix(version)
    share_qr._draw_function_patterns(dummy, function, version)
    return function


def _extract_codewords(matrix, version):
    size = len(matrix)
    function = _function_map(version)
    working = [list(row) for row in matrix]

    for y in range(size):
        for x in range(size):
            if not function[y][x] and (x + y) % 2 == 0:
                working[y][x] = not working[y][x]

    bits = []
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for offset in range(2):
                x = right - offset
                upward = ((right + 1) & 2) == 0
                y = size - 1 - vert if upward else vert
                if not function[y][x]:
                    bits.append(1 if working[y][x] else 0)
        right -= 2

    total = len(bits) // 8
    return [
        int("".join(str(bit) for bit in bits[index * 8:(index + 1) * 8]), 2)
        for index in range(total)
    ]


def _rs_valid(codewords, ecc_len):
    length = len(codewords)
    for index in range(ecc_len):
        total = 0
        for position, value in enumerate(codewords):
            power = (index * (length - 1 - position)) % 255
            total ^= share_qr._gf_mul(value, share_qr._EXP[power])
        if total:
            return False
    return True


def _decode(matrix):
    size = len(matrix)
    version = (size - 17) // 4
    ecc_len, blocks, data_total = share_qr._VERSIONS[version]
    stream = _extract_codewords(matrix, version)

    data_per_block = data_total // blocks
    data_blocks = [[0] * data_per_block for _ in range(blocks)]
    ecc_blocks = [[0] * ecc_len for _ in range(blocks)]

    index = 0
    for column in range(data_per_block):
        for block in range(blocks):
            data_blocks[block][column] = stream[index]
            index += 1
    for column in range(ecc_len):
        for block in range(blocks):
            ecc_blocks[block][column] = stream[index]
            index += 1

    for block in range(blocks):
        codewords = data_blocks[block] + ecc_blocks[block]
        if not _rs_valid(codewords, ecc_len):
            raise AssertionError("Reed-Solomon check failed")

    data = []
    for block in data_blocks:
        data.extend(block)

    bits = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)

    mode = 0
    for bit in bits[:4]:
        mode = (mode << 1) | bit
    length = 0
    for bit in bits[4:12]:
        length = (length << 1) | bit
    payload = []
    offset = 12
    for _ in range(length):
        value = 0
        for bit in bits[offset:offset + 8]:
            value = (value << 1) | bit
        payload.append(value)
        offset += 8

    if mode != 4:
        raise AssertionError("unexpected mode")
    return bytes(payload).decode("utf-8")


class QrStructureTests(unittest.TestCase):
    def test_finder_and_timing_patterns(self):
        text = "http://192.168.1.5:8000/"
        matrix = share_qr.encode(text)
        version = share_qr.choose_version(text)
        size = 17 + 4 * version
        self.assertEqual(len(matrix), size)

        for y in range(7):
            for x in range(7):
                expected = (
                    x in (0, 6)
                    or y in (0, 6)
                    or (2 <= x <= 4 and 2 <= y <= 4)
                )
                self.assertEqual(matrix[y][x], expected)

        for index in range(8, size - 8):
            self.assertEqual(matrix[6][index], index % 2 == 0)
            self.assertEqual(matrix[index][6], index % 2 == 0)

    def test_format_bits_for_m_mask_zero(self):
        matrix = share_qr.encode("x")
        self.assertEqual(_format_value(matrix), 0x5412)

    def test_roundtrip_decoder(self):
        for text in (
            "http://192.168.1.5:8000/",
            "http://10.0.0.2:8000/",
            "x",
            "http://255.255.255.255:65535/",
        ):
            with self.subTest(text=text):
                self.assertEqual(_decode(share_qr.encode(text)), text)

    def test_version_selection(self):
        self.assertEqual(share_qr.choose_version("a" * 14), 1)
        self.assertEqual(share_qr.choose_version("a" * 15), 2)
        self.assertEqual(share_qr.choose_version("a" * 30), 3)
        self.assertEqual(share_qr.choose_version("a" * 50), 4)
        self.assertEqual(share_qr.choose_version("a" * 80), 5)
        self.assertEqual(share_qr.choose_version("a" * 100), 6)
        with self.assertRaises(share_qr.QrError):
            share_qr.choose_version("a" * 107)
