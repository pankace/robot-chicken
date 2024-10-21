import socket

# Set up the TCP server
TCP_IP = "0.0.0.0"  # Listen on all network interfaces
TCP_PORT = 5005     # Port to listen on
BUFFER_SIZE = 1024  # Buffer size for receiving data

# Create the socket (TCP)
server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.bind((TCP_IP, TCP_PORT))
server_sock.listen(1)  # Listen for 1 connection at a time

print(f"Listening for TCP connections on port {TCP_PORT}...")

try:
    while True:
        # Accept a new connection
        conn, addr = server_sock.accept()
        print(f"Connection from {addr} established")

        try:
            # Receive data from the client
            while True:
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    break  # Connection closed by client

                try:
                    # Attempt to decode and convert the received data to an integer
                    received_value = int(data.decode('utf-8').strip())
                    print(f"Received integer: {received_value} from {addr}")
                except ValueError:
                    print(f"Received non-integer data: {data.decode('utf-8')} from {addr}")
        finally:
            # Close the connection when done
            conn.close()
            print(f"Connection from {addr} closed")

except KeyboardInterrupt:
    print("\nTCP listener stopped.")
finally:
    server_sock.close()
