"""纯 Python 的 QR Code Model 2 编码器（byte 模式，M 纠错，版本 1-6）。

只用于生成局域网地址这类短文本。没有第三方依赖；不实现版本 7 以上的
版本信息块，也不做掩码惩罚值评估（固定使用调用方指定的掩码，默认 0）。
"""

_VERSIONS = {
    # version: (每块纠错码字数, 块数, 数据码字总数)
    1: (10, 1, 16),
    2: (16, 1, 28),
    3: (26, 1, 44),
    4: (18, 2, 64),
    5: (24, 2, 86),
    6: (16, 4, 108),
}

_ALIGNMENT = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
}

_EC_LEVEL_M_BITS = 0
_FORMAT_XOR = 0x5412
_FORMAT_POLY = 0x537


class QrError(ValueError):
    pass


_EXP = [0] * 512
_LOG = [0] * 256


def _init_tables():
    value = 1
    for index in range(255):
        _EXP[index] = value
        _LOG[value] = index
        value <<= 1
        if value & 0x100:
            value ^= 0x11D
    for index in range(255, 512):
        _EXP[index] = _EXP[index - 255]


_init_tables()


def _gf_mul(left, right):
    if left == 0 or right == 0:
        return 0
    return _EXP[_LOG[left] + _LOG[right]]


def _rs_generator(degree):
    poly = [1]
    for index in range(degree):
        nxt = [0] * (len(poly) + 1)
        factor = _EXP[index]
        for position, coefficient in enumerate(poly):
            nxt[position] ^= coefficient
            nxt[position + 1] ^= _gf_mul(coefficient, factor)
        poly = nxt
    return poly


def _rs_remainder(data, degree):
    generator = _rs_generator(degree)
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder[0]
        remainder = remainder[1:] + [0]
        if factor:
            for index in range(degree):
                remainder[index] ^= _gf_mul(generator[index + 1], factor)
    return remainder


def _append_bits(bits, value, length):
    for shift in range(length - 1, -1, -1):
        bits.append((value >> shift) & 1)


def _build_data_codewords(payload, data_total):
    bits = []
    _append_bits(bits, 0b0100, 4)
    _append_bits(bits, len(payload), 8)
    for byte in payload:
        _append_bits(bits, byte, 8)

    capacity = data_total * 8
    bits.extend([0] * min(4, capacity - len(bits)))
    while len(bits) % 8:
        bits.append(0)

    codewords = []
    for index in range(0, len(bits), 8):
        value = 0
        for bit in bits[index:index + 8]:
            value = (value << 1) | bit
        codewords.append(value)

    pad = 0xEC
    while len(codewords) < data_total:
        codewords.append(pad)
        pad = 0x11 if pad == 0xEC else 0xEC

    return codewords


def _interleave(data, version):
    ecc_per_block, blocks, data_total = _VERSIONS[version]
    data_per_block = data_total // blocks
    data_blocks = [
        data[index * data_per_block:(index + 1) * data_per_block]
        for index in range(blocks)
    ]
    ecc_blocks = [_rs_remainder(block, ecc_per_block) for block in data_blocks]

    result = []
    for column in range(data_per_block):
        for block in data_blocks:
            result.append(block[column])
    for column in range(ecc_per_block):
        for block in ecc_blocks:
            result.append(block[column])
    return result


def choose_version(text):
    payload = text.encode("utf-8")
    for version in sorted(_VERSIONS):
        if len(payload) <= _VERSIONS[version][2] - 2:
            return version
    raise QrError("content is too long for QR versions 1-6")


def _new_matrix(version):
    size = 17 + 4 * version
    return (
        [[False] * size for _ in range(size)],
        [[False] * size for _ in range(size)],
    )


def _set_function(matrix, function, x, y, value):
    matrix[y][x] = bool(value)
    function[y][x] = True


def _draw_finder(matrix, function, x0, y0):
    size = len(matrix)
    for dy in range(-1, 8):
        for dx in range(-1, 8):
            x = x0 + dx
            y = y0 + dy
            if not (0 <= x < size and 0 <= y < size):
                continue
            if 0 <= dx < 7 and 0 <= dy < 7:
                dark = (
                    dx in (0, 6)
                    or dy in (0, 6)
                    or (2 <= dx <= 4 and 2 <= dy <= 4)
                )
            else:
                dark = False
            _set_function(matrix, function, x, y, dark)


