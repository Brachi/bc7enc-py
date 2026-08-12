# Test fixtures

Each DDS fixture is paired with the uncompressed source image it was encoded
from, so `test_decoding` can compare our decoder's output against a
known-good original.

DXT1/DXT5 fixtures are encoded with Pillow's independent encoder, so the
DDS is never produced by the code under test. Pillow has no BC7 writer, so
the BC7 fixture is instead encoded with this project's own
`pack_dds` (bc7enc_rdo) and wrapped in a hand-built DX10 DDS
header (128-byte legacy header + 20-byte DX10 extension, `dxgiFormat =
BC7_UNORM`) — meaning that fixture exercises encode+decode as a round
trip rather than independently verifying the decoder. The PSNR-against-
original check still catches gross corruption, but a bug that is
symmetric between our encoder and decoder wouldn't be caught by it.

- `bluemarble.png` — *The Earth seen from Apollo 17* (NASA, 1972). Public
  domain (NASA material is not protected by copyright, 17 U.S.C. § 105).
  Source: https://upload.wikimedia.org/wikipedia/commons/9/97/The_Earth_seen_from_Apollo_17.jpg
  - `bluemarble-BC1-NOMIPS.dds` — encoded as DXT1/BC1 (Pillow).
  - `bluemarble-BC3-NOMIPS.dds` — encoded as DXT5/BC3 (Pillow).
  - `bluemarble-BC7-NOMIPS.dds` — encoded as BC7 (this project's own encoder).

- `alphablend.png` — cropped/resized from `AlphaBlendLabels.png`, part of the
  Khronos glTF-Sample-Assets `AlphaBlendModeTest` model. Chosen for its real
  alpha gradient (full 0-255 range), to exercise BC3's alpha interpolation.
  © 2018 Analytical Graphics, Inc. / Ed Mackey. Licensed
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode).
  Source: https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/AlphaBlendModeTest
  - `alphablend-BC3-NOMIPS.dds` — encoded as DXT5/BC3.

- `normalmap.png` — cropped/resized from `NormalTangentTest_Normal.png`,
  part of the Khronos glTF-Sample-Assets `NormalTangentTest` model (a
  purpose-built asset for testing normal-map handling). A genuine
  tangent-space normal map (purple/blue, R=X, G=Y, B=Z), used as
  license-clean test data for the `unswizzle` feature — there's no real
  captured swizzled texture in this repo, to avoid committing a
  copyrighted game asset. © 2018 Analytical Graphics, Inc. / Ed Mackey.
  Licensed [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/legalcode).
  Source: https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/NormalTangentTest
  - `normalmap-swizzled-agnm-BC3-NOMIPS.dds` — `normalmap.png` swizzled
    into AGNM/"DXT5nm" layout (X->alpha, Y->green, red/blue unused) and
    encoded as DXT5/BC3 (Pillow). Decoded normally this looks flat green;
    `unpack_dds(..., unswizzle="agnm")` should reconstruct `normalmap.png`.
  - `normalmap-swizzled-rxgb-BC3-NOMIPS.dds` — `normalmap.png` swizzled
    into RXGB layout (X->alpha, red filled with white, green/blue
    unchanged) and encoded as DXT5/BC3 (Pillow). Decoded normally this
    looks pink/magenta; `unpack_dds(..., unswizzle="rxgb")` should
    reconstruct `normalmap.png`.

## Building a BC7 DDS file

There's no DDS writer in this project (or in Pillow) for BC7, so
`bluemarble-BC7-NOMIPS.dds` was built by hand: encode raw blocks with
`pack_dds`, then prepend a standard 128-byte DDS header plus the
20-byte DX10 extension that `dxgiFormat = BC7_UNORM` (98) requires, since
BC7 has no legacy FourCC of its own.

```python
import struct
from PIL import Image
from pybc7 import pack_dds

def make_dds_dx10_header(width, height, dxgi_format):
    magic = b"DDS "
    header_size = 124
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000  # CAPS | HEIGHT | WIDTH | PIXELFORMAT | LINEARSIZE
    pitch_or_linear_size = width * height
    pf_size, pf_flags, pf_fourcc = 32, 0x4, b"DX10"  # DDPF_FOURCC

    header = struct.pack("<4sIIIIIII", magic, header_size, flags, height, width,
                          pitch_or_linear_size, 0, 0)  # depth, mipmapcount
    header += struct.pack("<11I", *([0] * 11))  # reserved1
    header += struct.pack("<II4sIIIII", pf_size, pf_flags, pf_fourcc, 0, 0, 0, 0, 0)
    header += struct.pack("<IIIII", 0x1000, 0, 0, 0, 0)  # caps=DDSCAPS_TEXTURE, caps2-4, reserved2
    assert len(header) == 128

    dx10_header = struct.pack("<IIIII", dxgi_format, 3, 0, 1, 0)  # TEXTURE2D, arraySize=1
    return header + dx10_header

DXGI_FORMAT_BC7_UNORM = 98

im = Image.open("bluemarble.png").convert("RGBA")
blocks = pack_dds(im.tobytes(), im.width, im.height, "BC7")
header = make_dds_dx10_header(im.width, im.height, DXGI_FORMAT_BC7_UNORM)

with open("bluemarble-BC7-NOMIPS.dds", "wb") as f:
    f.write(header)
    f.write(blocks)
```

## Building the swizzle fixtures

```python
import numpy as np
from PIL import Image

# normalmap.png itself: NormalTangentTest_Normal.png resized to 256x256
# im = Image.open("NormalTangentTest_Normal.png").convert("RGBA")
# im.resize((256, 256), Image.LANCZOS).save("normalmap.png")

normal = np.array(Image.open("normalmap.png").convert("RGBA"))

agnm = np.zeros_like(normal)
agnm[..., 3] = normal[..., 0]  # X -> alpha
agnm[..., 1] = normal[..., 1]  # Y -> green
# red/blue left at 0: unused by AGNM
Image.fromarray(agnm).save("normalmap-swizzled-agnm-BC3-NOMIPS.dds", pixel_format="DXT5")

rxgb = normal.copy()
rxgb[..., 0] = 255             # red filled with white
rxgb[..., 3] = normal[..., 0]  # X -> alpha
# green (Y), blue (Z) unchanged
Image.fromarray(rxgb).save("normalmap-swizzled-rxgb-BC3-NOMIPS.dds", pixel_format="DXT5")
```
