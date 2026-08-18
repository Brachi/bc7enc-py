#include "bc7enc_rdo/rgbcx.h"
#include "bc7enc_rdo/bc7decomp.h"
#include "bc7enc_rdo/bc7enc.h"

#include <cmath>

#ifdef _WIN32
    #define LIB_EXPORT __declspec(dllexport)
#else
    #define LIB_EXPORT
#endif


extern "C" LIB_EXPORT void init(rgbcx::bc1_approx_mode mode = rgbcx::bc1_approx_mode::cBC1Ideal) {
    return rgbcx::init(mode);
}

extern "C" LIB_EXPORT void bc7_init() {
    return bc7enc_compress_block_init();
}


extern "C" LIB_EXPORT bool unpack_bc1(const void* pBlock_bits, void* pPixels, bool set_alpha, rgbcx::bc1_approx_mode mode) {
    return rgbcx::unpack_bc1(pBlock_bits, pPixels, set_alpha, mode);
}


extern "C" LIB_EXPORT bool unpack_bc7(const void* pBlock, bc7decomp::color_rgba* pPixels) {
    return bc7decomp::unpack_bc7(pBlock, pPixels);
}


extern "C" LIB_EXPORT bool unpack_bc3(const void* pBlock_bits, void* pPixels, rgbcx::bc1_approx_mode mode) {
    return rgbcx::unpack_bc3(pBlock_bits, pPixels, mode);
}


extern "C" LIB_EXPORT void unpack_bc5(const void* pBlock_bits, void* pPixels, uint32_t chan0, uint32_t chan1, uint32_t stride) {
    rgbcx::unpack_bc5(pBlock_bits, pPixels, chan0, chan1, stride);
}


// Reconstructs a standard RGB tangent-space normal map from an AGNM-
// swizzled texture (Alpha-Green Normal Map, aka "DXT5nm": a console/GPU-
// vendor optimization - BC3/DXT5 has much higher-precision alpha than
// color, so X/Y get stored there instead of in RGB - "green" instead of
// the usual "purple" normal map look).
//   X (normal.x) <- alpha channel
//   Y (normal.y) <- green channel
//   Z (normal.z) -> not stored; reconstructed, since normal vectors are
//                    unit length: X^2 + Y^2 + Z^2 = 1
// Mutates rgba in place. EXPERIMENTAL: only reconstructs the positive Z
// hemisphere (sqrt is never negative), which holds for typical tangent-
// space normal maps but isn't validated beyond that; red/blue in the
// source are assumed unused.
extern "C" LIB_EXPORT void unswizzle_agnm(uint8_t *rgba, int width, int height) {
    int num_pixels = width * height;
    for (int i = 0; i < num_pixels; ++i) {
        uint8_t *p = rgba + i * 4;

        double x_byte = p[3];
        double y_byte = p[1];

        double x_norm = (x_byte / 255.0) * 2.0 - 1.0;
        double y_norm = (y_byte / 255.0) * 2.0 - 1.0;
        double z_sq = 1.0 - x_norm * x_norm - y_norm * y_norm;
        double z_norm = std::sqrt(z_sq > 0.0 ? z_sq : 0.0);
        double z_byte = (z_norm + 1.0) * 0.5 * 255.0;

        p[0] = (uint8_t)(x_byte + 0.5);
        p[1] = (uint8_t)(y_byte + 0.5);
        p[2] = (uint8_t)(z_byte + 0.5);
        p[3] = 255;
    }
}


// Reconstructs a standard RGB tangent-space normal map from an RXGB-
// swizzled texture (the Doom 3/idTech4 convention). Like AGNM, X moves to
// alpha for its higher precision, but unlike AGNM, Y and Z are still
// stored normally in green/blue (not reconstructed) - only the now-
// redundant red channel is discarded, conventionally filled with white.
// This gives it a pink/magenta cast rather than AGNM's green cast: red
// ends up constant-white in the raw encoding, vs. constant-near-zero.
//   X (normal.x) <- alpha channel (red is discarded, was filled with white)
//   Y (normal.y) <- green channel, unchanged
//   Z (normal.z) <- blue channel, unchanged
// Mutates rgba in place.
extern "C" LIB_EXPORT void unswizzle_rxgb(uint8_t *rgba, int width, int height) {
    int num_pixels = width * height;
    for (int i = 0; i < num_pixels; ++i) {
        uint8_t *p = rgba + i * 4;
        p[0] = p[3];  // R <- X (alpha)
        // G (Y) and B (Z) are already stored correctly, left as-is.
        p[3] = 255;
    }
}


