cmake_minimum_required(VERSION 3.20)

project(Quake4CNOfficialCompat LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "official-compat targets Windows only")
endif()

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "official-compat must be built for x86")
endif()

add_executable(Q4CNLoader
    loader/main.cpp
)
target_compile_features(Q4CNLoader PRIVATE cxx_std_17)
target_compile_definitions(Q4CNLoader PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_include_directories(Q4CNLoader PRIVATE common)
target_link_libraries(Q4CNLoader PRIVATE bcrypt)

add_library(Q4CNCompat32 SHARED
    compat/dllmain.cpp
    compat/runtime_hooks.cpp
)
target_compile_features(Q4CNCompat32 PRIVATE cxx_std_17)
target_compile_definitions(Q4CNCompat32 PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_include_directories(Q4CNCompat32 PRIVATE common)

if(MSVC)
    foreach(target Q4CNLoader Q4CNCompat32)
        target_compile_options(${target} PRIVATE /W4 /WX /permissive- /utf-8)
        target_link_options(${target} PRIVATE /INCREMENTAL:NO)
    endforeach()
endif()
