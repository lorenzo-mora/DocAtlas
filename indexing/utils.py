import base64
import binascii
import hashlib
import os
from secrets import token_bytes
from typing import Union
import uuid as uuid_lib


class UUIDManager:
    """A utility class for managing UUIDs, providing methods to
    generate, compress, decompress, hash, and validate UUIDs.

    Methods
    -------
    `uuid()` -> str
        Generate a random UUID and return it as a string.

    `compress_uuid(original_uuid: Union[uuid_lib.UUID, str])` -> str
        Compress a UUID into a shorter Base64 string representation.

    `decompress_uuid(compressed: str)` -> uuid_lib.UUID
        Decompress a Base64 string back into a UUID object.

    `hash_uuid(original_uuid: Union[uuid_lib.UUID, str], hash_length: int = 7)` -> str
        Generate a short hash for a UUID using SHA-256.

    `is_valid(uuid: str)` -> bool
        Validate the format of a given UUID string.
    
    `are_equal(uuid1: Union[uuid_lib.UUID, str], uuid2: Union[uuid_lib.UUID, str])` -> bool
        Check whether the two UUIDs are the same.
    """
    @staticmethod
    def uuid() -> str:
        return str(uuid_lib.uuid4())

    @staticmethod
    def compress_uuid(original_uuid: Union[uuid_lib.UUID, str]) -> str:
        # Ensure the input is a valid UUID
        if not isinstance(original_uuid, uuid_lib.UUID):
            if isinstance(original_uuid, str) and UUIDManager.is_valid(original_uuid):
                original_uuid = uuid_lib.UUID(original_uuid)
            else:
                raise ValueError("Input must be a UUID object or valid UUID string.")

        # Convert the UUID to bytes
        uuid_bytes = original_uuid.bytes
        
        # Encode the bytes to a Base64 string and strip the trailing '=' padding
        compressed = base64.urlsafe_b64encode(uuid_bytes).rstrip(b'=').decode('utf-8')
        
        return compressed

    @staticmethod
    def decompress_uuid(compressed: str) -> uuid_lib.UUID:
        # Validate the input is a valid Base64 encoded string
        try:
            base64.urlsafe_b64decode(compressed + '===')
        except (binascii.Error, ValueError):
            raise ValueError("Input must be a valid Base64 encoded string.")

        # Add back any necessary '=' padding for Base64 decoding
        padding = '=' * ((4 - len(compressed) % 4) % 4)
        compressed += padding
        
        # Decode the Base64 string to bytes
        uuid_bytes = base64.urlsafe_b64decode(compressed)
        
        # Convert the bytes back to a UUID object
        original_uuid = uuid_lib.UUID(bytes=uuid_bytes)
        
        return original_uuid

    @staticmethod
    def hash_uuid(
            original_uuid: Union[uuid_lib.UUID, str],
            hash_length: int = 16
        ) -> str:
        """Generate a short hash for a UUID object and store the mapping."""
        if not (1 <= hash_length <= 64):
            raise ValueError("hash_length must be between 1 and 64.")

        # Ensure the input is a valid UUID
        if not isinstance(original_uuid, (uuid_lib.UUID, str)):
            raise ValueError("Input must be a UUID object or str.")
        if isinstance(original_uuid, uuid_lib.UUID):
            original_uuid = str(original_uuid)

        # Generate a hash using SHA-256 and take the specified number of characters
        random_salt = token_bytes(16)
        hash_value = UUIDManager.hash_from_text(
            original_uuid, random_salt)[:hash_length]
        
        return hash_value

    @staticmethod
    def hash_from_text(text: str, salt: bytes) -> str:
        """Generate a SHA-256 hash from the given text and salt.

        Parameters
        ----------
        text : str
            The input text to be hashed.
        salt : bytes
            The salt bytes to be added to the text before hashing.

        Returns
        -------
        str
            The hexadecimal representation of the SHA-256 hash.

        Raises
        ------
        ValueError
            If the input text is None or empty."""
        if not text:
            raise ValueError("Input text must not be None or empty.")

        sha256_hash = hashlib.sha256(salt + text.encode('utf-8'))

        return sha256_hash.hexdigest()

    @staticmethod
    def is_valid(uuid: str) -> bool:
        """Validation of input UUID format."""
        try:
            uuid_lib.UUID(uuid)
        except ValueError:
            return False

        return True

    @staticmethod
    def are_equal(
            uuid1: Union[uuid_lib.UUID, str],
            uuid2: Union[uuid_lib.UUID, str]
        ) -> bool:
        """Check if two UUIDs are the same."""
        if isinstance(uuid1, str):
            uuid1 = uuid_lib.UUID(uuid1)
        if isinstance(uuid2, str):
            uuid2 = uuid_lib.UUID(uuid2)
        return uuid1 == uuid2