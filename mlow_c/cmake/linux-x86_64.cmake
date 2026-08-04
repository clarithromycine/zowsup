# Cross-compilation toolchain for Linux x86_64 using zig cc
# Prerequisite: brew install zig
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

set(CMAKE_C_COMPILER "zig")
set(CMAKE_C_COMPILER_ARG1 "cc")
set(CMAKE_C_COMPILER_TARGET x86_64-linux-gnu)

set(CMAKE_CXX_COMPILER "zig")
set(CMAKE_CXX_COMPILER_ARG1 "c++")
set(CMAKE_CXX_COMPILER_TARGET x86_64-linux-gnu)

set(CMAKE_AR "zig;ar")
set(CMAKE_RANLIB "zig;ranlib")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
