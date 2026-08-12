import os
from dataclasses import dataclass

import pytest

DATA_DIR = "tests/data"
DATA_OUT_DIR = "tests-output"


@dataclass
class DDSSample:
    file_dir: str
    file_name: str
    width: int
    height: int
    format: str
    original_file_name: str  # uncompressed source image the DDS was encoded from, for similarity comparison
    # BC1/BC3 are lossy; the achievable PSNR depends on the source content (smooth
    # photos compress far better than sharp synthetic edges), so the pass/fail
    # floor is set per-fixture rather than as one global constant.
    min_psnr_db: float = 28.0
    # Legacy DXT1/DXT3/DXT5 FourCC headers are a fixed 128 bytes. BC7 has no legacy
    # FourCC, so it's stored via the DX10 extended header, which adds 20 bytes.
    data_offset: int = 128


DATA = [
    DDSSample(
        DATA_DIR,
        "bluemarble-BC1-NOMIPS.dds",
        256, 256, "DXT1",
        "bluemarble.png",
    ),
    DDSSample(
        DATA_DIR,
        "bluemarble-BC3-NOMIPS.dds",
        256, 256, "DXT5",
        "bluemarble.png",
    ),
    DDSSample(
        DATA_DIR,
        "alphablend-BC3-NOMIPS.dds",
        256, 256, "DXT5",
        "alphablend.png",
        min_psnr_db=24.0,  # sharp text/gradient edges compress worse than a natural photo
    ),
    DDSSample(
        DATA_DIR,
        "bluemarble-BC7-NOMIPS.dds",
        256, 256, "BC7",
        "bluemarble.png",
        min_psnr_db=38.0,  # BC7 is a much higher-fidelity codec than BC1/BC3
        data_offset=148,
    ),
]

@pytest.fixture(params=DATA)
def dds_sample(request):
    return request.param


def pytest_sessionstart():
    try:
        os.mkdir(DATA_OUT_DIR)
    except FileExistsError:
        pass

