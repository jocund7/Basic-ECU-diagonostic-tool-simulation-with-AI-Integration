cmake_minimum_required(VERSION 3.10)
project(UDSServer)

set(CMAKE_CXX_STANDARD 17)

add_executable(uds_server
    ecu_simulator.cpp
    uds_handler.cpp
)

target_include_directories(uds_server PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})