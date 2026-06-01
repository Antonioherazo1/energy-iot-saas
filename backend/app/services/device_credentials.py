import hashlib
import hmac
import secrets


def generate_device_key() -> str:
    return secrets.token_urlsafe(32)


def hash_device_key(device_key: str) -> str:
    return hashlib.sha256(device_key.encode("utf-8")).hexdigest()


def verify_device_key(device_key: str | None, device_key_hash: str | None) -> bool:
    if device_key_hash is None:
        return True
    if not device_key:
        return False
    return hmac.compare_digest(hash_device_key(device_key), device_key_hash)

