import pytest
from cv2 import cv2

from protocol import RequestHeader, RequestType
from qr_creator import MAX_DATA_SIZE
from tests.conftest import parse_image


@pytest.mark.parametrize(
    "request_type,sequence_number,payload",
    [
        (RequestType.start_connection, 1, b"TEST"),
        (RequestType.confirm_connection, 100, b""),
        (RequestType.send_data, 99, b""),
        (RequestType.confirm_data, 5, b"ABCDEFGH"),
        (RequestType.repeat_data, 4, b"ABC" * 500),
        (RequestType.repeat_data, 4, b"ABC" * 100),
        (RequestType.finish, 3, b"abc"),
        (RequestType.confirm_finish, 0, b"a"),
    ],
)
def test_create_qr_code(webcam_reader_mock, qr_creator, request_type, sequence_number, payload):
    header = RequestHeader(request_type=request_type, sequence_number=sequence_number)
    header.add_payload(payload)

    total_payload = header.build() + payload

    if len(total_payload) > MAX_DATA_SIZE:

        with pytest.raises(ValueError) as e:
            qr_creator.create(total_payload)

        assert e.value.args[0] == "Data is too big"

        return

    qr_code_image = qr_creator.create(total_payload)

    parsed_header, parsed_raw_payload = parse_image(webcam_reader_mock, qr_code_image, cv2.COLOR_BGR2RGB)

    assert parsed_header == header
    assert parsed_raw_payload == payload
