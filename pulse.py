from picamera2 import Picamera2
from lib.processors_noopenmdao import findFaceGetPulse
from lib.interface import plotXY, imshow, waitKey, destroyWindow
from cv2 import moveWindow
import argparse
import numpy as np
import datetime
import socket
import sys

class getPulseApp(object):
    """
    Python application that finds a face in a webcam stream, then isolates the
    forehead.
    Then the average green-light intensity in the forehead region is gathered
    over time, and the detected person's pulse is estimated.
    """
    def __init__(self, args):
        serial = args.serial
        baud = args.baud
        self.send_serial = False
        self.send_udp = False
        if serial:
            self.send_serial = True
            if not baud:
                baud = 9600
            else:
                baud = int(baud)
            self.serial = Serial(port=serial, baudrate=baud)

        udp = args.udp
        if udp:
            self.send_udp = True
            if ":" not in udp:
                ip = udp
                port = 5005
            else:
                ip, port = udp.split(":")
                port = int(port)
            self.udp = (ip, port)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Initialize the PiCamera2 object for the Raspberry Pi camera
        self.camera = Picamera2()
        self.camera.configure(self.camera.create_preview_configuration(main={"size": (640, 480)}))
        self.camera.start()

        self.w, self.h = 640, 480
        self.pressed = 0
        self.processor = findFaceGetPulse(bpm_limits=[50, 160],
                                          data_spike_limit=2500.,
                                          face_detector_smoothness=10.)

        self.bpm_plot = False
        self.plot_title = "Data display - raw signal (top) and PSD (bottom)"
        self.key_controls = {"s": self.toggle_search,
                             "d": self.toggle_display_plot,
                             "c": self.toggle_cam,
                             "f": self.write_csv}

    def toggle_cam(self):
        pass  # No need for camera toggling with a single Pi Camera

    def write_csv(self):
        fn = "Webcam-pulse" + str(datetime.datetime.now())
        fn = fn.replace(":", "_").replace(".", "_")
        data = np.vstack((self.processor.times, self.processor.samples)).T
        np.savetxt(fn + ".csv", data, delimiter=',')
        print("Writing csv")

    def toggle_search(self):
        state = self.processor.find_faces_toggle()
        print("face detection lock =", not state)

    def toggle_display_plot(self):
        if self.bpm_plot:
            print("bpm plot disabled")
            self.bpm_plot = False
            destroyWindow(self.plot_title)
        else:
            print("bpm plot enabled")
            if self.processor.find_faces:
                self.toggle_search()
            self.bpm_plot = True
            self.make_bpm_plot()
            moveWindow(self.plot_title, self.w, 0)

    def make_bpm_plot(self):
        plotXY([[self.processor.times,
                 self.processor.samples],
                [self.processor.freqs,
                 self.processor.fft]],
               labels=[False, True],
               showmax=[False, "bpm"],
               label_ndigits=[0, 0],
               showmax_digits=[0, 1],
               skip=[3, 3],
               name=self.plot_title,
               bg=self.processor.slices[0])

    def key_handler(self):
        self.pressed = waitKey(10) & 255
        if self.pressed == 27:  # exit program on 'esc'
            print("Exiting")
            if self.send_serial:
                self.serial.close()
            self.camera.close()  # Close the PiCamera properly
            sys.exit()

        for key in self.key_controls.keys():
            if chr(self.pressed) == key:
                self.key_controls[key]()



    def main_loop(self):
        """
        Single iteration of the application's main loop.
        """
        # Get current image frame from the camera
        frame = self.camera.capture_array()

        # Ensure the frame has 3 channels (RGB), not 4 (RGBA)
        if frame.shape[2] == 4:  # If the frame is RGBA
            frame = frame[:, :, :3]  # Strip the alpha channel, keeping only RGB

        self.h, self.w, _c = frame.shape

        # Set current image frame to the processor's input
        self.processor.frame_in = frame
        # Process the image frame to perform all needed analysis
        self.processor.run(0)
        # Collect the output frame for display
        output_frame = self.processor.frame_out

        # Ensure the output frame also has 3 channels (RGB)
        if output_frame.shape[2] == 4:
            output_frame = output_frame[:, :, :3]  # Strip the alpha channel

        # Show the processed/annotated output frame
        imshow("Processed", output_frame)

        # Create and/or update the raw data display if needed
        if self.bpm_plot:
            self.make_bpm_plot()

        # Handle serial and UDP transmission (if applicable)
        if self.send_serial:
            self.serial.write(str(self.processor.bpm) + "\r\n")

        if self.send_udp:
            self.sock.sendto(str(self.processor.bpm), self.udp)

        # Handle any key presses
        self.key_handler()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Raspberry Pi Camera pulse detector.')
    parser.add_argument('--serial', default=None, help='serial port destination for bpm data')
    parser.add_argument('--baud', default=None, help='Baud rate for serial transmission')
    parser.add_argument('--udp', default=None, help='udp address:port destination for bpm data')

    args = parser.parse_args()
    App = getPulseApp(args)
    while True:
        App.main_loop()
s