cmake_minimum_required(VERSION 3.20)
project(adb_drag_source LANGUAGES CXX)

add_library(adb_drag_source SHARED adb_drag_source.cpp)
target_compile_features(adb_drag_source PRIVATE cxx_std_17)
target_compile_definitions(adb_drag_source PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_link_libraries(adb_drag_source PRIVATE ole32 shell32 shlwapi uuid)
set_target_properties(adb_drag_source PROPERTIES OUTPUT_NAME adb_drag_source)
set_target_properties(adb_drag_source PROPERTIES
    PREFIX ""
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/Release"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/Release"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/Release"
    LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/Release"
)

if(MINGW)
    target_link_options(adb_drag_source PRIVATE -static -static-libgcc -static-libstdc++)
endif()

option(ADB_DRAG_BUILD_STREAM_PROBE "Build the real-device ADB stream probe" OFF)
if(ADB_DRAG_BUILD_STREAM_PROBE)
    add_executable(adb_drag_stream_probe tests/stream_probe.cpp)
    target_compile_features(adb_drag_stream_probe PRIVATE cxx_std_17)
    target_compile_definitions(adb_drag_stream_probe PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
    target_link_libraries(adb_drag_stream_probe PRIVATE ole32 shell32 shlwapi)
    set_target_properties(adb_drag_stream_probe PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/Release"
        RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/Release"
    )
    if(MINGW)
        target_link_options(adb_drag_stream_probe PRIVATE -static -static-libgcc -static-libstdc++)
    endif()
endif()

option(ADB_DRAG_BUILD_ASYNC_PROBE "Build the IDataObject async-operation probe" OFF)
if(ADB_DRAG_BUILD_ASYNC_PROBE)
    add_executable(adb_drag_async_probe tests/async_probe.cpp)
    target_compile_features(adb_drag_async_probe PRIVATE cxx_std_17)
    target_compile_definitions(adb_drag_async_probe PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
    target_link_libraries(adb_drag_async_probe PRIVATE ole32 shell32 shlwapi uuid)
    set_target_properties(adb_drag_async_probe PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/Release"
        RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/Release"
    )
    if(MINGW)
        target_link_options(adb_drag_async_probe PRIVATE -static -static-libgcc -static-libstdc++)
    endif()
endif()
