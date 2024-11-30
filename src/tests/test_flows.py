import time
from datetime import datetime
from unittest.mock import patch, MagicMock, mock_open as MockOpen

from cv2 import cv2

from protocol import RequestHeader, RequestType
from tests.conftest import parse_image
from webcam import WebcamReader


class WebcamReaderMock:
    def __init__(self):
        self.capture = MagicMock()

    def is_capturing(self):
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_happy_flow_listener(qr_code_communation_mock, webcam_reader_mock):
    class Test1(WebcamReaderMock):
        def __init__(self):
            self.capture = MagicMock(
                side_effect=[
                    WebcamReader.parse_from_image(cv2.imread("images/1_qr_code.png"), cv2.COLOR_BGR2GRAY),
                    WebcamReader.parse_from_image(cv2.imread("images/2_qr_code.png"), cv2.COLOR_BGR2GRAY),
                    WebcamReader.parse_from_image(cv2.imread("images/3_qr_code.png"), cv2.COLOR_BGR2GRAY),
                ]
            )

    mock_open = MagicMock()

    with patch("main.WebcamReader", Test1), patch("main.open", mock_open), patch("main.os.mkdir", MagicMock):
        try:
            qr_code_communation_mock.start()
        except StopIteration:
            pass

    assert mock_open.call_args_list[0][0][0].startswith("received-files\\File-")
    assert mock_open.call_args_list[0][0][0].endswith(".png")
    assert mock_open.call_args_list[0][0][1] == "wb"

    assert len(qr_code_communation_mock._qr_code_creator.responses) == 3

    expected_responses = [
        (
            RequestHeader(
                request_type=RequestType.confirm_connection,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x80!s\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
        (
            RequestHeader(
                request_type=RequestType.confirm_data,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x87\xbfs\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
        (
            RequestHeader(
                request_type=RequestType.confirm_finish,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x84ps\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
    ]
    for response, (expected_header, expected_payload) in zip(
        qr_code_communation_mock._qr_code_creator.responses, expected_responses
    ):
        parsed_header, parsed_payload = parse_image(webcam_reader_mock, image=response, mode=5)

        assert parsed_header == expected_header
        assert expected_payload == parsed_payload


def test_flow_with_repeat_listener(qr_code_communation_mock, webcam_reader_mock, qr_creator):
    header = RequestHeader(request_type=RequestType.send_data, sequence_number=0)
    header.add_payload(b"123")
    header.checksum = b"123"
    total_payload = header.build() + b"123"
    qr_code_image = qr_creator.create(total_payload)

    class Test2(WebcamReaderMock):
        def __init__(self):
            self.capture = MagicMock(
                side_effect=[
                    WebcamReader.parse_from_image(cv2.imread("images/1_qr_code.png"), cv2.COLOR_BGR2GRAY),
                    WebcamReader.parse_from_image(qr_code_image, cv2.COLOR_BGR2BGRA),
                    WebcamReader.parse_from_image(cv2.imread("images/2_qr_code.png"), cv2.COLOR_BGR2GRAY),
                    WebcamReader.parse_from_image(cv2.imread("images/3_qr_code.png"), cv2.COLOR_BGR2GRAY),
                ]
            )

    mock_open = MagicMock()
    with patch("main.WebcamReader", Test2), patch("main.open", mock_open), patch("main.os.mkdir", MagicMock):
        try:
            qr_code_communation_mock.start()
        except StopIteration:
            pass

    assert mock_open.call_args_list[0][0][0].startswith("received-files\\File-")
    assert mock_open.call_args_list[0][0][0].endswith(".png")
    assert mock_open.call_args_list[0][0][1] == "wb"

    assert len(qr_code_communation_mock._qr_code_creator.responses) == 4

    expected_responses = [
        (
            RequestHeader(
                request_type=RequestType.confirm_connection,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x80!s\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
        (
            RequestHeader(
                request_type=RequestType.repeat_data,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x86\xfas\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
        (
            RequestHeader(
                request_type=RequestType.confirm_data,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x87\xbfs\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
        (
            RequestHeader(
                request_type=RequestType.confirm_finish,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x84ps\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
    ]
    for response, (expected_header, expected_payload) in zip(
        qr_code_communation_mock._qr_code_creator.responses, expected_responses
    ):
        parsed_header, parsed_payload = parse_image(webcam_reader_mock, image=response, mode=5)

        assert parsed_header == expected_header
        assert expected_payload == parsed_payload


def test_happy_flow_sender(qr_code_communation_mock, webcam_reader_mock, qr_creator):
    payload = b""

    qr_codes = []

    for rh in [
        RequestHeader(request_type=RequestType.confirm_connection, sequence_number=0),
        RequestHeader(request_type=RequestType.confirm_data, sequence_number=0),
        RequestHeader(request_type=RequestType.confirm_data, sequence_number=1),
        RequestHeader(request_type=RequestType.confirm_finish, sequence_number=1),
    ]:
        rh.add_payload(payload)
        qr_codes.append(rh.build() + payload)

    class Test3(WebcamReaderMock):
        def __init__(self):
            self.capture = MagicMock(side_effect=[None] + qr_codes)

    mock_open = MockOpen(read_data=b"ABCD" * 64)
    mock_glob = MagicMock(glob=MagicMock(return_value=["file_to_send.txt"]))

    with patch("main.WebcamReader", Test3), patch("main.open", mock_open), patch("main.os.remove", MagicMock), patch(
        "main.glob", mock_glob
    ):
        try:
            qr_code_communation_mock.start()
        except StopIteration:
            pass

    assert mock_open.call_args_list[0][0][0] == "file_to_send.txt"

    assert len(qr_code_communation_mock._qr_code_creator.responses) == 4

    expected_requests = [
        (
            RequestHeader(
                request_type=RequestType.start_connection,
                sequence_number=0,
                payload_length=4,
                checksum=b"\xa7\xf22\xd4@_\x8f\xce",
                version=1,
            ),
            b".txt",
        ),
        (
            RequestHeader(
                request_type=RequestType.send_data,
                sequence_number=0,
                payload_length=150,
                checksum=b"\xa2m\xa5\xdd\\&\x11\x19",
                version=1,
            ),
            b"ABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABC"
            b"DABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDAB",
        ),
        (
            RequestHeader(
                request_type=RequestType.send_data,
                sequence_number=1,
                payload_length=106,
                checksum=b"t\xf3r]^x\xb7\x07",
                version=1,
            ),
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDAB"
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCD",
        ),
        (
            RequestHeader(
                request_type=RequestType.finish,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x855s\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
    ]
    for response, (expected_header, expected_payload) in zip(
        qr_code_communation_mock._qr_code_creator.responses, expected_requests
    ):
        parsed_header, parsed_payload = parse_image(webcam_reader_mock, image=response, mode=5)

        assert parsed_header == expected_header
        assert expected_payload == parsed_payload


def test_happy_flow_sender_repeat(qr_code_communation_mock, webcam_reader_mock, qr_creator):
    payload = b""

    qr_codes = []

    for rh in [
        RequestHeader(request_type=RequestType.confirm_connection, sequence_number=0),
        RequestHeader(request_type=RequestType.confirm_data, sequence_number=0),
        RequestHeader(request_type=RequestType.repeat_data, sequence_number=1),
        RequestHeader(request_type=RequestType.confirm_data, sequence_number=1),
        RequestHeader(request_type=RequestType.confirm_finish, sequence_number=1),
    ]:
        rh.add_payload(payload)
        qr_codes.append(rh.build() + payload)

    class Test4(WebcamReaderMock):
        def __init__(self):
            self.capture = MagicMock(side_effect=[None] + qr_codes)

    mock_open = MockOpen(read_data=b"ABCD" * 64)
    mock_glob = MagicMock(glob=MagicMock(return_value=["file_to_send.txt"]))

    with patch("main.WebcamReader", Test4), patch("main.open", mock_open), patch("main.os.remove", MagicMock), patch(
        "main.glob", mock_glob
    ):
        try:
            qr_code_communation_mock.start()
        except StopIteration:
            pass

    assert mock_open.call_args_list[0][0][0] == "file_to_send.txt"

    assert len(qr_code_communation_mock._qr_code_creator.responses) == 5

    expected_requests = [
        (
            RequestHeader(
                request_type=RequestType.start_connection,
                sequence_number=0,
                payload_length=4,
                checksum=b"\xa7\xf22\xd4@_\x8f\xce",
                version=1,
            ),
            b".txt",
        ),
        (
            RequestHeader(
                request_type=RequestType.send_data,
                sequence_number=0,
                payload_length=150,
                checksum=b"\xa2m\xa5\xdd\\&\x11\x19",
                version=1,
            ),
            b"ABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABC"
            b"DABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDAB",
        ),
        (
            RequestHeader(
                request_type=RequestType.send_data,
                sequence_number=1,
                payload_length=106,
                checksum=b"t\xf3r]^x\xb7\x07",
                version=1,
            ),
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDAB"
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCD",
        ),
        (
            RequestHeader(
                request_type=RequestType.send_data,
                sequence_number=1,
                payload_length=106,
                checksum=b"t\xf3r]^x\xb7\x07",
                version=1,
            ),
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDAB"
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCD",
        ),
        (
            RequestHeader(
                request_type=RequestType.finish,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x855s\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
    ]
    for response, (expected_header, expected_payload) in zip(
        qr_code_communation_mock._qr_code_creator.responses, expected_requests
    ):
        parsed_header, parsed_payload = parse_image(webcam_reader_mock, image=response, mode=5)

        assert parsed_header == expected_header
        assert expected_payload == parsed_payload


def test_flow_sender_timeout_and_start_again(qr_code_communation_mock, webcam_reader_mock, qr_creator):
    payload = b""

    qr_codes = []

    for rh in [
        RequestHeader(request_type=RequestType.confirm_connection, sequence_number=0),
        RequestHeader(request_type=RequestType.confirm_data, sequence_number=0),
        RequestHeader(request_type=RequestType.confirm_connection, sequence_number=0),
        RequestHeader(request_type=RequestType.confirm_connection, sequence_number=0),
        RequestHeader(request_type=RequestType.confirm_data, sequence_number=0),
        RequestHeader(request_type=RequestType.confirm_data, sequence_number=1),
        RequestHeader(request_type=RequestType.confirm_finish, sequence_number=1),
    ]:
        rh.add_payload(payload)
        qr_codes.append(rh.build() + payload)

    def _sleep():
        qr_code_communation_mock._now = MagicMock(return_value=datetime(2020, 1, 1))

    effects = [None] + qr_codes
    effects.insert(2, _sleep)

    def side_effect():
        if len(effects) == 0:
            raise StopIteration()

        popped_effect = effects.pop(0)

        if hasattr(popped_effect, "__call__"):
            popped_effect()

            return effects.pop(0)

        qr_code_communation_mock._now = MagicMock(return_value=datetime.now())

        return popped_effect

    class Test5(WebcamReaderMock):
        def __init__(self):
            self.capture = MagicMock(side_effect=side_effect)

    mock_open = MockOpen(read_data=b"ABCD" * 64)
    mock_glob = MagicMock(glob=MagicMock(return_value=["file_to_send.txt"]))

    with patch("main.WebcamReader", Test5), patch("main.open", mock_open), patch("main.os.remove", MagicMock), patch(
        "main.glob", mock_glob
    ), patch("main.time.sleep", MagicMock):
        try:
            qr_code_communation_mock.start()
        except StopIteration:
            pass

    assert mock_open.call_args_list[0][0][0] == "file_to_send.txt"

    assert len(qr_code_communation_mock._qr_code_creator.responses) == 7

    expected_requests = [
        (
            RequestHeader(
                request_type=RequestType.start_connection,
                sequence_number=0,
                payload_length=4,
                checksum=b"\xa7\xf22\xd4@_\x8f\xce",
                version=1,
            ),
            b".txt",
        ),
        (
            RequestHeader(
                request_type=RequestType.send_data,
                sequence_number=0,
                payload_length=150,
                checksum=b"\xa2m\xa5\xdd\\&\x11\x19",
                version=1,
            ),
            b"ABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABC"
            b"DABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDAB",
        ),
        (
            RequestHeader(
                request_type=RequestType.send_data,
                sequence_number=1,
                payload_length=106,
                checksum=b"t\xf3r]^x\xb7\x07",
                version=1,
            ),
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDAB"
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCD",
        ),
        (
            RequestHeader(
                request_type=RequestType.start_connection,
                sequence_number=0,
                payload_length=4,
                checksum=b"\xa7\xf22\xd4@_\x8f\xce",
                version=1,
            ),
            b".txt",
        ),
        (
            RequestHeader(
                request_type=RequestType.send_data,
                sequence_number=0,
                payload_length=150,
                checksum=b"\xa2m\xa5\xdd\\&\x11\x19",
                version=1,
            ),
            b"ABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABC"
            b"DABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDAB",
        ),
        (
            RequestHeader(
                request_type=RequestType.send_data,
                sequence_number=1,
                payload_length=106,
                checksum=b"t\xf3r]^x\xb7\x07",
                version=1,
            ),
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDAB"
            b"CDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCDABCD",
        ),
        (
            RequestHeader(
                request_type=RequestType.finish,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x855s\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
    ]
    for response, (expected_header, expected_payload) in zip(
        qr_code_communation_mock._qr_code_creator.responses, expected_requests
    ):
        parsed_header, parsed_payload = parse_image(webcam_reader_mock, image=response, mode=5)

        assert parsed_header == expected_header
        assert expected_payload == parsed_payload


def test_flow_listener_timeout_and_start_again(qr_code_communation_mock, webcam_reader_mock, qr_creator):
    qr_codes = []

    for rh, payload in [
        (RequestHeader(request_type=RequestType.start_connection, sequence_number=0), b".txt"),
        (RequestHeader(request_type=RequestType.send_data, sequence_number=0), b"ABCDEFG"),
        (RequestHeader(request_type=RequestType.start_connection, sequence_number=0), b".txt"),
        (RequestHeader(request_type=RequestType.send_data, sequence_number=0), b"ABCDEFG"),
        (RequestHeader(request_type=RequestType.finish, sequence_number=0), b""),
    ]:
        rh.add_payload(payload)
        qr_codes.append(rh.build() + payload)

    def _sleep():
        qr_code_communation_mock._now = MagicMock(return_value=datetime(2020, 1, 1))

    effects = qr_codes
    effects.insert(1, _sleep)

    def side_effect():
        if len(effects) == 0:
            raise StopIteration()

        popped_effect = effects.pop(0)

        if hasattr(popped_effect, "__call__"):
            popped_effect()

            return effects.pop(0)

        qr_code_communation_mock._now = MagicMock(return_value=datetime.now())

        return popped_effect

    class Test6(WebcamReaderMock):
        def __init__(self):
            self.capture = MagicMock(side_effect=side_effect)

    mock_open = MockOpen(read_data=b"ABCD" * 64)

    with patch("main.WebcamReader", Test6), patch("main.open", mock_open), patch("main.time.sleep", MagicMock), patch("main.os.mkdir", MagicMock):
        try:
            qr_code_communation_mock.start()
        except StopIteration:
            pass

    assert mock_open.call_args_list[0][0][0].startswith("received-files\\File")
    assert mock_open.call_args_list[0][0][0].endswith(".txt")

    assert len(qr_code_communation_mock._qr_code_creator.responses) == 5

    expected_responses = [
        (
            RequestHeader(
                request_type=RequestType.confirm_connection,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x80!s\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
        (
            RequestHeader(
                request_type=RequestType.confirm_data,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x87\xbfs\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
        (
            RequestHeader(
                request_type=RequestType.confirm_connection,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x80!s\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
        (
            RequestHeader(
                request_type=RequestType.confirm_data,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x87\xbfs\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
        (
            RequestHeader(
                request_type=RequestType.confirm_finish,
                sequence_number=0,
                payload_length=0,
                checksum=b"\x12\xea\x84ps\xb7\xaa\xe5",
                version=1,
            ),
            b"",
        ),
    ]
    for response, (expected_header, expected_payload) in zip(
        qr_code_communation_mock._qr_code_creator.responses, expected_responses
    ):
        parsed_header, parsed_payload = parse_image(webcam_reader_mock, image=response, mode=5)

        assert parsed_header == expected_header
        assert expected_payload == parsed_payload
