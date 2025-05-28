from flask import Flask, render_template, request, jsonify
import socket
import struct
import json
import time
from threading import Lock

app = Flask(__name__)
lock = Lock()

# Configuration
BACKEND_HOST = 'localhost'
BACKEND_PORT = 5001
BUFFER_SIZE = 4096

# Add this error mapping at the top
NRC_MESSAGES = {
    0x11: "Service not supported",
    0x12: "Sub-function not supported",
    0x13: "Incorrect message length",
    0x22: "Conditions not correct",
    0x31: "Request out of range",
    0x33: "Security access denied",
    0x72: "General programming failure"
}

def parse_uds_response(response_hex):
    """Convert raw hex response to human-readable format"""
    if not response_hex:
        return "No response from ECU"
    
    try:
        bytes_list = response_hex.upper().split()
        if not bytes_list:
            return "Empty response"

        # Negative response check (must come first!)
        if len(bytes_list) >= 3 and bytes_list[0] == '7F':
            service = int(bytes_list[1], 16)
            nrc = int(bytes_list[2], 16)
            reason = NRC_MESSAGES.get(nrc, f"Unknown error (NRC=0x{nrc:02X})")
            return f"❌ Error (Service 0x{service:02X}): {reason}"

        # Positive response
        first_byte = int(bytes_list[0], 16)
        if first_byte & 0x40:
            service = first_byte - 0x40
            # Handle different service responses
            if service == 0x23:  # ReadMemory
                data = ' '.join(bytes_list[1:]) if len(bytes_list) > 1 else 'No data'
            elif service == 0x3D:  # WriteMemory
                data = "Write successful"
            else:
                data = ' '.join(bytes_list[1:])
            return f"✅ Success (Service 0x{service:02X}): {data}"

        return f"Unknown Response: {response_hex}"
    except ValueError as e:
        return f"Invalid response format: {str(e)}"
    
# def parse_uds_response(response_hex):
#     """Convert raw hex response to human-readable format"""
#     if not response_hex:
#         return "No response from ECU"
    
#     try:
#         bytes_list = response_hex.split()
#         first_byte = int(bytes_list[0], 16)
        
#         # Positive response
#         if first_byte & 0x40:
#             service = first_byte - 0x40
#             data = ' '.join(bytes_list[1:]) if len(bytes_list) > 1 else 'No data'
#             return f"✅ Success (Service 0x{service:02X}): {data}"
        
#         # Negative response
#         if len(bytes_list) >= 3 and bytes_list[0] == '7F':
#             service = int(bytes_list[1], 16)
#             nrc = int(bytes_list[2], 16)
#             reason = NRC_MESSAGES.get(nrc, f"Unknown error (NRC=0x{nrc:02X})")
#             return f"❌ Error (Service 0x{service:02X}): {reason}"
        
#         return f"Unknown Response: {response_hex}"
#     except ValueError:
#         return f"Invalid response format: {response_hex}"

class UDSClient:
    def __init__(self):
        self.socket = None
        self.lock = Lock()
        self.timeout = 2.0
        self.max_retries = 3
        
    def _ensure_connection(self):
        for attempt in range(self.max_retries):
            try:
                if self.socket is None:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.settimeout(self.timeout)
                    self.socket.connect((BACKEND_HOST, BACKEND_PORT))
                return True
            except Exception as e:
                print(f"Connection attempt {attempt + 1} failed: {e}")
                self._close_socket()
                if attempt == self.max_retries - 1:
                    return False
                time.sleep(0.5)
    

    
    def send_request(self, service, data=None, address=None, length=None):
        request_bytes = bytearray()
        request_bytes.append(service)
        
        if address is not None:
            # Pack address as 3 bytes (big-endian)
            request_bytes.extend(struct.pack('>I', address)[1:])
            
        if length is not None:
            request_bytes.append(length)
            
        if data is not None:
            if isinstance(data, str):
                # Convert hex string to bytes
                data_bytes = bytes.fromhex(data.replace(' ', ''))
                request_bytes.extend(data_bytes)
            else:
                request_bytes.extend(data)
                
        with self.lock:
            try:
                if not self._ensure_connection():
                    return None
                    
                self.socket.sendall(request_bytes)
                response = self.socket.recv(BUFFER_SIZE)
                print(f"Received raw bytes: {response.hex(' ')}")  # Debug log
                return response.hex(' ')
            except Exception as e:
                print(f"Communication error: {e}")
                self._close_socket()
                return None
    
    def _close_socket(self):
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

uds_client = UDSClient()

@app.before_request
def log_request():
    if request.method == 'POST':
        print(f"\nRequest: {request.path} | Data: {request.json}")

@app.after_request
def log_response(response):
    if request.method == 'POST':
        data = response.get_json()
        print(f"Response: {data.get('message')} | Raw: {data.get('raw_response')}")
    return response

@app.route('/')
def index():
    return render_template('index.html')