// Resizes src (src_width x src_height RGBA) into caller-allocated dst
// (dst_width x dst_height RGBA) via a 2x2 box average. Only valid when
// dst dims are max(1, src_dim>>1) on each axis (i.e. one mip-chain step in
// a power-of-2 base image, per the standard mip halving rule) - the "axis
// already at 1" case is handled the same way DirectXTex's
// Generate2DMipsBoxFilter does, by resampling the same row/column twice
// instead of requiring square-only input.
extern "C" LIB_EXPORT void downsample_box(const uint8_t *src, int src_width, int src_height,
                                           uint8_t *dst, int dst_width, int dst_height) {
    for (int dy = 0; dy < dst_height; ++dy) {
        int sy0 = (src_height > 1) ? dy * 2 : 0;
        int sy1 = (src_height > 1) ? sy0 + 1 : sy0;
        for (int dx = 0; dx < dst_width; ++dx) {
            int sx0 = (src_width > 1) ? dx * 2 : 0;
            int sx1 = (src_width > 1) ? sx0 + 1 : sx0;

            const uint8_t *p00 = src + 4 * (sy0 * src_width + sx0);
            const uint8_t *p01 = src + 4 * (sy0 * src_width + sx1);
            const uint8_t *p10 = src + 4 * (sy1 * src_width + sx0);
            const uint8_t *p11 = src + 4 * (sy1 * src_width + sx1);
            uint8_t *out = dst + 4 * (dy * dst_width + dx);

            for (int c = 0; c < 4; ++c)
                out[c] = (uint8_t)((p00[c] + p01[c] + p10[c] + p11[c] + 2) / 4);
        }
    }
}

// General bilinear resize of src (src_width x src_height RGBA) into
// caller-allocated dst (dst_width x dst_height RGBA), for arbitrary
// dst dims relative to src (not just clean 2x downsampling). Fallback for
// mip generation on non-power-of-2 base images, matching how DirectXTex
// falls back to TEX_FILTER_LINEAR in that case.
extern "C" LIB_EXPORT void downsample_bilinear(const uint8_t *src, int src_width, int src_height,
                                                uint8_t *dst, int dst_width, int dst_height) {
    double x_ratio = (double)src_width / (double)dst_width;
    double y_ratio = (double)src_height / (double)dst_height;

    for (int dy = 0; dy < dst_height; ++dy) {
        double sy = (dy + 0.5) * y_ratio - 0.5;
        int sy0 = (int)std::floor(sy);
        double fy = sy - sy0;
        int sy0c = sy0 < 0 ? 0 : (sy0 >= src_height ? src_height - 1 : sy0);
        int sy1c = (sy0 + 1) < 0 ? 0 : ((sy0 + 1) >= src_height ? src_height - 1 : (sy0 + 1));

        for (int dx = 0; dx < dst_width; ++dx) {
            double sx = (dx + 0.5) * x_ratio - 0.5;
            int sx0 = (int)std::floor(sx);
            double fx = sx - sx0;
            int sx0c = sx0 < 0 ? 0 : (sx0 >= src_width ? src_width - 1 : sx0);
            int sx1c = (sx0 + 1) < 0 ? 0 : ((sx0 + 1) >= src_width ? src_width - 1 : (sx0 + 1));

            const uint8_t *p00 = src + 4 * (sy0c * src_width + sx0c);
            const uint8_t *p01 = src + 4 * (sy0c * src_width + sx1c);
            const uint8_t *p10 = src + 4 * (sy1c * src_width + sx0c);
            const uint8_t *p11 = src + 4 * (sy1c * src_width + sx1c);
            uint8_t *out = dst + 4 * (dy * dst_width + dx);

            for (int c = 0; c < 4; ++c) {
                double top = p00[c] * (1.0 - fx) + p01[c] * fx;
                double bot = p10[c] * (1.0 - fx) + p11[c] * fx;
                double val = top * (1.0 - fy) + bot * fy;
                out[c] = (uint8_t)(val + 0.5);
            }
        }
    }
}


