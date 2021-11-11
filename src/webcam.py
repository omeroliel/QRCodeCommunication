from __future__ import print_function

from typing import Optional

import pyzbar.pyzbar as pyzbar
from cv2 import cv2


class WebcamReader:
    def __init__(self, font: int = cv2.FONT_HERSHEY_SIMPLEX, width: int = 640, height: int = 480):
        self._font = font
        self._capture_webcam = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        self._capture_webcam.set(3, width)
        self._capture_webcam.set(4, height)

    def __enter__(self):
        return self

    def is_capturing(self) -> bool:
        return self._capture_webcam.isOpened()

    def capture(self) -> Optional[bytes]:
        _, frame = self._capture_webcam.read()
        frame_image = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Decode the QR code
        decoded_objects = pyzbar.decode(frame_image)
        if len(decoded_objects) == 0:
            return
        elif len(decoded_objects) > 1:
            # TODO: What to do when there is more than 1 QR CODE
            return

        decoded_object = decoded_objects[0]

        try:
            data_to_bytes = bytes.fromhex(decoded_object.data.decode())
        except ValueError:
            print("Bad data received")

            return

        return data_to_bytes

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Releasing the webcam resources")
        self._capture_webcam.release()
