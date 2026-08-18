from array import array
import ctypes
import enum
import struct
from ctypes import byref
import os

bc7 = None
this_dir = os.path.dirname(__file__)

if not bc7:
    try:
        bc7 = ctypes.cdll.LoadLibrary(os.path.join(this_dir, 'bc7enc.so'))
    except OSError:
        bc7 = ctypes.cdll.LoadLibrary(os.path.join(this_dir, 'bc7enc.dll'))
    bc7.init(0)
    bc7.bc7_init()


class BC1ApproxMode(enum.IntEnum):
    """Mirrors rgbcx::bc1_approx_mode (bc7enc_rdo/rgbcx.h)."""
    IDEAL = 0
    NVIDIA = 1
    AMD = 2
    IDEAL_ROUND_4 = 3


class RGBA(ctypes.Structure):

    _fields_ = (
        ("r", ctypes.c_ubyte),
        ("g", ctypes.c_ubyte),
        ("b", ctypes.c_ubyte),
        ("a", ctypes.c_ubyte),
    )


class color_rgba(ctypes.Union):
    _anonymous_ = ("rgba",)
    _fields_ = (
        ("m_comps", ctypes.c_ubyte * 4),
        ("rgba", RGBA)
    )

DDS_FORMATS_BLOCK_SIZE = {
    "DXT1": (8, bc7.unpack_bc1),
    "DXT5": (16, bc7.unpack_bc3),
    "BC7": (16, bc7.unpack_bc7),
    "BC5": (16, bc7.unpack_bc5),
}


class  bc7enc_compress_block_params(ctypes.Structure):
    _fields_ = (
        ("m_mode_mask", ctypes.c_uint32 ),
        ("m_max_partitions", ctypes.c_uint32),
        ("m_weights", ctypes.c_uint32 * 4),
        ("m_uber_level", ctypes.c_uint32),
        ("m_perceptual", ctypes.c_bool),
        ("m_try_least_squares", ctypes.c_bool),
        ("m_mode17_partition_estimation_filterbank", ctypes.c_bool),
        ("m_force_alpha", ctypes.c_bool),
        ("m_force_selectors", ctypes.c_bool),
        ("m_selectors", ctypes.c_ubyte * 16),
        ("m_quant_mode6_endpoints", ctypes.c_bool),
        ("m_bias_mode1_pbits", ctypes.c_bool),
        ("m_pbit1_weight", ctypes.c_float),
        ("m_mode1_error_weight", ctypes.c_float),
        ("m_mode5_error_weight", ctypes.c_float),
        ("m_mode6_error_weight", ctypes.c_float),
        ("m_mode7_error_weight", ctypes.c_float),
        ("m_low_frequency_partition_weight", ctypes.c_float),
    )
        #uint32_t m_mode_mask;
        #uint32_t m_max_partitions;
        #uint32_t m_weights[4];
        #uint32_t m_uber_level;
        #bool m_perceptual;
        #bool m_try_least_squares;
        #bool m_mode17_partition_estimation_filterbank;
        #bool m_force_alpha;
        #bool m_force_selectors;
        #uint8_t m_selectors[16];
        #bool m_quant_mode6_endpoints;
        #bool m_bias_mode1_pbits;
        #float m_pbit1_weight;
        #float m_mode1_error_weight;
        #float m_mode5_error_weight;
        #float m_mode6_error_weight;
        #float m_mode7_error_weight;
        #float m_low_frequency_partition_weight;

def bc7enc_compress_block_params_init():
    p = bc7enc_compress_block_params(
        m_mode_mask=0xFFFFFFFF,
        m_max_partitions=64,
        m_try_least_squares=True,
        m_mode17_partition_estimation_filterbank=True,
        m_uber_level=0,
        m_force_selectors=False,
        m_force_alpha=False,
        m_quant_mode6_endpoints=False,
        m_bias_mode1_pbits=False,
        m_pbit1_weight=1.0,
        m_mode1_error_weight=1.0,
        m_mode5_error_weight=1.0,
        m_mode6_error_weight=1.0,
        m_mode7_error_weight=1.0,
        m_low_frequency_partition_weight=1.0,
        m_perceptual=True,
        m_weights=(ctypes.c_uint * 4)(128, 64, 16, 32),
    )
    return p


"""

inline void bc7enc_compress_block_params_init_perceptual_weights(bc7enc_compress_block_params *p)
{
	p->m_perceptual = true;
	p->m_weights[0] = 128;
	p->m_weights[1] = 64;
	p->m_weights[2] = 16;
	p->m_weights[3] = 32;
}


inline void bc7enc_compress_block_params_init(bc7enc_compress_block_params *p)
{
	p->m_mode_mask = UINT32_MAX;
	p->m_max_partitions = BC7ENC_MAX_PARTITIONS;
	p->m_try_least_squares = true;
	p->m_mode17_partition_estimation_filterbank = true;
	p->m_uber_level = 0;
	p->m_force_selectors = false;
	p->m_force_alpha = false;
	p->m_quant_mode6_endpoints = false;
	p->m_bias_mode1_pbits = false;
	p->m_pbit1_weight = 1.0f;
	p->m_mode1_error_weight = 1.0f;
	p->m_mode5_error_weight = 1.0f;
	p->m_mode6_error_weight = 1.0f;
	p->m_mode7_error_weight = 1.0f;
	p->m_low_frequency_partition_weight = 1.0f;
	bc7enc_compress_block_params_init_perceptual_weights(p);
}
"""



