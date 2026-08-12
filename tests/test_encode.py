import io
import os

import numpy as np
from PIL import Image
from tests.conftest import DATA_OUT_DIR, psnr

from pybc7 import pack_dds, unpack_dds


def test_encoding(encode_sample):
    original_path = os.path.join(encode_sample.file_dir, encode_sample.original_file_name)
    original = Image.open(original_path).convert("RGBA")

    blocks = pack_dds(original.tobytes(), original.width, original.height, encode_sample.format)

    # unpack_dds only seeks past data_offset, it never parses header content,
    # so any padding of the right length stands in for a real DDS header.
    fake_header = b"\x00" * 128
    pixels = unpack_dds(
        io.BytesIO(fake_header + blocks),
        original.width,
        original.height,
        encode_sample.format,
        len(fake_header),
    )
    decoded = Image.frombytes("RGBA", (original.width, original.height), bytes(pixels))
    decoded.save(f"{os.path.join(DATA_OUT_DIR, encode_sample.original_file_name)}.{encode_sample.format}.png")

    score = psnr(np.array(original), np.array(decoded))
    assert score >= encode_sample.min_psnr_db, (
        f"encoded+decoded image too dissimilar from original ({encode_sample.original_file_name}, "
        f"{encode_sample.format}): PSNR={score:.2f}dB, expected >= {encode_sample.min_psnr_db}dB"
    )


def test_bc5_encoding():
    # BC5 only stores 2 channels (typically R/G, e.g. for normal maps), so
    # unlike the other formats it can't be judged on full-RGBA fidelity - the
    # other 2 channels are simply not encoded.
    original = Image.open(os.path.join("tests/data", "bluemarble.png")).convert("RGBA")

    blocks = pack_dds(original.tobytes(), original.width, original.height, "BC5")

    fake_header = b"\x00" * 128
    pixels = unpack_dds(
        io.BytesIO(fake_header + blocks),
        original.width,
        original.height,
        "BC5",
        len(fake_header),
    )
    decoded_arr = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(original.height, original.width, 4)

    original_arr = np.array(original)
    score = psnr(original_arr[..., :2], decoded_arr[..., :2])
    assert score >= 28.0, f"PSNR (R/G channels)={score:.2f}dB"
