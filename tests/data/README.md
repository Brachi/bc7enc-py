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
