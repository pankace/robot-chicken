import socket

# Set up the UDP server
UDP_IP = " 127.0.0.1"  # Listen on all interfaces
UDP_PORT = 5005     # Port to listen on

# Create the socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"Listening for UDP packets on port {UDP_PORT}...")

try:
    while True:
        data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
        print(f"Received message: {data.decode('utf-8')} from {addr}")
except KeyboardInterrupt:
    print("\nUDP listener stopped.")
finally:
    sock.close()
