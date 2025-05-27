#!/bin/bash

# Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip cmake g++

# Install Python requirements
pip3 install flask

# Build C++ backend
mkdir -p backend/build
cd backend/build
cmake ..
make
cd ../..

echo "Setup complete!"
echo "To start the backend server: ./backend/build/uds_server"
echo "To start the frontend: python3 frontend/app.py"