from __future__ import print_function

import pyzbar.pyzbar as pyzbar
from cv2 import cv2


class WebcamReader:
    def __init__(self, font: int = cv2.FONT_HERSHEY_SIMPLEX, width: int = 640, height: int = 480):
        self._font = font
        self._capture_webcam = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        self._capture_webcam.set(3, width)
        self._capture_webcam.set(4, height)

    def capture(self) -> bytes:
        while self._capture_webcam.isOpened() is True:
            # Capture frame-by-frame
            _, frame = self._capture_webcam.read()
            frame_image = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Decode the QR code
            decoded_objects = pyzbar.decode(frame_image)
            if len(decoded_objects) == 0:
                continue
            elif len(decoded_objects) > 1:
                # TODO: What to do when there is more than 1 QR CODE
                continue

            decoded_object = decoded_objects[0]

            return decoded_object.data

    def release(self):
        self._capture_webcam.release()