"""
struct bc7enc_compress_block_params
{
	uint32_t m_mode_mask;
	uint32_t m_max_partitions;
	uint32_t m_weights[4];
	uint32_t m_uber_level;
	bool m_perceptual;
	bool m_try_least_squares;
	bool m_mode17_partition_estimation_filterbank;
	bool m_force_alpha;
	bool m_force_selectors;
    uint8_t m_selectors[16];
	bool m_quant_mode6_endpoints;
    bool m_bias_mode1_pbits;
	float m_pbit1_weight;
	float m_mode1_error_weight;
	float m_mode5_error_weight;
	float m_mode6_error_weight;
	float m_mode7_error_weight;
	float m_low_frequency_partition_weight;
"""


def pack_bc7(rgba_bytes, params):
    # TODO: do more than one block of 16x16 rgba pixels
    dst_block = ctypes.create_string_buffer(16)
    rgba_ctypes = ctypes.create_string_buffer(rgba_bytes)

    bc7.pack_bc7_block(ctypes.byref(dst_block), ctypes.byref(rgba_ctypes), ctypes.byref(params))

    return bytes(dst_block)


# rgbcx.h: "If in doubt just use level 10" (range is MIN_LEVEL=0..MAX_LEVEL=18).
DEFAULT_LEVEL = 10


def _pack_dds_bc1(rgba_ptr, width, height, blocks_ptr, level=DEFAULT_LEVEL,
                   allow_3color=True, use_transparent_texels_for_black=False):
    bc7.compress_image_bc1(rgba_ptr, width, height, blocks_ptr,
                            level, allow_3color, use_transparent_texels_for_black)


def _pack_dds_bc3(rgba_ptr, width, height, blocks_ptr, level=DEFAULT_LEVEL):
    bc7.compress_image_bc3(rgba_ptr, width, height, blocks_ptr, level)


def _pack_dds_bc5(rgba_ptr, width, height, blocks_ptr, chan0=0, chan1=1):
    bc7.compress_image_bc5(rgba_ptr, width, height, blocks_ptr, chan0, chan1)


def _pack_dds_bc7(rgba_ptr, width, height, blocks_ptr, params=None):
    if params is None:
        params = bc7enc_compress_block_params_init()
    bc7.compress_image(rgba_ptr, width, height, blocks_ptr, ctypes.byref(params))


# bc7enc_rdo only provides single-block encoders (bc7enc_compress_block,
# rgbcx::encode_bc1/bc3/bc5); there's no whole-image DXT1/DXT3/DXT5 encoder
# to call directly. wrapper.cpp's compress_image_bc1/bc3/bc5 add that by
# reusing the same block-iteration loop as compress_image (BC7) - see
# compress_image_blocks() there - without modifying the bc7enc_rdo submodule.
PACK_DDS_FORMATS = {
    "DXT1": (8, _pack_dds_bc1),
    "DXT5": (16, _pack_dds_bc3),
    "BC7": (16, _pack_dds_bc7),
    "BC5": (16, _pack_dds_bc5),
}


def _pack_dds_single_level(rgba, width, height, pack_func, size_block, **kwargs):
    # Block storage rounds up: width/height need not be multiples of 4 (nor
    # powers of 2) per the DDS/BC spec; compress_image_blocks() in wrapper.cpp
    # clamps edge-block reads accordingly.
    blocks_wide = (width + 3) // 4
    blocks_high = (height + 3) // 4
    num_blocks = blocks_wide * blocks_high

    rgba = array("B", rgba)
    rgba_addr, _ = rgba.buffer_info()
    rgba_ptr = ctypes.c_void_p(rgba_addr)

    blocks = ctypes.create_string_buffer(num_blocks * size_block)

    pack_func(rgba_ptr, width, height, ctypes.byref(blocks), **kwargs)

    return bytes(blocks)


def _is_pow2(n):
    return n > 0 and (n & (n - 1)) == 0


