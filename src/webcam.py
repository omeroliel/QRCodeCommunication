from __future__ import print_function

import base64
from typing import Optional

import pyzbar.pyzbar as pyzbar
from cv2 import cv2


class WebcamReader:
    def __init__(
        self, font: int = cv2.FONT_HERSHEY_SIMPLEX, width: int = 640, height: int = 480, capture_webcam: Optional = None
    ):
        self._font = font
        self._capture_webcam = capture_webcam or cv2.VideoCapture(0, cv2.CAP_DSHOW)

        self._capture_webcam.set(3, width)
        self._capture_webcam.set(4, height)

    def __enter__(self):
        return self

    def is_capturing(self) -> bool:
        return self._capture_webcam.isOpened()

    def capture(self, mode=cv2.COLOR_BGR2GRAY) -> Optional[bytes]:
        _, frame = self._capture_webcam.read()

        return self.parse_from_image(frame, mode)

    @staticmethod
    def parse_from_image(frame, mode) -> Optional[bytes]:
        frame_image = cv2.cvtColor(frame, mode)

        # Decode the QR code
        decoded_objects = pyzbar.decode(frame_image)
        if len(decoded_objects) == 0:
            return
        elif len(decoded_objects) > 1:
            # Too many QR codes. Ignore them.
            return

        decoded_object = decoded_objects[0]

        try:
            data_to_bytes = base64.b64decode(decoded_object.data)
        except ValueError:
            print("Bad data received")

            return

        return data_to_bytes

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Releasing the webcam resources")
        self._capture_webcam.release()
