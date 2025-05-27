#ifndef UDS_HANDLER_H
#define UDS_HANDLER_H

#include <vector>
#include <cstdint>
#include <string>

class UDSHandler {
public:
    UDSHandler();
    
    // Process UDS request and generate response
    std::vector<uint8_t> processRequest(const std::vector<uint8_t>& request);
    
    // Supported UDS services
    static const uint8_t SERVICE_READ_MEMORY = 0x23;
    static const uint8_t SERVICE_WRITE_MEMORY = 0x3D;
    static const uint8_t SERVICE_ECU_RESET = 0x11;
    static const uint8_t SERVICE_READ_DATA_ID = 0x22;
    
private:
    // ECU memory simulation
    std::vector<uint8_t> ecu_memory_;
    
    // Helper methods
    std::vector<uint8_t> handleReadMemory(const std::vector<uint8_t>& request);
    std::vector<uint8_t> handleWriteMemory(const std::vector<uint8_t>& request);
    std::vector<uint8_t> handleECUReset(const std::vector<uint8_t>& request);
    std::vector<uint8_t> handleReadDataByIdentifier(const std::vector<uint8_t>& request);
    
    void initializeECUMemory();
};

#endif // UDS_HANDLER_H