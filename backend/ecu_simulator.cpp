#include "uds_handler.h"
#include <iostream>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <cstring>

const int PORT = 5001;
const int BUFFER_SIZE = 4096;

void runServer() {
    int server_fd, new_socket;
    struct sockaddr_in address;
    int opt = 1;
    int addrlen = sizeof(address);
    
    // Create socket file descriptor
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == 0) {
        perror("socket failed");
        exit(EXIT_FAILURE);
    }
    
    // Set socket options
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, &opt, sizeof(opt))) {
        perror("setsockopt");
        exit(EXIT_FAILURE);
    }
    
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);
    
    // Bind socket to port
    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        perror("bind failed");
        exit(EXIT_FAILURE);
    }
    
    // Start listening
    if (listen(server_fd, 3) < 0) {
        perror("listen");
        exit(EXIT_FAILURE);
    }
    
    std::cout << "UDS Server listening on port " << PORT << std::endl;
    
    UDSHandler handler;
    
    while (true) {
        // Accept new connection
        if ((new_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t*)&addrlen)) < 0) {
            perror("accept");
            continue;
        }
        
        // Read request
        std::vector<uint8_t> buffer(BUFFER_SIZE);
        int bytes_read = read(new_socket, buffer.data(), BUFFER_SIZE);
        
        if (bytes_read > 0) {
            buffer.resize(bytes_read);
            
            // Process UDS request
            std::vector<uint8_t> response = handler.processRequest(buffer);
            
            // Send response
            send(new_socket, response.data(), response.size(), 0);
        }
        
        close(new_socket);
    }
}

int main() {
    runServer();
    return 0;
}