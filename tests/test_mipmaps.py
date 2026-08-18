import ctypes
import io

import numpy as np
import pytest
from PIL import Image
from tests.conftest import DATA_DIR, psnr

from bc7enc import bc7, generate_mip_chain, pack_dds, unpack_dds


def _downsample(func, src_bytes, src_width, src_height, dst_width, dst_height):
    src_buf = ctypes.create_string_buffer(src_bytes, len(src_bytes))
    dst_buf = ctypes.create_string_buffer(dst_width * dst_height * 4)
    func(ctypes.byref(src_buf), src_width, src_height, ctypes.byref(dst_buf), dst_width, dst_height)
    return bytes(dst_buf)


def test_downsample_box():
    # 4x4 checkerboard: red/green alternating both directions. Each 2x2
    # destination cell covers exactly 2 red + 2 green source pixels, so the
    # exact expected average is (128, 128, 0, 255) - not an approximation.
    red, green = bytes([255, 0, 0, 255]), bytes([0, 255, 0, 255])
    src = b"".join(red if (x + y) % 2 == 0 else green for y in range(4) for x in range(4))

    out = _downsample(bc7.downsample_box, src, 4, 4, 2, 2)
    expected_pixel = bytes([128, 128, 0, 255])
    assert out == expected_pixel * 4

    # Degenerate case: one axis already at 1 (can't halve further). Box
    # filter must collapse to sampling that single row/column twice rather
    # than reading out of bounds.
    pixel = bytes([10, 20, 30, 255])
    src_1x4 = pixel * 4
    out = _downsample(bc7.downsample_box, src_1x4, 1, 4, 1, 2)
    assert out == pixel * 2


def test_downsample_bilinear():
    # 2x1 -> 1x1: destination pixel center maps exactly to the midpoint
    # between the two source pixels.
    src = bytes([0, 0, 0, 255]) + bytes([100, 200, 50, 255])
    out = _downsample(bc7.downsample_bilinear, src, 2, 1, 1, 1)
    assert out == bytes([50, 100, 25, 255])

    # 3x1 -> 2x1: a non-2x ratio, exercising the general (non-power-of-2
    # fallback) resize path with hand-computed expected weights.
    src = bytes([0, 0, 0, 255]) + bytes([100, 100, 100, 255]) + bytes([200, 200, 200, 255])
    out = _downsample(bc7.downsample_bilinear, src, 3, 1, 2, 1)
    assert out == bytes([25, 25, 25, 255]) + bytes([175, 175, 175, 255])


def test_generate_mip_chain_filter_selection_and_dimensions():
    # Power-of-2 base -> box filter, clean halving down to 1x1.
    levels = generate_mip_chain(b"\x00" * (256 * 256 * 4), 256, 256)
    assert [(w, h) for w, h, _ in levels] == [
        (256, 256), (128, 128), (64, 64), (32, 32), (16, 16), (8, 8), (4, 4), (2, 2), (1, 1),
    ]

    # Non-power-of-2 base -> bilinear fallback, floor-halving per axis.
    levels = generate_mip_chain(b"\x00" * (250 * 250 * 4), 250, 250)
    assert [(w, h) for w, h, _ in levels] == [
        (250, 250), (125, 125), (62, 62), (31, 31), (15, 15), (7, 7), (3, 3), (1, 1),
    ]

    # max_levels caps the chain without changing earlier levels' dimensions.
    capped = generate_mip_chain(b"\x00" * (256 * 256 * 4), 256, 256, max_levels=3)
    assert [(w, h) for w, h, _ in capped] == [(256, 256), (128, 128), (64, 64)]


def test_pack_dds_mipmaps_default_unchanged():
    original = Image.open(f"{DATA_DIR}/bluemarble.png").convert("RGBA")
    rgba = original.tobytes()

    single = pack_dds(rgba, original.width, original.height, "BC7")
    assert pack_dds(rgba, original.width, original.height, "BC7", mipmaps=False) == single
    assert pack_dds(rgba, original.width, original.height, "BC7") == single  # no mipmaps kwarg at all


@pytest.mark.parametrize("size", [(256, 256), (250, 250)], ids=["pow2", "non_pow2"])
def test_pack_dds_mipmaps_roundtrip(size):
    # No new fixture needed: derive both the power-of-2 and non-power-of-2
    # base images from the existing bluemarble.png fixture (same approach
    # as the non-multiple-of-4 regression test in test_decode.py).
    original = Image.open(f"{DATA_DIR}/bluemarble.png").convert("RGBA").resize(size)
    width, height = size

    blocks = pack_dds(original.tobytes(), width, height, "BC7", mipmaps=True)

    w, h = width, height
    offset = 0
    level = 0
    while True:
        size_bytes = ((w + 3) // 4) * ((h + 3) // 4) * 16
        level_blocks = blocks[offset:offset + size_bytes]

        fake_header = b"\x00" * 128
        pixels = unpack_dds(io.BytesIO(fake_header + level_blocks), w, h, "BC7", len(fake_header))
        decoded = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(h, w, 4)

        reference = np.array(original.resize((w, h), Image.LANCZOS))
        score = psnr(reference, decoded)
        # Loose floor: box/bilinear resampling vs. an independent LANCZOS
        # reference naturally diverge more at very small levels (a handful
        # of pixels, extreme downsampling ratio), on top of BC7's own
        # quantization - this just needs to catch a broken chain, not match
        # LANCZOS exactly.
        assert score >= 10.0, f"level {level} ({w}x{h}): PSNR={score:.2f}dB"

        offset += size_bytes
        level += 1
        if w == 1 and h == 1:
            break
        w = w // 2 if w > 1 else 1
        h = h // 2 if h > 1 else 1

    assert offset == len(blocks)
