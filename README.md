# bc7enc-py

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
from bc7enc import unpack_dds

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
blocks), which `unpack_dds`/`pack_dds` handle automatically.

**Experimental:** `unpack_dds` also accepts an optional `unswizzle` argument,
for reconstructing a standard RGB tangent-space normal map from one that's
been swizzled to exploit BC3/DXT5's higher-precision alpha channel (X moved
into alpha instead of the usual RGB layout):

- `"agnm"` (Alpha-Green Normal Map, aka "DXT5nm"): X <- alpha, Y <- green,
  Z is not stored at all and gets reconstructed from X/Y since normal
  vectors are unit length. Decoded without the swizzle, these textures
  look flat green instead of the usual purple.
- `"rxgb"` (the Doom 3/idTech4 convention): X <- alpha; unlike `"agnm"`,
  Y and Z are still stored normally in green/blue, so no reconstruction is
  needed for them — only the now-redundant red channel is discarded
  (conventionally filled with white). Decoded without the swizzle, these
  textures look pink/magenta instead of purple.

```
pixels = unpack_dds(f, 1024, 1024, "DXT5", 128, unswizzle="agnm")  # or "rxgb"
```

```
from PIL import Image
from bc7enc import pack_dds

# Encoding

im = Image.open("/path/to/image.png").convert("RGBA")
blocks = pack_dds(im.tobytes(), im.width, im.height, "BC7")  # or DXT1, DXT5, BC5
# `blocks` is raw block data (no DDS header). Wrapping it in a valid DDS
# container requires a DX10 extended header for BC7/BC5 (no legacy FourCC)
# — see tests/data/README.md for a worked example of building one.
```

`pack_dds` accepts format-specific keyword arguments, forwarded to the
underlying encoder:
- `DXT1`/`BC1`: `level` (0-18, default 10), `allow_3color`, `use_transparent_texels_for_black`
- `DXT5`/`BC3`: `level` (0-18, default 10)
- `BC5`: `chan0`, `chan1` — which two source channels to encode (default 0, 1 i.e. R, G)
- `BC7`: `params`, a `bc7enc_compress_block_params` (defaults to `bc7enc_compress_block_params_init()`)

bc7enc_rdo only exposes single 4x4-block encoders (`bc7enc_compress_block`,
`rgbcx::encode_bc1`/`encode_bc3`/`encode_bc5`) — there's no whole-image DXT1/
DXT3/DXT5 encoder to call directly. `pack_dds` gets this by looping blocks in
`wrapper.cpp` (our own file) and calling whichever single-block encoder the
format needs, without modifying the bc7enc_rdo submodule itself.

**Mipmaps:** bc7enc_rdo has no concept of mip levels either — it's a pure
block compressor, same posture as Microsoft's
[DirectXTex](https://github.com/microsoft/DirectXTex) (whose `GenerateMipMaps`
and `CompressEx` are entirely separate: one resamples an uncompressed image,
the other loops over an already-built chain compressing each level
independently). `pack_dds` follows the same split — it's opt-in and doesn't
change the function's return type:

```
blocks = pack_dds(im.tobytes(), im.width, im.height, "BC7", mipmaps=True)
# blocks is still plain bytes: every mip level's block data concatenated in
# order (base level first), same "no DDS header" contract as the single-
# level case. mipmaps=<int> caps the chain at that many levels instead of
# going all the way down to 1x1.
```

Level dimensions follow the standard mip halving rule (`dim > 1 ? dim // 2 : 1`,
independent per axis). Resampling uses a 2x2 box filter when both base
dimensions are powers of 2 (exact averaging, since every level then halves
cleanly), and falls back to a general bilinear resize otherwise — mirroring
DirectXTex's own fallback rule (`TEX_FILTER_BOX` only for power-of-2 input,
`TEX_FILTER_LINEAR` otherwise). See `generate_mip_chain` and wrapper.cpp's
`downsample_box`/`downsample_bilinear`.
