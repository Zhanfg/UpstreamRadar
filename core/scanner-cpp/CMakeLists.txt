cmake_minimum_required(VERSION 3.20)
project(upstreamradar_change_score LANGUAGES CXX)

add_executable(
  upstreamradar-change-score
  src/main.cpp
)
target_compile_features(
  upstreamradar-change-score
  PRIVATE cxx_std_20
)

add_executable(
  upstreamradar-museum-selftest
  src/museum/selftest.cpp
)
target_compile_features(
  upstreamradar-museum-selftest
  PRIVATE cxx_std_20
)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(
    upstreamradar-change-score
    PRIVATE -Wall -Wextra -Wpedantic
  )
  target_compile_options(
    upstreamradar-museum-selftest
    PRIVATE -Wall -Wextra -Wpedantic
  )
endif()
