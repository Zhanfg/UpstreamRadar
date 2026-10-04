cmake_minimum_required(VERSION 3.20)
project(upstreamradar_change_score LANGUAGES CXX)
add_executable(upstreamradar-change-score src/main.cpp)
target_compile_features(upstreamradar-change-score PRIVATE cxx_std_20)
