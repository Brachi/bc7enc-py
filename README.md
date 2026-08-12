# pybc7

⚠️
This is a work in progress
⚠️


Python bindings for [bc7enc_rdo](https://github.com/richgel999/bc7enc_rdo), a state of the art RDO BC1-7 GPU texture encoder library.

## Development

CMake is required to build the bc7enc as a shared library. Test fixtures under
`tests/data/` are stored via [git-lfs](https://git-lfs.com/) — install it and
run `git lfs install` before cloning/pulling, or `pytest` will fail against
LFS pointer files instead of the real images.

```
# Development
pip install -e .[tests]

# Build wheel for the current platform (only Windows and Linux supported (64))
pip wheel
# or using build, which will provide a more verbose output
python -m build --wheel

# Running tests
pytest
```


## Usage


The API for now focus on cases for unpacking the dds data where no header might be present, hence the need to specify width, height and format.

```
from PIL import Image  # Optional
from pybc7 import unpack_dds

# Decoding

with open("/path/to/image.dds", "rb") as f:
    pixels = unpack_dds(
        f,
        1024, # width
        1024, # height
        "DXT1", # format -> DXT1 (BC1), DXT5 (BC3), or BC7
        128,  # Start of DDS data: 128 for the legacy DXT1/DXT3/DXT5 FourCC
              # header, 148 for formats stored via the DX10 extended header
              # (BC7 has no legacy FourCC, so it always uses this).
    )
    # Use the raw pixels to create a png image
    im = Image.frombytes("RGBA", (1024, 1024), bytes(pixels))
    im.save("/path/to/image.png")
```

Width and height don't need to be multiples of 4 (or powers of 2) — per the
DDS/BC spec, block storage rounds up (`ceil(width / 4) * ceil(height / 4)`
blocks), which `unpack_dds`/`compress_bc7_image` handle automatically.

```
from PIL import Image
from pybc7 import compress_bc7_image

# Encoding (BC7 only for now; there's no BC1/BC3 encode path yet)

im = Image.open("/path/to/image.png").convert("RGBA")
blocks = compress_bc7_image(im.tobytes(), im.width, im.height)
# `blocks` is raw BC7 block data (no DDS header). Wrapping it in a valid DDS
# container requires a DX10 extended header, since BC7 has no legacy FourCC
# — see tests/data/README.md for a worked example of building one.
```