extern "C" LIB_EXPORT bool pack_bc7_block(void *pBlock, const void *pPixelsRGBA, const bc7enc_compress_block_params *pComp_params) {
    return bc7enc_compress_block(pBlock, pPixelsRGBA, pComp_params);
}

// Shared block-iteration loop for whole-image block-compressed encoding.
// bc7enc_rdo only provides single-block encoders (bc7enc_compress_block,
// rgbcx::encode_bc1/bc3/bc5); this loops the image and hands each 4x4 block
// to whichever one-block encoder is passed in, so the format-specific
// functions below don't each duplicate it. width/height need not be
// multiples of 4 (per the DDS/BC spec, block storage always rounds up);
// edge blocks past the image bounds wrap the last valid row/column instead
// of reading out of bounds.
template <typename EncodeBlockFn>
static void compress_image_blocks(const uint8_t *rgba, int width, int height, void *blocks, int bytesPerBlock, EncodeBlockFn encode_block) {
    uint8_t* targetBlock = reinterpret_cast< uint8_t* >( blocks );

    for( int y = 0; y < height; y += 4 )
    {
        int bh = (height - y) < 4 ? (height - y) : 4;
        for( int x = 0; x < width; x += 4 )
        {
            int bw = (width - x) < 4 ? (width - x) : 4;

            // build the 4x4 block of pixels
            uint8_t sourceRgba[16*4];
            uint8_t* targetPixel = sourceRgba;
            for( int py = 0; py < 4; ++py )
            {
                for( int px = 0; px < 4; ++px )
                {
                    // get the source pixel in the image
                    int sx = x + (px % bw);
                    int sy = y + (py % bh);

                    // copy the rgba value
                    uint8_t const* sourcePixel = rgba + 4*( width*sy + sx );
                    for( int i = 0; i < 4; ++i )
                        *targetPixel++ = *sourcePixel++;
                }
            }
            // compress it into the output
            encode_block(targetBlock, sourceRgba);
            // advance
            targetBlock += bytesPerBlock;
        }
    }
}

extern "C" LIB_EXPORT void compress_image(uint8_t *rgba, int width, int height, void *blocks, const bc7enc_compress_block_params *pComp_params) {
    compress_image_blocks(rgba, width, height, blocks, 16, [pComp_params](uint8_t* dst, const uint8_t* src) {
        bc7enc_compress_block(dst, src, pComp_params);
    });
}

extern "C" LIB_EXPORT void compress_image_bc1(uint8_t *rgba, int width, int height, void *blocks, uint32_t level, bool allow_3color, bool use_transparent_texels_for_black) {
    compress_image_blocks(rgba, width, height, blocks, 8, [=](uint8_t* dst, const uint8_t* src) {
        rgbcx::encode_bc1(level, dst, src, allow_3color, use_transparent_texels_for_black);
    });
}

extern "C" LIB_EXPORT void compress_image_bc3(uint8_t *rgba, int width, int height, void *blocks, uint32_t level) {
    compress_image_blocks(rgba, width, height, blocks, 16, [level](uint8_t* dst, const uint8_t* src) {
        rgbcx::encode_bc3(level, dst, src);
    });
}

extern "C" LIB_EXPORT void compress_image_bc5(uint8_t *rgba, int width, int height, void *blocks, uint32_t chan0, uint32_t chan1) {
    compress_image_blocks(rgba, width, height, blocks, 16, [=](uint8_t* dst, const uint8_t* src) {
        rgbcx::encode_bc5(dst, src, chan0, chan1, 4);
    });
}


extern "C" LIB_EXPORT void rearrange_pixels(uint8_t* targetRgba, uint8_t* rgba, int x, int y, int width, int height) {
    /* move unpacked block pixels to correct location in image
     * Adapted from https://github.com/castano/nvidia-texture-tools/blob/master/src/nvtt/squish/squish.cpp#L176
    */
    uint8_t* sourcePixel = targetRgba;
    for( int py = 0; py < 4; ++py )
    {
        for( int px = 0; px < 4; ++px )
        {
            // get the target location
            int sx = x + px;
            int sy = y + py;
            if( sx < width && sy < height )
            {
                uint8_t* targetPixel = rgba + 4*( width*sy + sx );
                // copy the rgba value
                for( int i = 0; i < 4; ++i )
                    *targetPixel++ = *sourcePixel++;
            }
            else
            {
                // skip this pixel as its outside the image
                sourcePixel += 4;
            }
        }
    }
}
