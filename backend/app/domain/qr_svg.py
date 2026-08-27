from __future__ import annotations


VERSION = 5
SIZE = VERSION * 4 + 17
DATA_CODEWORDS = 108
ECC_CODEWORDS = 26
# Masked (ECC=L, mask=0) format-info codeword, verified bit-for-bit against
# the reference `qrcode` library's version-5/ECC-L/mask-0 output — the value
# this constant previously held did not match a real encoder's output.
FORMAT_BITS_L_MASK_0 = 0b001000111110111


def qr_svg(data: str, scale: int = 8, border: int = 4) -> str:
    raw = data.encode("utf-8")
    if len(raw) > 106:
        raise ValueError("QR data is too long for MVP encoder")
    matrix, reserved = _empty_matrix()
    _draw_patterns(matrix, reserved)
    codewords = _data_codewords(raw)
    full_codewords = codewords + _reed_solomon_remainder(codewords, ECC_CODEWORDS)
    bits = [((codeword >> shift) & 1) for codeword in full_codewords for shift in range(7, -1, -1)]
    _draw_data(matrix, reserved, bits)
    _draw_format_bits(matrix, reserved)
    return _matrix_to_svg(matrix, scale=scale, border=border)


def _empty_matrix() -> tuple[list[list[bool]], list[list[bool]]]:
    return (
        [[False for _ in range(SIZE)] for _ in range(SIZE)],
        [[False for _ in range(SIZE)] for _ in range(SIZE)],
    )


def _set(matrix: list[list[bool]], reserved: list[list[bool]], x: int, y: int, value: bool) -> None:
    if 0 <= x < SIZE and 0 <= y < SIZE:
        matrix[y][x] = value
        reserved[y][x] = True


def _format_info_coords() -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """The two 15-cell format-info strips that wrap the top-left finder, per
    ISO/IEC 18004. Shared by pattern reservation and by _draw_format_bits so
    the two can never drift apart (they previously did: a hand-mirrored
    reservation loop skipped index 6 on both the direct *and* mirrored side,
    but the mirrored side's index-6 cell isn't a timing-pattern collision —
    it under-reserved 2 real format-info cells and over-reserved 2 unrelated
    ones, which silently shifted every data bit placed after them)."""
    coords_1 = [(8, i) for i in range(6)] + [(8, 7), (8, 8), (7, 8)] + [(i, 8) for i in range(5, -1, -1)]
    coords_2 = [(SIZE - 1 - i, 8) for i in range(8)] + [(8, SIZE - 7 + i) for i in range(7)]
    return coords_1, coords_2


def _draw_patterns(matrix: list[list[bool]], reserved: list[list[bool]]) -> None:
    for x, y in ((0, 0), (SIZE - 7, 0), (0, SIZE - 7)):
        _draw_finder(matrix, reserved, x, y)
    for i in range(8, SIZE - 8):
        _set(matrix, reserved, i, 6, i % 2 == 0)
        _set(matrix, reserved, 6, i, i % 2 == 0)
    _draw_alignment(matrix, reserved, 30, 30)
    _set(matrix, reserved, 8, SIZE - 8, True)
    for coords in _format_info_coords():
        for x, y in coords:
            reserved[y][x] = True


def _draw_finder(matrix: list[list[bool]], reserved: list[list[bool]], x: int, y: int) -> None:
    for dy in range(-1, 8):
        for dx in range(-1, 8):
            xx, yy = x + dx, y + dy
            if not (0 <= xx < SIZE and 0 <= yy < SIZE):
                continue
            value = 0 <= dx <= 6 and 0 <= dy <= 6 and (dx in {0, 6} or dy in {0, 6} or 2 <= dx <= 4 and 2 <= dy <= 4)
            _set(matrix, reserved, xx, yy, value)


def _draw_alignment(matrix: list[list[bool]], reserved: list[list[bool]], cx: int, cy: int) -> None:
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            value = max(abs(dx), abs(dy)) in {0, 2}
            _set(matrix, reserved, cx + dx, cy + dy, value)


def _data_codewords(raw: bytes) -> list[int]:
    bits: list[int] = []
    bits.extend([0, 1, 0, 0])
    bits.extend((len(raw) >> shift) & 1 for shift in range(7, -1, -1))
    for byte in raw:
        bits.extend((byte >> shift) & 1 for shift in range(7, -1, -1))
    bits.extend([0] * min(4, DATA_CODEWORDS * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    codewords = [
        sum(bits[index + shift] << (7 - shift) for shift in range(8))
        for index in range(0, len(bits), 8)
    ]
    pads = (0xEC, 0x11)
    pad_index = 0
    while len(codewords) < DATA_CODEWORDS:
        codewords.append(pads[pad_index % 2])
        pad_index += 1
    return codewords


def _reed_solomon_remainder(data: list[int], degree: int) -> list[int]:
    generator = [1]
    for i in range(degree):
        generator = _poly_multiply(generator, [1, _gf_pow(2, i)])
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder.pop(0)
        remainder.append(0)
        if factor:
            for index in range(degree):
                remainder[index] ^= _gf_multiply(generator[index + 1], factor)
    return remainder


def _poly_multiply(left: list[int], right: list[int]) -> list[int]:
    result = [0] * (len(left) + len(right) - 1)
    for i, left_value in enumerate(left):
        for j, right_value in enumerate(right):
            result[i + j] ^= _gf_multiply(left_value, right_value)
    return result


def _gf_multiply(left: int, right: int) -> int:
    value = 0
    for _ in range(8):
        if right & 1:
            value ^= left
        carry = left & 0x80
        left = (left << 1) & 0xFF
        if carry:
            left ^= 0x1D
        right >>= 1
    return value


def _gf_pow(value: int, power: int) -> int:
    result = 1
    for _ in range(power):
        result = _gf_multiply(result, value)
    return result


def _draw_data(matrix: list[list[bool]], reserved: list[list[bool]], bits: list[int]) -> None:
    bit_index = 0
    upward = True
    x = SIZE - 1
    while x > 0:
        if x == 6:
            x -= 1
        rows = range(SIZE - 1, -1, -1) if upward else range(SIZE)
        for y in rows:
            for dx in (0, 1):
                xx = x - dx
                if reserved[y][xx]:
                    continue
                value = bits[bit_index] == 1 if bit_index < len(bits) else False
                if _mask_0(xx, y):
                    value = not value
                matrix[y][xx] = value
                bit_index += 1
        upward = not upward
        x -= 2


def _draw_format_bits(matrix: list[list[bool]], reserved: list[list[bool]]) -> None:
    coords_1, coords_2 = _format_info_coords()
    bits = [(FORMAT_BITS_L_MASK_0 >> i) & 1 == 1 for i in range(14, -1, -1)]
    for (x, y), value in zip(coords_1, bits):
        _set(matrix, reserved, x, y, value)
    for (x, y), value in zip(coords_2, bits):
        _set(matrix, reserved, x, y, value)


def _mask_0(x: int, y: int) -> bool:
    return (x + y) % 2 == 0


def _matrix_to_svg(matrix: list[list[bool]], scale: int, border: int) -> str:
    size = (SIZE + border * 2) * scale
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="QR code">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for y, row in enumerate(matrix):
        for x, value in enumerate(row):
            if value:
                parts.append(
                    f'<rect x="{(x + border) * scale}" y="{(y + border) * scale}" width="{scale}" height="{scale}" fill="#05070d"/>'
                )
    parts.append("</svg>")
    return "".join(parts)
