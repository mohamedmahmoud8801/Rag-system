import base64


def bytes_to_base64(file_bytes: bytes) -> str:
    """
    Convert raw file bytes to a Base64 string.
    """
    return base64.b64encode(file_bytes).decode("utf-8")


def file_to_base64(file_path: str) -> str:
    """
    Convert a local file to Base64.

    Used internally for testing/backend processing.
    Frontend should upload bytes instead of sending file paths.
    """
    with open(file_path, "rb") as file:
        return bytes_to_base64(file.read())