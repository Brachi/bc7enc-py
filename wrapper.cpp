#include "bc7enc_rdo/rgbcx.h"
#include "bc7enc_rdo/bc7decomp.h"
#include "bc7enc_rdo/bc7enc.h"

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


extern "C" LIB_EXPORT bool pack_bc7_block(void *pBlock, const void *pPixelsRGBA, const bc7enc_compress_block_params *pComp_params) {
    return bc7enc_compress_block(pBlock, pPixelsRGBA, pComp_params);
}

extern "C" LIB_EXPORT void compress_image(uint8_t *rgba, int width, int height, void *blocks, const bc7enc_compress_block_params *pComp_params) {

    // BC7 only; DXT1/DXT3/DXT5 encoding isn't implemented here yet.
    int bytesPerBlock = 16;

    // initialise the block output
    uint8_t* targetBlock = reinterpret_cast< uint8_t* >( blocks );

    // loop over blocks. width/height need not be multiples of 4 (per the DDS/BC
    // spec, block storage always rounds up); edge blocks past the image bounds
    // wrap the last valid row/column instead of reading out of bounds.
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
            bc7enc_compress_block(targetBlock, sourceRgba, pComp_params);
            // advance
            targetBlock += bytesPerBlock;
        }
    }

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
