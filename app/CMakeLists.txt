# Mirror's Edge (Xbox 360) Native Static Recompilation (ReXGlue SDK + Vulkan NVK)

cmake_minimum_required(VERSION 3.25)
project(mirrorsedge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(REXSDK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../sdk" CACHE PATH "Path to the ReXGlue SDK source tree")

if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/generated/rexglue.cmake")
    message(FATAL_ERROR "app/generated/rexglue.cmake is missing: run tools/codegen.sh first")
endif()
include(generated/rexglue.cmake)

set(MIRRORSEDGE_SOURCES
    src/main.cpp
    src/me_packaged.cpp
    src/native/me_native_system.cpp
    src/native/me_heap_report.cpp
    src/native/me_hang_watchdog.cpp
    src/native/mirrorsedge/masseffect_native_draws.cpp
    src/native/mirrorsedge/masseffect_deferred_recording.cpp
    src/native/mirrorsedge/masseffect_native_targets.cpp
    src/native/mirrorsedge/masseffect_native_shaders.cpp
    src/native/mirrorsedge/masseffect_native_textures_pool.cpp
    src/native/mirrorsedge/masseffect_shader_library.cpp
    src/native/mirrorsedge/me_masseffect_glue.cpp
)

if(CMAKE_SYSTEM_NAME STREQUAL "Generic" OR SWITCH)
    list(APPEND MIRRORSEDGE_SOURCES
        src/native/me_ring_wait.cpp
        src/native/me_resolution.cpp
        src/native/me_physx.cpp
        src/native/me_audio_hooks.cpp
        src/native/me_ini_override.cpp
    )
else()
    list(APPEND MIRRORSEDGE_SOURCES src/native/host_stubs.cpp)
endif()
if(WIN32)
    add_executable(mirrorsedge WIN32 ${MIRRORSEDGE_SOURCES})
else()
    add_executable(mirrorsedge ${MIRRORSEDGE_SOURCES})
endif()

rexglue_setup_target(mirrorsedge GPU_PLUGINS xenos)

target_include_directories(mirrorsedge PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/native
    ${CMAKE_CURRENT_SOURCE_DIR}/src/native/mirrorsedge
    ${CMAKE_CURRENT_SOURCE_DIR}/src/native/mirrorsedge/shaders
    ${CMAKE_CURRENT_SOURCE_DIR}/src/native/mirrorsedge/shaders/inc
    ${CMAKE_CURRENT_SOURCE_DIR}/generated/default
    ${REXSDK_DIR}/include
    ${REXSDK_DIR}/src/core
    ${REXSDK_DIR}/src/ui/shaders
    ${REXSDK_DIR}/thirdparty/imgui
    ${REXSDK_DIR}/thirdparty/xxHash
)
target_compile_definitions(mirrorsedge PRIVATE
    REX_PROJECT_NAME="mirrorsedge"
    REX_TITLE_ID=0x45410850
)

add_compile_options(-ffunction-sections -fdata-sections)
target_link_libraries(mirrorsedge PRIVATE xxhash rexgpu-xenos glslang SPIRV)
if(NOT WIN32)
    target_link_options(mirrorsedge PRIVATE -Wl,--gc-sections)
endif()

if(CMAKE_SYSTEM_NAME STREQUAL "Generic" OR SWITCH)
    # The SDK packager strips the ELF first. Passing the unstripped executable to
    # elf2nro embedded the whole symbol table in the NRO (69.5 MB vs ~40 MB).
    rexglue_switch_add_nro(mirrorsedge
        NAME "Mirrors Edge"
        AUTHOR "EA DICE / ReXGlue Port"
        VERSION "1.0.0"
        ICON "${CMAKE_CURRENT_SOURCE_DIR}/icon.jpg"
    )
endif()
