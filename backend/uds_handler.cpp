#include "uds_handler.h"
#include <algorithm>
#include <cstring>
#include<iostream>

UDSHandler::UDSHandler() {
    initializeECUMemory();
}

void UDSHandler::initializeECUMemory() {
    // Initialize with 64KB of simulated memory
    // ecu_memory_.resize(64 * 1024, 0x00);

    ecu_memory_.resize(1024 * 1024, 0x00);
    // ecu_memory_.resize(0x10000, 0x00);  
    
    // Set some example values
    ecu_memory_[0x1000] = 0xAA;
    ecu_memory_[0x1001] = 0xBB;
    ecu_memory_[0x1002] = 0xCC;
    
    // Example configuration data
    ecu_memory_[0x2000] = 0x01; // Config byte 1
    ecu_memory_[0x2001] = 0x02; // Config byte 2

    // Add some test patterns at high addresses
ecu_memory_[0x10000] = 0xAA;
ecu_memory_[0xFFFFF] = 0xBB;
}

std::vector<uint8_t> UDSHandler::processRequest(const std::vector<uint8_t>& request) {
    if (request.empty()) {
        return {0x7F, 0x00}; // Negative response - general reject
    }
    
    uint8_t service_id = request[0];
    
    switch (service_id) {
        case SERVICE_READ_MEMORY:
            return handleReadMemory(request);
        case SERVICE_WRITE_MEMORY:
            return handleWriteMemory(request);
        case SERVICE_ECU_RESET:
            return handleECUReset(request);
        case SERVICE_READ_DATA_ID:
            return handleReadDataByIdentifier(request);
        default:
            return {0x7F, service_id, 0x11}; // Service not supported
    }
}

std::vector<uint8_t> UDSHandler::handleReadMemory(const std::vector<uint8_t>& request) {

     
    // Format: [0x23, addr_high, addr_mid, addr_low, length]
    if (request.size() < 5) {
        return {0x7F, SERVICE_READ_MEMORY, 0x13}; // Incorrect message length
    }
    
    uint32_t address = (request[1] << 16) | (request[2] << 8) | request[3];
    uint8_t length = request[4];
    // Debug print to verify address
    // std::cout << "DEBUG - Requested address: 0x" << std::hex << address << std::endl;
    
    if (address >= ecu_memory_.size()) {  // Check against actual memory size
        std::cerr << "ERROR - Address 0x" << std::hex << address 
                  << " exceeds memory size 0x" << ecu_memory_.size() << std::endl;
        return {0x7F, SERVICE_READ_MEMORY, 0x31};
    }
    
    std::vector<uint8_t> response = {SERVICE_READ_MEMORY + 0x40}; // Positive response
    response.insert(response.end(), ecu_memory_.begin() + address, 
                   ecu_memory_.begin() + address + length);
    
    return response;
}

std::vector<uint8_t> UDSHandler::handleWriteMemory(const std::vector<uint8_t>& request) {
    // Format: [0x3D, addr_high, addr_mid, addr_low, data...]
    if (request.size() < 5) {
        return {0x7F, SERVICE_WRITE_MEMORY, 0x13}; // Incorrect message length
    }
    
    uint32_t address = (request[1] << 16) | (request[2] << 8) | request[3];
    size_t data_length = request.size() - 4;
    
    if (address + data_length > ecu_memory_.size()) {
        return {0x7F, SERVICE_WRITE_MEMORY, 0x31}; // Request out of range
    }
    
    std::copy(request.begin() + 4, request.end(), ecu_memory_.begin() + address);
    
    return {SERVICE_WRITE_MEMORY + 0x40}; // Positive response
}

std::vector<uint8_t> UDSHandler::handleECUReset(const std::vector<uint8_t>& request) {

    // std::cout << "\n=== ECU Reset Triggered ===" << std::endl;
    // std::cout << "Request Data: ";
    // for (auto b : request) printf("%02X ", b);
    // std::cout << "\nResetting ECU memory..." << std::endl;

    // Simple reset simulation - just reinitialize memory
    initializeECUMemory();
    return {SERVICE_ECU_RESET + 0x40}; // Positive response
}

std::vector<uint8_t> UDSHandler::handleReadDataByIdentifier(const std::vector<uint8_t>& request) {
    // Format: [0x22, data_id_high, data_id_low]
    if (request.size() < 3) {
        return {0x7F, SERVICE_READ_DATA_ID, 0x13}; // Incorrect message length
    }

    uint16_t data_id = (request[1] << 8) | request[2];
    
    // Debug print to verify DID
    // std::cout << "DEBUG - Requested DID: 0x" << std::hex << data_id << std::endl;

    switch (data_id) {
        case 0xF100: // ECU Serial Number
            return {SERVICE_READ_DATA_ID + 0x40, 0xF1, 0x00, 
                    'E', 'C', 'U', '1', '2', '3', '4', '5'}; // ASCII "ECU12345"
            
        case 0xF200: // Software Version
            return {SERVICE_READ_DATA_ID + 0x40, 0xF2, 0x00, 
                    '1', '.', '0', '.', '0'}; // ASCII "1.0.0"
            
        default:
            return {0x7F, SERVICE_READ_DATA_ID, 0x31}; // Request out of range
    }
}