# Main
import cv2.cv2 as cv

from src.protocol import RequestHeader, RequestType, HEADER_LENGTH
from src.qr_creator import QRCodeCreator
from src.webcam import WebcamReader

import os.path


class QRCodeCommunication:
    def __init__(self):
        self._qr_code_creator = QRCodeCreator()

        self._windows_opened = False

    def start(self):
        file_path = r"c:\Users\Omer\Downloads\icons8-menu-16.png"
        file_content = self.read_file(file_path)

        request_header = RequestHeader(RequestType.send_data, 1, 1, len(file_content))
        request_header.add_payload(file_content)

        image = self._qr_code_creator.create(request_header.build() + file_content)

        self.show_image(image)

        with WebcamReader() as webcam:
            while webcam.is_capturing():
                data = webcam.capture()

                if data is None:
                    continue

                header = RequestHeader.parse(data[:HEADER_LENGTH])
                payload = data[HEADER_LENGTH:header.payload_length]
                print(data)

    def show_image(self, image):
        if self._windows_opened is True:
            cv.destroyAllWindows()

        cv.imshow("QR Code", image)
        cv.waitKey(1)
        self._windows_opened = True

    def close_windows(self):
        cv.destroyAllWindows()
        self._windows_opened = False


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
