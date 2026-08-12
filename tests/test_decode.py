import io
import os

import numpy as np
from PIL import Image
from tests.conftest import DATA_DIR, DATA_OUT_DIR

from pybc7 import compress_bc7_image, unpack_dds


def psnr(reference, sample):
    mse = np.mean((reference.astype(np.float64) - sample.astype(np.float64)) ** 2)
    if mse == 0:
        return float("inf")
    return 10 * np.log10((255.0 ** 2) / mse)


def test_decoding(dds_sample):
    file_path = os.path.join(dds_sample.file_dir, dds_sample.file_name)
    with open(file_path, "rb") as f:
        pixels = unpack_dds(
            f,
            dds_sample.width,
            dds_sample.height,
            dds_sample.format,
            dds_sample.data_offset,
        )
        decoded = Image.frombytes("RGBA", (dds_sample.width, dds_sample.height), bytes(pixels))
        decoded.save(f"{os.path.join(DATA_OUT_DIR, dds_sample.file_name)}.png")

    original_path = os.path.join(dds_sample.file_dir, dds_sample.original_file_name)
    original = Image.open(original_path).convert("RGBA")

    decoded_arr = np.array(decoded)
    original_arr = np.array(original)

    assert decoded_arr.shape == original_arr.shape

    score = psnr(original_arr, decoded_arr)
    assert score >= dds_sample.min_psnr_db, (
        f"decoded image too dissimilar from original ({dds_sample.original_file_name}): "
        f"PSNR={score:.2f}dB, expected >= {dds_sample.min_psnr_db}dB"
    )


def test_bc7_roundtrip_non_multiple_of_4_dimensions():
    # Regression test: block storage must round up (ceil(dim / 4)), not down.
    # A previous floor-division bug undersized the compress_bc7_image output
    # buffer for any width/height not a multiple of 4, causing a heap buffer
    # overflow (observed as a hard process crash, not a Python exception) on
    # encode, and a spurious AssertionError on decode. The DDS/BC spec fully
    # supports non-multiple-of-4 (and non-power-of-2) texture dimensions, so
    # this is a real, common case rather than an edge case to reject.
    width, height = 250, 250
    original = Image.open(os.path.join(DATA_DIR, "bluemarble.png")).convert("RGBA")
    original = original.resize((width, height))

    blocks = compress_bc7_image(original.tobytes(), width, height)

    fake_header = b"\x00" * 148  # unpack_dds only seeks past data_offset
    pixels = unpack_dds(io.BytesIO(fake_header + blocks), width, height, "BC7", len(fake_header))
    decoded_arr = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(height, width, 4)

    score = psnr(np.array(original), decoded_arr)
    assert score >= 38.0, f"PSNR={score:.2f}dB"
