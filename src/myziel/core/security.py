"""Password hashing, session handling, login rate limiting (NFR-5)."""

import base64
import hashlib
import hmac
import os
import time
from collections import defaultdict, deque

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, digest_b64 = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(digest_b64)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=len(expected), **_SCRYPT)
    return hmac.compare_digest(digest, expected)


class LoginRateLimiter:
    """Allow `max_attempts` failed logins per key within `window_seconds`."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._failures[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def is_blocked(self, key: str) -> bool:
        return len(self._prune(key, time.monotonic())) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
