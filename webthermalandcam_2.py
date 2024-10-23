#!/usr/bin/python3

import io
import logging
import socketserver
from http import server
from threading import Condition, Thread, Event
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
import matplotlib.pyplot as plt
from scipy import interpolate
import numpy as np
import time, sys
sys.path.append('../')
import amg8833_i2c

PAGE = """\
<html>
<head>
<title>Pi Camera and AMG8833 Thermal Camera</title>
</head>
<body>
<h1>Pi Camera and AMG8833 Thermal Camera</h1>
<img src="stream.mjpg" width="640" height="480" />
<h2>Thermal Camera Output</h2>
<img src="thermal_stream.mjpg" width="640" height="480" />
</body>
</html>
"""

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.stream_video(output)
        elif self.path == '/thermal_stream.mjpg':
            self.stream_video(thermal_output)
        else:
            self.send_error(404)
            self.end_headers()

    def stream_video(self, stream_output):
        self.send_response(200)
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.end_headers()
        try:
            while True:
                with stream_output.condition:
                    stream_output.condition.wait()
                    frame = stream_output.frame
                self.wfile.write(b'--FRAME\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
        except Exception as e:
            logging.warning('Removed streaming client %s: %s', self.client_address, str(e))

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

# Function to stream thermal camera plot as MJPEG
def thermal_camera_stream(output, stop_event, frame_rate=10):
    sensor = amg8833_i2c.AMG8833(addr=0x69)
    pix_res = (8, 8)
    xx, yy = np.linspace(0, pix_res[0], pix_res[0]), np.linspace(0, pix_res[1], pix_res[1])
    pix_mult = 6
    interp_res = (pix_mult * pix_res[0], pix_mult * pix_res[1])
    grid_x, grid_y = np.linspace(0, pix_res[0], interp_res[0]), np.linspace(0, pix_res[1], interp_res[1])

    def interp(z_var):
        f = interpolate.interp2d(xx, yy, z_var, kind='cubic')
        return f(grid_x, grid_y)

    plt.rcParams.update({'font.size': 16})
    fig, ax = plt.subplots(figsize=(10, 9))
    im1 = ax.imshow(np.zeros(interp_res), vmin=18, vmax=37, cmap=plt.cm.plasma)
    cbar = fig.colorbar(im1, fraction=0.0475, pad=0.03)
    cbar.set_label('Temperature [C]', labelpad=10)

    buf = io.BytesIO()
    interval = 1.0 / frame_rate  # Time between frames

    while not stop_event.is_set():
        start_time = time.time()
        status, pixels = sensor.read_temp(64)
        if not status:
            new_z = interp(np.reshape(pixels, pix_res))
            im1.set_data(new_z)
            fig.canvas.draw()
            
            # Save the plot to the in-memory buffer
            buf.seek(0)
            fig.savefig(buf, format='jpeg')
            buf.truncate()  # Remove extra space from previous images

            # Write the frame to the thermal output stream
            output.write(buf.read())

        # Sleep to maintain the frame rate
        elapsed_time = time.time() - start_time
        time.sleep(max(0, interval - elapsed_time))

# Start the Pi camera stream
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
output = StreamingOutput()
picam2.start_recording(JpegEncoder(), FileOutput(output))

# Create the output object for thermal stream
thermal_output = StreamingOutput()

# Use threading event for stopping thermal thread safely
stop_event = Event()

# Start the thermal camera stream in a separate thread
thermal_thread = Thread(target=thermal_camera_stream, args=(thermal_output, stop_event, 10))
thermal_thread.start()

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    stop_event.set()  # Signal the thermal thread to stop
    thermal_thread.join()  # Wait for the thermal thread to exit
    picam2.stop_recording() # fix : wait for thred to exit 

