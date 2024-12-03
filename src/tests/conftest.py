from typing import Optional
from unittest.mock import MagicMock

import pytest
from cv2 import cv2

from main import QRCodeCommunication
from protocol import RequestHeader, HEADER_LENGTH
from qr_creator import QRCodeCreator
from webcam import WebcamReader


@pytest.fixture
def webcam_reader_mock():
    capture_webcam = MagicMock()
    reader = WebcamReader(capture_webcam=capture_webcam)

    return reader


class QRCodeCreatorMock(QRCodeCreator):
    def __init__(self):
        super().__init__()

        self.responses = []

    def create(self, *args, **kwargs):
        super_result = super().create(*args, **kwargs)

        self.responses.append(super_result)

        return super_result


@pytest.fixture
def qr_creator():
    creator = QRCodeCreator()

    return creator


@pytest.fixture
def qr_code_communation_mock(webcam_reader_mock):
    qrcode = QRCodeCommunication("received-files")
    qrcode._qr_code_creator = QRCodeCreatorMock()
    qrcode.show_image = MagicMock(return_value=None)
    return qrcode


def parse_image(webcam_reader_mock, image, mode=cv2.COLOR_BGR2GRAY) -> tuple[Optional[RequestHeader], Optional[bytes]]:
    webcam_reader_mock._capture_webcam.read.return_value = ("", image)

    raw_data = webcam_reader_mock.capture(mode=mode)

    if raw_data is None:
        return None, None

    header = RequestHeader.parse(raw_data[:HEADER_LENGTH])
    raw_payload = raw_data[HEADER_LENGTH:]

    return header, raw_payload