# # Update the API endpoints to use parse_uds_response
# @app.route('/api/read_memory', methods=['POST'])
# def read_memory():
#     try:
#         data = request.json
#         address = int(data['address'], 16)
#         length = int(data['length'])
        
#         if not (0 <= address <= 0xFFFFF):
#             return jsonify({'error': 'Address out of range (0x00000-0xFFFFF)'}), 400
#         if not (1 <= length <= 255):
#             return jsonify({'error': 'Invalid length (1-255)'}), 400
            
#         response = uds_client.send_request(
#             service=0x23,
#             address=address,
#             length=length
#         )
#         return jsonify({
#             'response': response,
#             'message': parse_uds_response(response)
#         })
#     except ValueError:
#         return jsonify({'error': 'Invalid hex format'}), 400

@app.route('/api/read_memory', methods=['POST'])
def read_memory():
    try:
        data = request.json
        address = int(data['address'], 16)
        length = int(data['length'])
        
        if not (0 <= address <= 0xFFFFF):
            return jsonify({
                'success': False,
                'raw_response': '7F 23 31',
                'message': '❌ Error (Service 0x23): Address out of range'
            })
        
        if not (1 <= length <= 255):
            return jsonify({
                'success': False,
                'raw_response': '7F 23 31',
                'message': '❌ Error (Service 0x23): Invalid length (1-255)'
            })
            
        response = uds_client.send_request(service=0x23, address=address, length=length)
        
        return jsonify({
            'success': True,
            'raw_response': response,
            'message': parse_uds_response(response)
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'raw_response': '7F 23 13',
            'message': f'❌ Error (Service 0x23): {str(e)}'
        })
    
# @app.route('/api/write_memory', methods=['POST'])
# def write_memory():
#     data = request.json
#     address = int(data['address'], 16)
#     value = data['value']
    
#     response = uds_client.send_request(
#         service=0x3D,
#         address=address,
#         data=value
#     )
    
#     return jsonify({'response': response})

# @app.route('/api/write_memory', methods=['POST'])
# def write_memory():
#     data = request.json
#     try:
#         address = int(data['address'], 16)
#         value = data['value']
        
#         # Validate hex values
#         bytes.fromhex(value.replace(' ', ''))
        
#         if not (0 <= address <= 0xFFFFF):
#             return jsonify({'error': 'Address out of range (0x00000-0xFFFFF)'}), 400
            
#         response = uds_client.send_request(
#             service=0x3D,
#             address=address,
#             data=value
#         )
#         return jsonify({
#             'raw_response': response,
#             'message': parse_uds_response(response)
#         })
#     except ValueError:
#         return jsonify({'error': 'Invalid hex format'}), 400
    
@app.route('/api/write_memory', methods=['POST'])
def write_memory():
    try:
        data = request.json
        address = int(data['address'], 16)
        value = data['value']
        
        # Validate hex
        bytes.fromhex(value.replace(' ', ''))

        if not (0 <= address <= 0xFFFFF):
            return jsonify({
                'success': False,
                'raw_response': '7F 3D 31',
                'message': '❌ Error (Service 0x23): Address out of range'
            })
        
        response = uds_client.send_request(service=0x3D, address=address, data=value)
        
        return jsonify({
            'success': True,
            'raw_response': response or '7D',  # Default write confirmation
            'message': parse_uds_response(response or '7D')
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'raw_response': '7F 3D 13',
            'message': f'❌ Error (Service 0x3D): {str(e)}'
        })

# @app.route('/api/read_data_id', methods=['POST'])
# def read_data_id():
#     data = request.json
#     data_id = int(data['data_id'], 16)
    
#     # Pack data ID as 2 bytes
#     data_bytes = struct.pack('>H', data_id)
    
#     response = uds_client.send_request(
#         service=0x22,
#         data=data_bytes
#     )
    
#     return jsonify({'response': response})

@app.route('/api/read_data_id', methods=['POST'])
def read_data_id():
    try:
        data = request.json
        print(f"DEBUG - Received request for DID: {data['data_id']}")  # Log input
        
        data_id = int(data['data_id'], 16)
        data_bytes = struct.pack('>H', data_id)
        
        response = uds_client.send_request(service=0x22, data=data_bytes)
        print(f"DEBUG - Backend response: {response}")  # Log raw response
        
        if not response:
            raise ValueError("No response from backend")
            
        return jsonify({
            'raw_response': response,  # Ensure this matches frontend expectation
            'message': parse_uds_response(response)
        })
    except Exception as e:
        print(f"ERROR - {str(e)}")
        return jsonify({
            'raw_response': '7F 22 13',
            'message': f'❌ Error (Service 0x22): {str(e)}'
        })
    
@app.route('/api/ecu_reset', methods=['POST'])
def ecu_reset():
    response = uds_client.send_request(service=0x11)
    # return jsonify({'response': response})
    return jsonify({
            'response': response,
            'message': parse_uds_response(response)
        })

@app.teardown_appcontext
def teardown(exception):
    uds_client._close_socket()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)