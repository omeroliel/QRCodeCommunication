import hashlib
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from crc64iso.crc64iso import crc64

"""
Protocol Header:
Version: 1 byte
Request type: 1 byte
Sequence number: 2 bytes
Payload Length: 2 bytes
Header + Payload checksum: 8 bytes

Total length: 16 bytes
"""


class RequestType(Enum):
    waiting = 0
    start_connection = 1  # WANT TO SEND FILE
    confirm_connection = 2
    send_data = 3
    confirm_data = 4
    repeat_data = 5
    finish = 6
    confirm_finish = 7
    reset = 8
    confirm_reset = 9


VERSION = 1
HEADER_LENGTH = 14


@dataclass
class RequestHeader:
    request_type: RequestType
    sequence_number: int
    payload_length: Optional[int] = None
    checksum: Optional[bytes] = None
    version: int = VERSION

    def build(self) -> bytes:
        return struct.pack(
            "<bbHHH8s",
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

        version, raw_request_type, sequence_number, payload_length, checksum = struct.unpack("<bbHH8s", data)

        return cls(RequestType(raw_request_type), sequence_number, payload_length, checksum, version)

    def add_payload(self, payload: Optional[bytes] = None):
        if payload is None:
            self.payload_length = 0
        else:
            self.payload_length = len(payload)

        self.checksum = self._calculate_hash(payload)

    def _calculate_hash(self, data: bytes):
        hash_tuple = (
            self.version,
            self.request_type.value,
            self.sequence_number,
            data,
        )

        return bytes.fromhex(crc64(str(hash_tuple)))
