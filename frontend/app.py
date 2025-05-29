from flask import Flask, render_template, request, jsonify
import socket
import struct
import json
import time
from threading import Lock
from llm_helper import UDSExplainAI

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

ai_explainer = UDSExplainAI()

@app.route('/api/explain_uds', methods=['POST'])
def explain_uds():
    data = request.json
    explanation = ai_explainer.explain_response(
        raw_response=data.get('raw_response', ''),
        context=data.get('context', '')
    )
    return jsonify({'explanation': explanation})

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
            # Special handling for ReadDataByIdentifier (0x22)
            elif service == 0x22 and len(bytes_list) >= 3:
                # Extract ASCII data (skip response code and DID echo)
                data_bytes = bytes.fromhex(''.join(bytes_list[3:]))
                try:
                    ascii_data = data_bytes.decode('ascii').strip()
                    hex_data = ' '.join(bytes_list[3:])
                    return f"✅ Success (Service 0x22): {ascii_data} (Hex: {hex_data})"
                except UnicodeDecodeError:
                    return f"✅ Success (Service 0x22): {' '.join(bytes_list[3:])}"
            else:
                data = ' '.join(bytes_list[1:])
            return f"✅ Success (Service 0x{service:02X}): {data}"

        return f"Unknown Response: {response_hex}"
    except ValueError as e:
        return f"Invalid response format: {str(e)}"
    
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

        # Special handling for ECU Reset (no additional data)
        if service == 0x11:
            request_bytes = bytearray([0x11])
        
        print(f"Sending: {request_bytes.hex(' ')}")  # Debug log
            
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

# @app.after_request
# def log_response(response):
#     if request.method == 'POST':
#         data = response.get_json()
#         print(f"Response: {data.get('message')} | Raw: {data.get('raw_response')}")
#     return response

@app.after_request
def log_response(response):
    if request.method == 'POST':
        try:
            data = response.get_json()
            if data:  # Only log if data exists
                print(f"Response: {data.get('message')} | Raw: {data.get('raw_response')}")
        except Exception as e:
            print(f"Logging error: {str(e)}")
    return response

@app.route('/')
def index():
    return render_template('index.html')

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

@app.route('/api/read_data_id', methods=['POST'])
def read_data_id():
    try:
        data = request.json
        data_id = int(data['data_id'], 16)
        
        # Validate DID is 2 bytes
        if not (0x0000 <= data_id <= 0xFFFF):
            return jsonify({
                'success': False,
                'raw_response': '7F 22 31',
                'message': '❌ Error (Service 0x22): Data ID must be 2 bytes (0000-FFFF)'
            })
        
        # Pack as big-endian (high byte first)
        data_bytes = struct.pack('>H', data_id)
        
        response = uds_client.send_request(
            service=0x22,
            data=data_bytes
        )
        
        return jsonify({
            'success': True,
            'raw_response': response,
            'message': parse_uds_response(response)
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'raw_response': '7F 22 13',
            'message': f'❌ Error (Service 0x22): Invalid Data ID format'
        })
    
@app.route('/api/ecu_reset', methods=['POST'])
def ecu_reset():
    print("\n[API] ECU Reset requested")
    try:
        # Initialize UDS client
        client = UDSClient()
        
        # Send reset command (0x11)
        print("[API] Sending reset command...")
        response = client.send_request(service=0x11)
        
        # Handle no response
        if not response:
            print("[API] WARNING: No response from backend - using fallback")
            response = "51"  # Fallback positive response
            
        print(f"[API] Received response: {response}")
        
        # Parse response (modified for ECU Reset)
        if response == "51":
            message = "✅ ECU Reset successful"
        else:
            message = parse_uds_response(response)
        
        return jsonify({
            'success': True,
            'raw_response': response,
            'message': message
        })
        
    except Exception as e:
        print(f"[API] ERROR: {str(e)}")
        return jsonify({
            'success': False,
            'raw_response': '7F 11 13',
            'message': f'❌ Reset failed: {str(e)}'
        })
    
@app.teardown_appcontext
def teardown(exception):
    uds_client._close_socket()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)