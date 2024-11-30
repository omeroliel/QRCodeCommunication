import callee as callee
import cv2
import pytest as pytest

from protocol import RequestType
from tests.conftest import parse_image


@pytest.mark.parametrize(
    "file_path,request_type,sequence_number,payload_length,payload",
    [
        ("images/1_qr_code.png", RequestType.start_connection, 0, 4, b".png"),
        ("images/1.1_qr_code.jpeg", RequestType.confirm_connection, 0, 0, b""),
        ("images/2_qr_code.png", RequestType.send_data, 0, 99, callee.InstanceOf(bytes)),
        ("images/2.1_qr_code.jpeg", RequestType.confirm_data, 0, 0, b""),
        ("images/3_qr_code.png", RequestType.finish, 0, 0, callee.InstanceOf(bytes)),
        ("images/3.1_qr_code.jpeg", RequestType.confirm_finish, 0, 0, b""),
    ],
)
def test_parsing(webcam_reader_mock, file_path, request_type, sequence_number, payload_length, payload):
    image = cv2.imread(file_path)

    header, raw_payload = parse_image(webcam_reader_mock, image)

    assert header.request_type == request_type
    assert header.sequence_number == sequence_number
    assert header.payload_length == payload_length
    assert raw_payload == payload


def test_parsing_unrelated_qr_code(webcam_reader_mock):
    image = cv2.imread("images/unrelated_qr_code.png")

    header, raw_payload = parse_image(webcam_reader_mock, image)

    assert header is None
    assert raw_payload is None


def test_parsing_wounded_qr_code(webcam_reader_mock):
    image = cv2.imread("images/wounded_qr_code.png")

    header, raw_payload = parse_image(webcam_reader_mock, image)

    assert header is None
    assert raw_payload is None
