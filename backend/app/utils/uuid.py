import uuid

def generate_uuid() -> bytes:
    """Generate a new UUID as binary data"""
    return uuid.uuid4().bytes


def bytes_to_uuid_string(uuid_bytes: bytes) -> str:
    """Convert binary UUID to string format"""
    return str(uuid.UUID(bytes=uuid_bytes))


def uuid_string_to_bytes(uuid_string: str) -> bytes:
    """Convert string UUID to binary format. Raises ValueError on invalid format."""
    try:
        return uuid.UUID(uuid_string).bytes
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(f"Invalid UUID format: {uuid_string!r}") from e