import asyncio
from io import BytesIO

import numpy
import qrcode as qrcode
from cv2 import cv2 as cv
from numpy import ndarray
from qrcode import QRCode
# from pyqrcodeng import QRCode


MAX_DATA_SIZE = 2.5 * 1024  # 2KB


class QRCodeCreator:
    def __init__(
        self,
        error_correction_level: int = qrcode.constants.ERROR_CORRECT_H,
        box_size: int = 5,
        border: int = 4,
        fill_color: str = "black",
        back_color: str = "white",
        color_profile: str = "RGB",
        image_type: str = "png",
    ):
        self._error_correction_level = error_correction_level
        self._box_size = box_size
        self._border = border
        self._fill_color = fill_color
        self._back_color = back_color
        self._color_profile = color_profile
        self._image_type = image_type

    @staticmethod
    def _validate_size(data: bytes) -> None:
        if len(data) > MAX_DATA_SIZE:
            raise ValueError("Data is too big")

    @staticmethod
    def _create_opencv_image(image_stream: BytesIO, cv2_image_flag: int = 0) -> ndarray:
        image_stream.seek(0)

        img_array = numpy.asarray(bytearray(image_stream.read()), dtype=numpy.uint8)
        return cv.imdecode(img_array, cv2_image_flag)

    def create(self, data: bytes) -> ndarray:
        self._validate_size(data)

        image_stream = BytesIO()

        qr_code = QRCode(
            version=1, error_correction=self._error_correction_level, box_size=self._box_size, border=self._border
        )

        qr_code.add_data(data)

        temp_image = qr_code.make_image(fill_color=self._fill_color, back_color=self._back_color).convert(
            self._color_profile
        )
        temp_image.save(image_stream, self._image_type)

        qr_code_image = self._create_opencv_image(image_stream)

        return qr_code_image
