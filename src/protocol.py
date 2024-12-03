import struct
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from crc64iso.crc64iso import crc64

"""
Protocol Header:
Version: 1 byte
Request type: 1 byte
Sequence number: 4 bytes
Payload Length: 4 bytes
Header + Payload checksum: 8 bytes

Total length: 18 bytes
"""


class RequestType(Enum):
    start_connection = 1  # WANT TO SEND FILE
    confirm_connection = 2
    send_data = 3
    confirm_data = 4
    repeat_data = 5
    finish = 6
    confirm_finish = 7


VERSION = 1
HEADER_LENGTH = 18


@dataclass
class RequestHeader:
    request_type: RequestType
    sequence_number: int
    payload_length: Optional[int] = None
    checksum: Optional[bytes] = None
    version: int = VERSION

    def build(self) -> bytes:
        return struct.pack(
            "<bbii8s",
            self.version,
            self.request_type.value,
            self.sequence_number,
            self.payload_length,
            self.checksum,
        )

    @classmethod
    def parse(cls, data: bytes) -> "RequestHeader":
        if len(data) != HEADER_LENGTH:
            raise ValueError("Header has bad length")

        version, raw_request_type, sequence_number, payload_length, checksum = struct.unpack("<bbii8s", data)

        return cls(RequestType(raw_request_type), sequence_number, payload_length, checksum, version)

    def add_payload(self, payload: Optional[bytes] = None):
        if payload is None:
            self.payload_length = 0
        else:
            self.payload_length = len(payload)

        self.checksum = calculate_hash(self.version, self.request_type, self.sequence_number, payload)


def calculate_hash(version: int, request_type: RequestType, sequence: int, payload: Optional[bytes]):
    hash_tuple = (version, request_type.value, sequence, payload)

    return bytes.fromhex(crc64(str(hash_tuple)))
