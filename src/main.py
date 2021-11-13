# Main
import glob
import os.path
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Optional

import cv2.cv2 as cv

from protocol import RequestHeader, RequestType, HEADER_LENGTH
from qr_creator import QRCodeCreator
from webcam import WebcamReader


class Status(Enum):
    waiting = 0
    waiting_to_send_file = 1
    sent_data = 2
    finished = 3

    receiving_data = 4


NUM_BYTES_PER_MESSAGE = 200


class QRCodeCommunication:
    def __init__(self):
        self._qr_code_creator = QRCodeCreator()

        self._windows_opened = False

        self._received_files_folder = "received-files"
        self._files_to_send_folder = "send-files"

        self._status = Status.waiting
        self._last_status_transition = datetime.now()

        self._sequence = 0

        self._in_session = False
        self._in_file_sending = False
        self._waiting_response = False

        self._messages_count = 0

        self._file_array: dict[bytes] = defaultdict(bytes)
        self._file_name = None
        self._current_image = None

    def start(self):
        with WebcamReader() as webcam:
            while webcam.is_capturing():
                self.show_image()

                data = webcam.capture()

                if data is not None:
                    header = RequestHeader.parse(data[:HEADER_LENGTH])
                    payload = data[HEADER_LENGTH : HEADER_LENGTH + header.payload_length]

                if data is None and self._status != Status.waiting:
                    continue

                if self._status == Status.waiting:
                    file_content_to_send, file_name_to_send = self._get_file_to_send()

                    if file_content_to_send is not None:
                        self._sequence = 0
                        self._file_array = self._split_content_to_byte_array(file_content_to_send)
                        self._file_name = file_name_to_send

                        start_session_header = RequestHeader(RequestType.start_connection, self._messages_count, 0)
                        start_session_header.add_payload()

                        self._update_status(Status.waiting_to_send_file)
                        self.build_image(start_session_header)
                    elif data is None:
                        continue
                    elif header.request_type == RequestType.start_connection:
                        self._update_status(Status.receiving_data)

                        accept_session_header = RequestHeader(RequestType.confirm_connection, self._messages_count, 0)
                        accept_session_header.add_payload()
                        self.build_image(accept_session_header)
                    else:
                        self._current_image = None
                        self.close_windows()
                elif self._status == Status.waiting_to_send_file:
                    if header.request_type == RequestType.confirm_connection:

                        send_file_header = RequestHeader(RequestType.send_data, self._messages_count, self._sequence)
                        send_file_header.add_payload(self._file_array[self._sequence])

                        self.build_image(send_file_header, self._file_array[self._sequence])
                        self._update_status(Status.sent_data)
                elif self._status == Status.sent_data:
                    if header.request_type == RequestType.confirm_data and header.sequence_number == self._sequence:
                        self._sequence += 1

                        if self._sequence == len(self._file_array):
                            send_finished_header = RequestHeader(RequestType.finish, self._messages_count, 0)
                            send_finished_header.add_payload()

                            self._update_status(Status.finished)
                            self.build_image(send_finished_header)
                        else:
                            send_file_header = RequestHeader(
                                RequestType.send_data, self._messages_count, self._sequence
                            )
                            send_file_header.add_payload(self._file_array[self._sequence])

                            self.build_image(send_file_header, self._file_array[self._sequence])
                    elif header.request_type == RequestType.repeat_data and 0 <= header.sequence_number < len(
                        self._file_array
                    ):
                        self._sequence = header.sequence_number
                        send_file_header = RequestHeader(RequestType.send_data, self._messages_count, self._sequence)
                        send_file_header.add_payload(self._file_array[self._sequence])

                        self._sequence += 1

                        self.build_image(send_file_header, self._file_array[self._sequence])
                elif self._status == Status.finished:
                    if header.request_type == RequestType.confirm_finish:
                        self._sequence = 0
                        self._file_array = defaultdict(bytes)
                        self._update_status(Status.waiting)

                        os.remove(self._files_to_send_folder + "\\" + self._file_name)

                        self._file_name = None

                        self.close_windows()
                elif self._status == Status.receiving_data:
                    if header.request_type == RequestType.send_data:
                        # TODO: Check checksum

                        if header.sequence_number not in self._file_array:
                            print("Received data for sequence", header.sequence_number)
                            self._file_array[header.sequence_number] = payload
                            ack_file_header = RequestHeader(
                                RequestType.confirm_data, self._messages_count, header.sequence_number
                            )
                            ack_file_header.add_payload()
                            self.build_image(ack_file_header)
                        # else:
                        #     self._file_array[header.sequence_number] = payload

                    elif header.request_type == RequestType.finish:
                        file_content = [c for i, c in sorted(list(self._file_array.items()), key=lambda s: s[0])]
                        open(self._received_files_folder + "\\" + "file", "wb").write(b"".join(file_content))

                        confirm_finish_header = RequestHeader(
                            RequestType.confirm_finish, self._messages_count, header.sequence_number
                        )
                        confirm_finish_header.add_payload()

                        self._file_array = defaultdict(bytes)
                        self.build_image(confirm_finish_header)
                        self._update_status(Status.waiting)

                # time.sleep(5)

    def build_image(self, header: RequestHeader, payload: Optional[bytes] = None):
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

    @staticmethod
    def _split_content_to_byte_array(content: bytes):
        y = 0
        byte_array = defaultdict(bytes)
        for i in range(0, len(content), NUM_BYTES_PER_MESSAGE):
            byte_array[y] = content[i : i + NUM_BYTES_PER_MESSAGE]
            y += 1

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

        # if self._windows_opened is True:
        #     cv.destroyAllWindows()

        cv.imshow("QR Code", self._current_image)
        cv.waitKey(1)
        self._windows_opened = True

    def close_windows(self):
        cv.destroyAllWindows()
        self._windows_opened = False
        self._current_image = None

    def read_file(self, file_path: str):
        if not os.path.exists(file_path):
            # TODO
            print("File does not exist")

        with open(file_path, "rb") as fp:
            file_contents = fp.read()

        return file_contents


if __name__ == "__main__":
    qr_code_communicator = QRCodeCommunication()
    qr_code_communicator.start()