def generate_mip_chain(rgba, width, height, max_levels=None):
    """
    Generates a mip chain from a base RGBA image: [(width, height,
    rgba_bytes), ...] starting with the (unchanged) base level down to
    1x1, or max_levels total if given. Each level's dimensions follow the
    standard mip halving rule (dim > 1 ? dim // 2 : 1), independent per
    axis - this is unrelated to the ceil-based block-count rounding
    pack_dds/unpack_dds do per level.

    bc7enc_rdo has no mip-generation of its own (it's a pure block
    compressor - see wrapper.cpp's compress_image_blocks); this uses a 2x2
    box filter when both base dimensions are powers of 2 (exact averaging,
    since every level then halves cleanly), and falls back to a general
    bilinear resize otherwise, mirroring DirectXTex's own fallback rule
    (see wrapper.cpp's downsample_box/downsample_bilinear).
    """
    downsample = bc7.downsample_box if (_is_pow2(width) and _is_pow2(height)) else bc7.downsample_bilinear

    cur_width, cur_height = width, height
    cur_bytes = bytes(rgba)
    levels = [(cur_width, cur_height, cur_bytes)]

    while cur_width > 1 or cur_height > 1:
        if max_levels is not None and len(levels) >= max_levels:
            break

        next_width = cur_width // 2 if cur_width > 1 else 1
        next_height = cur_height // 2 if cur_height > 1 else 1

        cur_buf = ctypes.create_string_buffer(cur_bytes, len(cur_bytes))
        next_buf = ctypes.create_string_buffer(next_width * next_height * 4)
        downsample(ctypes.byref(cur_buf), cur_width, cur_height, ctypes.byref(next_buf), next_width, next_height)

        cur_width, cur_height = next_width, next_height
        cur_bytes = bytes(next_buf)
        levels.append((cur_width, cur_height, cur_bytes))

    return levels


def pack_dds(rgba, width, height, dds_format, mipmaps=False, **kwargs):
    if dds_format not in PACK_DDS_FORMATS:
        raise TypeError(f"Invalid DDS format: {dds_format}")

    size_block, pack_func = PACK_DDS_FORMATS[dds_format]

    if not mipmaps:
        return _pack_dds_single_level(rgba, width, height, pack_func, size_block, **kwargs)

    max_levels = mipmaps if isinstance(mipmaps, int) and mipmaps is not True else None
    levels = generate_mip_chain(rgba, width, height, max_levels=max_levels)

    return b"".join(
        _pack_dds_single_level(level_rgba, level_width, level_height, pack_func, size_block, **kwargs)
        for level_width, level_height, level_rgba in levels
    )


# See wrapper.cpp's unswizzle_agnm/unswizzle_rxgb for the algorithm/rationale
# of each. Each entry is called as swizzle_func(ctypes.byref(rgba), width,
# height) and mutates the decoded RGBA buffer in place.
SWIZZLES = {
    "agnm": bc7.unswizzle_agnm,  # aka "DXT5nm"; green cast
    "rxgb": bc7.unswizzle_rxgb,  # Doom 3/idTech4 convention; pink/magenta cast
}


def unpack_dds(file_handle, width, height, dds_format, data_offset, unswizzle=None):

    if dds_format not in DDS_FORMATS_BLOCK_SIZE:
        raise TypeError(f"Invalid DDS format: {dds_format}")

    if unswizzle is not None and unswizzle not in SWIZZLES:
        raise TypeError(f"Invalid unswizzle: {unswizzle}")

    SIZE_BLOCK, unpack_func = DDS_FORMATS_BLOCK_SIZE[dds_format]

    # Block storage rounds up: width/height need not be multiples of 4 per the
    # DDS/BC spec, and rearrange_pixels() already clamps edge-block writes.
    blocks_wide = (width + 3) // 4
    blocks_high = (height + 3) // 4
    num_blocks = blocks_wide * blocks_high

    file_handle.seek(data_offset)
    rgba = ctypes.create_string_buffer(width * height * 4)
    blocks_processed = 0

    for h in range(0, height, 4):
        for w in range(0, width, 4):
            block_bytes = ctypes.create_string_buffer(file_handle.read(SIZE_BLOCK))
            result_pixels = (color_rgba * 16)()
            if dds_format == "DXT1":
                unpack_func(ctypes.byref(block_bytes), ctypes.byref(result_pixels), True, BC1ApproxMode.IDEAL)
            elif dds_format == "DXT5":
                unpack_func(ctypes.byref(block_bytes), ctypes.byref(result_pixels), BC1ApproxMode.IDEAL)
            elif dds_format == "BC5":
                # Only writes the 2 selected channels per pixel (chan0/chan1);
                # result_pixels is zero-initialized, so the other 2 stay 0.
                unpack_func(ctypes.byref(block_bytes), ctypes.byref(result_pixels), 0, 1, 4)
            else:
                unpack_func(ctypes.byref(block_bytes), ctypes.byref(result_pixels))

            bc7.rearrange_pixels(byref(result_pixels), byref(rgba), w, h, width, height)
            blocks_processed += 1

    assert blocks_processed == num_blocks, f"blocks processed: {blocks_processed}, {num_blocks}"

    if unswizzle is not None:
        SWIZZLES[unswizzle](byref(rgba), width, height)

    return rgba
