import base64
import hashlib
import re
from typing import Union
import uuid as uuid_lib


def contains_placeholders(s: str) -> bool:
    """Determine if a string contains placeholders.

    The function checks if the input string contains any of the
    following placeholders:
    - `'%s'`
    - `'{}'`
    - `'{{}}'`

    Parameters
    ----------
    s : str
        The string to be checked for placeholders.

    Returns
    -------
    bool
        True if the string contains any placeholders, False otherwise.
    """
    return bool(re.search(r'(?:%\w|\{\{|\})', s))

class UUIDManager:
    """A utility class for managing UUIDs, providing methods to
    generate, compress, decompress, hash, and validate UUIDs.

    Methods
    -------
    `uuid()` -> str:
        Generate a random UUID and return it as a string.

    `compress_uuid(original_uuid: Union[uuid_lib.UUID, str])` -> str:
        Compress a UUID into a shorter Base64 string representation.

    `decompress_uuid(compressed: str)` -> uuid_lib.UUID:
        Decompress a Base64 string back into a UUID object.

    `hash_uuid(original_uuid: Union[uuid_lib.UUID, str], hash_length: int = 7)` -> str:
        Generate a short hash for a UUID using SHA-256.

    `is_valid(uuid: str)` -> bool:
        Validate the format of a given UUID string.
    """
    @staticmethod
    def uuid() -> str:
        return str(uuid_lib.uuid4())

    @staticmethod
    def compress_uuid(original_uuid: Union[uuid_lib.UUID, str]) -> str:
        # Ensure the input is a valid UUID
        if not isinstance(original_uuid, (uuid_lib.UUID, str)):
            raise ValueError("Input must be a UUID object or str.")
        if isinstance(original_uuid, str):
            original_uuid = uuid_lib.UUID(original_uuid)

        # Convert the UUID to bytes
        uuid_bytes = original_uuid.bytes
        
        # Encode the bytes to a Base64 string and strip the trailing '=' padding
        compressed = base64.urlsafe_b64encode(uuid_bytes).rstrip(b'=').decode('utf-8')
        
        return compressed

    @staticmethod
    def decompress_uuid(compressed: str) -> uuid_lib.UUID:
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
            hash_length: int = 7
        ) -> str:
        """Generate a short hash for a UUID object and store the mapping."""
        # Ensure the input is a valid UUID
        if not isinstance(original_uuid, (uuid_lib.UUID, str)):
            raise ValueError("Input must be a UUID object or str.")
        if isinstance(original_uuid, str):
            original_uuid = uuid_lib.UUID(original_uuid)

        # Generate a hash using SHA-256 and take the specified number of characters
        hash_value = hashlib.sha256(original_uuid.bytes).hexdigest()[:hash_length]
        
        return hash_value

    @staticmethod
    def is_valid(uuid: str) -> bool:
        """Validation of input UUID format."""
        try:
            uuid_lib.UUID(uuid)
        except ValueError:
            return False

        return True