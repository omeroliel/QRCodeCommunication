# Main
import glob
import os.path
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Optional

import cv2.cv2 as cv

from protocol import RequestHeader, RequestType, HEADER_LENGTH, calculate_hash
from qr_creator import QRCodeCreator
from webcam import WebcamReader


class Status(Enum):
    waiting = 0
    waiting_to_send_file = 1
    sent_data = 2
    finished = 3

    receiving_data = 4


NUM_BYTES_PER_MESSAGE = 200

# TODO: Reset status if no answer for too long


class QRCodeCommunication:
    def __init__(self):
        self._qr_code_creator = QRCodeCreator()

        self._received_files_folder = "received-files"
        self._files_to_send_folder = "send-files"

        self._status = Status.waiting
        self._last_status_transition = datetime.now()

        self._sequence = 0

        self._file_array: dict[int, bytes] = defaultdict(bytes)
        self._file_name = None
        self._current_image = None
        self._last_build = None

    def start(self):
        with WebcamReader() as webcam:
            # TODO: Add caliberation
            while webcam.is_capturing():
                self.show_image()

                data = webcam.capture()

                data_valid, header, payload = self._parse_data(data)

                if not data_valid:
                    continue

                if header is None and self._status != Status.waiting:
                    continue

                if self._status == Status.waiting:
                    self._handle_waiting_status(header)
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
        self._file_name = None
        self.close_windows()

    def _send_data(self, header: RequestHeader, payload: Optional[bytes] = None):
        header.add_payload(payload)
        self._build_image(header)

    def _handle_receiving_data_status(self, header: RequestHeader, payload: bytes):
        if header.request_type == RequestType.send_data:
            if header.checksum != calculate_hash(header.version, header.request_type, header.sequence_number, payload):
                print("Checksum failed")
                self._send_data(RequestHeader(RequestType.repeat_data, header.sequence_number))
            elif header.sequence_number not in self._file_array:
                print("Received data for sequence", header.sequence_number)
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

                open(self._received_files_folder + "\\" + "file", "wb").write(b"".join(file_content))

            self._send_data(RequestHeader(RequestType.confirm_data, header.sequence_number))

            self._file_array = defaultdict(bytes)
            self._update_status(Status.waiting)

    def _handle_finished_status(self, header: RequestHeader):
        if header.request_type == RequestType.repeat_data:
            if header.sequence_number < len(self._file_array):
                self._send_data(
                    RequestHeader(RequestType.send, header.sequence_number), self._file_array[header.sequence_number]
                )
        elif header.request_type == RequestType.confirm_finish:
            os.remove(self._files_to_send_folder + "\\" + self._file_name)
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

    def _handle_waiting_status(self, header: RequestHeader) -> None:
        file_content_to_send, file_name_to_send = self._get_file_to_send()

        if header is not None and header.request_type == RequestType.start_connection:
            self._update_status(Status.receiving_data)
            self._send_data(RequestHeader(RequestType.confirm_connection, 0))
        elif file_content_to_send is not None:
            self._sequence = 0
            self._file_array = self._split_content_to_byte_array(file_content_to_send)
            self._file_name = file_name_to_send

            self._send_data(RequestHeader(RequestType.start_connection, 0))
            self._update_status(Status.waiting_to_send_file)
        else:
            self._current_image = None
            self.close_windows()

    @staticmethod
    def _parse_data(data: bytes) -> tuple[bool, Optional[RequestHeader], Optional[bytes]]:
        header = None
        payload = None
        if data is not None:
            try:
                header = RequestHeader.parse(data[:HEADER_LENGTH])
                payload = data[HEADER_LENGTH:]

                if payload != header.payload_length:
                    raise ValueError("Bad payload length")
            except ValueError as e:
                print(f"Received bad data: {e}")

                return False, None, None

        return True, header, payload

    def _build_image(self, header: RequestHeader, payload: Optional[bytes] = None):
        print(
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
            byte_array[y] = content[i : i + NUM_BYTES_PER_MESSAGE]

        return byte_array

    def _update_status(self, status: Status):
        self._status = status
        self._last_status_transition = datetime.now()

    def _get_file_to_send(self) -> tuple[Optional[bytes], Optional[str]]:
        for file in glob.glob(self._files_to_send_folder + "/*"):
            with open(file, "rb") as fp:
                return fp.read(), file.split("\\")[1]

        return None, None

    def show_image(self):
        if self._current_image is None:
            return

        cv.imshow("QR Code", self._current_image)
        cv.waitKey(1)

    def close_windows(self):
        self._current_image = None
        cv.destroyAllWindows()

    @staticmethod
    def read_file(file_path: str):
        if not os.path.exists(file_path):
            print("File does not exist")

        with open(file_path, "rb") as fp:
            file_contents = fp.read()

        return file_contents


if __name__ == "__main__":
    qr_code_communicator = QRCodeCommunication()
    qr_code_communicator.start()