def _draw_function_patterns(matrix, function, version):
    size = len(matrix)

    _draw_finder(matrix, function, 0, 0)
    _draw_finder(matrix, function, size - 7, 0)
    _draw_finder(matrix, function, 0, size - 7)

    for index in range(8, size - 8):
        _set_function(matrix, function, index, 6, index % 2 == 0)
        _set_function(matrix, function, 6, index, index % 2 == 0)

    centers = _ALIGNMENT[version]
    if centers:
        last = centers[-1]
        for center_y in centers:
            for center_x in centers:
                if (
                    (center_x == 6 and center_y == 6)
                    or (center_x == 6 and center_y == last)
                    or (center_x == last and center_y == 6)
                ):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        dark = max(abs(dx), abs(dy)) != 1
                        _set_function(
                            matrix, function, center_x + dx, center_y + dy, dark
                        )

    _set_function(matrix, function, 8, size - 8, True)

    for index in range(6):
        function[index][8] = True
    function[7][8] = True
    function[8][8] = True
    function[8][7] = True
    for index in range(9, 15):
        function[8][14 - index] = True
    for index in range(8):
        function[8][size - 1 - index] = True
    for index in range(8, 15):
        function[size - 15 + index][8] = True


def _place_data(matrix, function, codewords):
    size = len(matrix)
    bits = []
    for codeword in codewords:
        _append_bits(bits, codeword, 8)

    index = 0
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for offset in range(2):
                x = right - offset
                upward = ((right + 1) & 2) == 0
                y = size - 1 - vert if upward else vert
                if not function[y][x] and index < len(bits):
                    matrix[y][x] = bool(bits[index])
                    index += 1
        right -= 2


def _mask_condition(mask, x, y):
    if mask == 0:
        return (x + y) % 2 == 0
    if mask == 1:
        return y % 2 == 0
    if mask == 2:
        return x % 3 == 0
    if mask == 3:
        return (x + y) % 3 == 0
    if mask == 4:
        return (y // 2 + x // 3) % 2 == 0
    if mask == 5:
        return (x * y) % 2 + (x * y) % 3 == 0
    if mask == 6:
        return ((x * y) % 2 + (x * y) % 3) % 2 == 0
    return ((x + y) % 2 + (x * y) % 3) % 2 == 0


def _apply_mask(matrix, function, mask):
    size = len(matrix)
    for y in range(size):
        for x in range(size):
            if not function[y][x] and _mask_condition(mask, x, y):
                matrix[y][x] = not matrix[y][x]


def _format_bits(mask):
    data = (_EC_LEVEL_M_BITS << 3) | mask
    remainder = data
    for _ in range(10):
        remainder = (remainder << 1) ^ ((remainder >> 9) * _FORMAT_POLY)
    return ((data << 10) | remainder) ^ _FORMAT_XOR


def _draw_format(matrix, mask):
    size = len(matrix)
    bits = _format_bits(mask)

    def bit(index):
        return (bits >> index) & 1

    for index in range(6):
        matrix[index][8] = bool(bit(index))
    matrix[7][8] = bool(bit(6))
    matrix[8][8] = bool(bit(7))
    matrix[8][7] = bool(bit(8))
    for index in range(9, 15):
        matrix[8][14 - index] = bool(bit(index))

    for index in range(8):
        matrix[8][size - 1 - index] = bool(bit(index))
    for index in range(8, 15):
        matrix[size - 15 + index][8] = bool(bit(index))


def encode(text, version=None, mask=0):
    if version is None:
        version = choose_version(text)
    if version not in _VERSIONS:
        raise QrError("unsupported QR version")
    if not 0 <= mask <= 7:
        raise QrError("mask must be 0-7")

    payload = text.encode("utf-8")
    data_total = _VERSIONS[version][2]
    if len(payload) > data_total - 2:
        raise QrError("content does not fit in the requested version")

    data = _build_data_codewords(payload, data_total)
    codewords = _interleave(data, version)

    matrix, function = _new_matrix(version)
    _draw_function_patterns(matrix, function, version)
    _place_data(matrix, function, codewords)
    _apply_mask(matrix, function, mask)
    _draw_format(matrix, mask)

    return matrix
