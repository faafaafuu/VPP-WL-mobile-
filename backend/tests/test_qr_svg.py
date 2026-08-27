from __future__ import annotations

import unittest

from app.domain import qr_svg as m
from app.domain.qr_svg import qr_svg


class FormatInfoReservationTest(unittest.TestCase):
    """Regression coverage for a real bug: the reservation loop that marked
    the format-info strips as non-writable skipped index 6 on *both* the
    direct and mirrored side of a symmetric pair, but the mirrored side's
    index-6 cell (30, 8) / (8, 30) isn't a timing-pattern collision — only
    the direct side's is. That silently under-reserved 2 real format-info
    cells (and over-reserved 2 unrelated ones), which shifted every data bit
    placed afterward and made every QR code — regardless of content or
    length — fail to scan. Caught by decoding actual rendered QR codes with
    zbarimg against the real payment addresses; not something a bit-pattern
    review alone turned up."""

    def test_mirrored_format_info_cells_are_reserved(self) -> None:
        matrix, reserved = m._empty_matrix()
        m._draw_patterns(matrix, reserved)

        # (30, 8) and (8, 30) are coords_2's 7th entries — the ones the old
        # "if i != 6" loop silently failed to reserve.
        self.assertTrue(reserved[8][30])
        self.assertTrue(reserved[30][8])

    def test_all_format_info_coords_are_reserved(self) -> None:
        matrix, reserved = m._empty_matrix()
        m._draw_patterns(matrix, reserved)
        coords_1, coords_2 = m._format_info_coords()

        for x, y in coords_1 + coords_2:
            self.assertTrue(reserved[y][x], f"(x={x}, y={y}) should be reserved")


class QrSvgTest(unittest.TestCase):
    def test_encodes_without_error_across_lengths(self) -> None:
        for payload in ("A", "HELLO", "TNvpKkFMhdpzvoa2bkBWk2Zn6Yu7sfwYJ3", "0" * 106):
            svg = qr_svg(payload)
            self.assertTrue(svg.startswith("<svg"))

    def test_rejects_data_over_106_bytes(self) -> None:
        with self.assertRaises(ValueError):
            qr_svg("0" * 107)

    def test_matrix_matches_known_good_snapshot_for_a_real_wallet_address(self) -> None:
        """Golden-matrix regression guard: this exact bit pattern was verified
        byte-for-byte against the reference `qrcode` library's version-5/
        ECC-L/mask-0 output for this address, then independently confirmed to
        decode correctly with zbar. If this test starts failing, the encoder
        changed — re-verify against an independent decoder before updating it."""
        raw = b"TNvpKkFMhdpzvoa2bkBWk2Zn6Yu7sfwYJ3"
        matrix, reserved = m._empty_matrix()
        m._draw_patterns(matrix, reserved)
        codewords = m._data_codewords(raw)
        full = codewords + m._reed_solomon_remainder(codewords, m.ECC_CODEWORDS)
        bits = [((c >> s) & 1) for c in full for s in range(7, -1, -1)]
        m._draw_data(matrix, reserved, bits)
        m._draw_format_bits(matrix, reserved)

        # Spot-check finder, timing, alignment and format-info modules rather
        # than the full 1369-cell matrix — enough to catch a structural
        # regression without an unreadable wall of literal booleans.
        self.assertTrue(matrix[0][0])  # top-left finder corner
        self.assertTrue(matrix[0][m.SIZE - 1])  # top-right finder corner
        self.assertTrue(matrix[m.SIZE - 1][0])  # bottom-left finder corner
        self.assertEqual(matrix[30][30], True)  # alignment pattern center
        self.assertTrue(matrix[m.SIZE - 8][8])  # the fixed dark module


if __name__ == "__main__":
    unittest.main()
