cmake_minimum_required(VERSION 3.16)
project(crshe LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

option(WITH_OPENFHE "Build the real BFV backend (required for reported numbers)" ON)
option(WITH_NATIVE_ARCH "Compile with -march=native" ON)

# -----------------------------------------------------------------------------
# Architecture flags.  The DPF needs hardware AES; without it the code still
# builds and is still correct, but the throughput numbers are meaningless and
# every binary says so at startup.
# -----------------------------------------------------------------------------
include(CheckCXXCompilerFlag)
if(WITH_NATIVE_ARCH)
  check_cxx_compiler_flag("-march=native" HAS_MARCH_NATIVE)
  if(HAS_MARCH_NATIVE)
    add_compile_options(-march=native)
  endif()
endif()
if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
  check_cxx_compiler_flag("-march=armv8-a+crypto" HAS_ARMV8_CRYPTO)
  if(HAS_ARMV8_CRYPTO AND NOT WITH_NATIVE_ARCH)
    add_compile_options(-march=armv8-a+crypto)
  endif()
endif()
add_compile_options(-O3 -Wall -Wextra -Wno-unused-parameter)

find_package(OpenMP)

# -----------------------------------------------------------------------------
# Core library
# -----------------------------------------------------------------------------
add_library(crshe_core
  src/aes_prg.cpp
  src/zp.cpp
  src/dpf.cpp
  src/index.cpp
  src/dataset.cpp
  src/he_backend.cpp
  src/he_openfhe.cpp
  src/protocol.cpp
)
target_include_directories(crshe_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
if(OpenMP_CXX_FOUND)
  target_link_libraries(crshe_core PUBLIC OpenMP::OpenMP_CXX)
endif()

if(WITH_OPENFHE)
  find_package(OpenFHE QUIET)
  if(OpenFHE_FOUND)
    message(STATUS "OpenFHE found: ${OpenFHE_VERSION} -- real BFV backend enabled")
    target_compile_definitions(crshe_core PUBLIC CRSHE_WITH_OPENFHE=1)
    target_include_directories(crshe_core PUBLIC
      ${OpenFHE_INCLUDE}
      ${OpenFHE_INCLUDE}/third-party/include
      ${OpenFHE_INCLUDE}/core
      ${OpenFHE_INCLUDE}/pke
      ${OpenFHE_INCLUDE}/binfhe)
    target_link_directories(crshe_core PUBLIC ${OpenFHE_LIBDIR})
    target_link_libraries(crshe_core PUBLIC ${OpenFHE_SHARED_LIBRARIES})
  else()
    message(WARNING
      "OpenFHE not found. Building with the plaintext HE stand-in only: "
      "correctness tests will run, but no reportable HE numbers. "
      "Run scripts/install_openfhe.sh, then re-run cmake with "
      "-DCMAKE_PREFIX_PATH=<install-prefix>.")
  endif()
endif()

# -----------------------------------------------------------------------------
# Executables: every .cpp in apps/ becomes a binary of the same name.
# -----------------------------------------------------------------------------
file(GLOB CRSHE_APPS ${CMAKE_CURRENT_SOURCE_DIR}/apps/*.cpp)
foreach(app_src ${CRSHE_APPS})
  get_filename_component(app_name ${app_src} NAME_WE)
  add_executable(${app_name} ${app_src})
  target_link_libraries(${app_name} PRIVATE crshe_core)
endforeach()

enable_testing()
add_test(NAME dpf COMMAND test_dpf)
add_test(NAME he COMMAND test_he)
add_test(NAME e2e COMMAND test_e2e)
