# Main
import glob
import os.path
import time
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import cv2.cv2 as cv

from protocol import RequestHeader, RequestType, HEADER_LENGTH, calculate_hash
from qr_creator import QRCodeCreator
from webcam import WebcamReader

WAITING_TIMEOUT_SECONDS = 10


class Status(Enum):
    waiting = 0
    waiting_to_send_file = 1
    sent_data = 2
    finished = 3

    receiving_data = 4


NUM_BYTES_PER_MESSAGE = 200
PRINT_INTERVAL = 5  # in seconds


class QRCodeCommunication:
    def __init__(self):
        self._qr_code_creator = QRCodeCreator()

        self._received_files_folder = "received-files"
        self._files_to_send_folder = "send-files"

        self._status = Status.waiting
        self._last_status_transition = datetime.now()

        self._sequence = 0

        self._file_array: dict[int, bytes] = defaultdict(bytes)
        self._file_path: Optional[str] = None
        self._file_suffix: Optional[str] = None

        self._current_image = None
        self._last_build = None

        self._prints: dict[str, datetime] = {}

    def start(self):
        with WebcamReader() as webcam:
            # TODO: Add caliberation
            while webcam.is_capturing():
                self.show_image()

                # If we are waiting too long for something, reset and continue
                if (
                        self._status != Status.waiting
                        and self._last_build is not None
                        and datetime.now() - self._last_build > timedelta(seconds=WAITING_TIMEOUT_SECONDS)
                ):
                    print("Took too much waiting and nothing happened")
                    self._reset_and_close()

                    time.sleep(5)

                data = webcam.capture()

                data_valid, header, payload = self._parse_data(data)

                if not data_valid:
                    continue

                if header is None and self._status != Status.waiting:
                    continue

                if self._status == Status.waiting:
                    self._handle_waiting_status(header, payload)
                elif self._status == Status.waiting_to_send_file:
                    self._handle_waiting_to_send_file_status(header)
                elif self._status == Status.sent_data:
                    self._handle_sent_data_status(header)
                elif self._status == Status.finished:
                    self._handle_finished_status(header)
                elif self._status == Status.receiving_data:
                    self._handle_receiving_data_status(header, payload)

    def _reset_and_close(self):
        self._sequence = 0
        self._file_array = defaultdict(bytes)
        self._update_status(Status.waiting)
        self._file_path = None
        self._last_build = None
        self.close_windows()

    def _send_data(self, header: RequestHeader, payload: Optional[bytes] = None):
        header.add_payload(payload)
        self._build_image(header, payload)

    def _print(self, string: str):
        # Reset after 100 lines
        if len(self._prints) == 100:
            self._prints = {}

        if string in self._prints and datetime.now() - self._prints[string] < timedelta(seconds=PRINT_INTERVAL):
            return

        self._prints[string] = datetime.now()

        print(string)

    def _handle_receiving_data_status(self, header: RequestHeader, payload: bytes):
        if header.request_type == RequestType.send_data:
            if header.checksum != calculate_hash(header.version, header.request_type, header.sequence_number, payload):
                self._print("Checksum failed")
                self._send_data(RequestHeader(RequestType.repeat_data, header.sequence_number))
            elif header.sequence_number not in self._file_array:
                self._print(f"Received data for sequence {header.sequence_number}")
                self._file_array[header.sequence_number] = payload
                self._send_data(RequestHeader(RequestType.confirm_data, header.sequence_number))

        elif header.request_type == RequestType.finish:
            file_content = [c for i, c in sorted(list(self._file_array.items()), key=lambda s: s[0])]
            if len(file_content) > 0:
                max_sequence = max(self._file_array.keys())
                missing = set(range(max_sequence + 1)) - set(self._file_array.keys())

                if len(missing) > 0:
                    self._send_data(RequestHeader(RequestType.repeat_data, min(missing)))

                    return

                file_name = f"File-{datetime.now().isoformat()}{self._file_suffix}"

                open(os.path.join(self._received_files_folder, file_name), "wb").write(b"".join(file_content))

            self._send_data(RequestHeader(RequestType.confirm_data, header.sequence_number))

            self._file_array = defaultdict(bytes)
            self._update_status(Status.waiting)

    def _handle_finished_status(self, header: RequestHeader):
        if header.request_type == RequestType.repeat_data:
            if header.sequence_number < len(self._file_array):
                self._send_data(
                    RequestHeader(RequestType.send_data, header.sequence_number), self._file_array[header.sequence_number]
                )
        elif header.request_type == RequestType.confirm_finish:
            os.remove(self._file_path)
            self._reset_and_close()
        elif header.request_type == RequestType.confirm_data:
            self._send_data(RequestHeader(RequestType.finish, 0))

    def _handle_sent_data_status(self, header: RequestHeader):
        if header.request_type == RequestType.confirm_data and header.sequence_number == self._sequence:
            self._sequence += 1

            if self._sequence == len(self._file_array):
                self._send_data(RequestHeader(RequestType.finish, 0))
                self._update_status(Status.finished)
            else:
                self._send_data(RequestHeader(RequestType.send_data, self._sequence), self._file_array[self._sequence])
        elif header.request_type == RequestType.repeat_data and 0 <= header.sequence_number < len(self._file_array):
            self._sequence = header.sequence_number
            self._send_data(RequestHeader(RequestType.send_data, self._sequence), self._file_array[self._sequence])

    def _handle_waiting_to_send_file_status(self, header: RequestHeader):
        if header.request_type == RequestType.confirm_connection:
            self._send_data(RequestHeader(RequestType.send_data, self._sequence), self._file_array[self._sequence])
            self._update_status(Status.sent_data)

    def _handle_waiting_status(self, header: RequestHeader, payload: bytes) -> None:
        file_content_to_send, file_path = self._get_file_to_send()

        if header is not None and header.request_type == RequestType.start_connection:
            self._file_suffix = payload.decode()
            if len(payload) > 10:
                self._file_suffix = None

            self._update_status(Status.receiving_data)

            self._send_data(RequestHeader(RequestType.confirm_connection, 0))
        elif file_content_to_send is not None:
            self._sequence = 0
            self._file_array = self._split_content_to_byte_array(file_content_to_send)
            self._file_path = file_path
            _, self._file_suffix = os.path.splitext(file_path)

            self._send_data(RequestHeader(RequestType.start_connection, 0), self._file_suffix.encode())
            self._update_status(Status.waiting_to_send_file)
        else:
            self._current_image = None
            self.close_windows()

    def _parse_data(self, data: bytes) -> tuple[bool, Optional[RequestHeader], Optional[bytes]]:
        header = None
        payload = None
        if data is not None:
            try:
                header = RequestHeader.parse(data[:HEADER_LENGTH])
                payload = data[HEADER_LENGTH:]

                if len(payload) != header.payload_length:
                    raise ValueError("Bad payload length")
            except ValueError as e:
                self._print(f"Received bad data: {e}")

                return False, None, None

        return True, header, payload

    def _build_image(self, header: RequestHeader, payload: Optional[bytes] = None):
        self._print(
            f"Building image for (request={header.request_type.name}, "
            f"sequence={header.sequence_number}, payload_length={header.payload_length}), "
            f"actual payload length: {len(payload) if payload else 0}"
        )
        payload_data = payload
        if payload is None:
            payload_data = b""

        image_payload = header.build() + payload_data

        self._current_image = self._qr_code_creator.create(image_payload)
        self._last_build = datetime.now()

    @staticmethod
    def _split_content_to_byte_array(content: bytes):
        byte_array = defaultdict(bytes)
        for y, i in enumerate(range(0, len(content), NUM_BYTES_PER_MESSAGE)):
            byte_array[y] = content[i: i + NUM_BYTES_PER_MESSAGE]

        return byte_array

    def _update_status(self, status: Status):
        self._status = status
        self._last_status_transition = datetime.now()

    def _get_file_to_send(self) -> tuple[Optional[bytes], Optional[str]]:
        for file in glob.glob(self._files_to_send_folder + "/*"):
            with open(file, "rb") as fp:
                return fp.read(), file

        return None, None

    def show_image(self):
        if self._current_image is None:
            return

        cv.imshow("QR Code", self._current_image)
        cv.waitKey(1)

    def close_windows(self):
        self._current_image = None
        cv.destroyAllWindows()

    def read_file(self, file_path: str):
        if not os.path.exists(file_path):
            self._print("File does not exist")

        with open(file_path, "rb") as fp:
            file_contents = fp.read()

        return file_contents


if __name__ == "__main__":
    qr_code_communicator = QRCodeCommunication()
    qr_code_communicator.start()
