from myziel.core.security import LoginRateLimiter, hash_password, verify_password


def test_password_roundtrip():
    stored = hash_password("s3cret-pass")
    assert stored.startswith("scrypt$")
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret-pass", "garbage")


def test_hashes_are_salted():
    assert hash_password("same") != hash_password("same")


def test_rate_limiter_blocks_after_max_attempts():
    limiter = LoginRateLimiter(max_attempts=3)
    for _ in range(3):
        assert not limiter.is_blocked("ip")
        limiter.record_failure("ip")
    assert limiter.is_blocked("ip")
    assert not limiter.is_blocked("other-ip")
    limiter.reset("ip")
    assert not limiter.is_blocked("ip")
