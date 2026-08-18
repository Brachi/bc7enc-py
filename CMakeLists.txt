cmake_minimum_required(VERSION 3.5)
project(bc7enc)


set (BC7ENC_SRC_LIST
	bc7enc_rdo/bc7enc.cpp
	bc7enc_rdo/bc7enc.h
	bc7enc_rdo/bc7decomp.cpp
	bc7enc_rdo/bc7decomp.h
	bc7enc_rdo/rgbcx.cpp
	bc7enc_rdo/rgbcx.h
	wrapper.cpp
	)

set(CMAKE_SHARED_LIBRARY_PREFIX "")
add_library(bc7enc SHARED ${BC7ENC_SRC_LIST})
