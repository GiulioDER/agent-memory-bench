import base64


def encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode()
