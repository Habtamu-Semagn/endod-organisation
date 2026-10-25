import pytest

from app import security, totp


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-0123456789abcdefghijklmnop")


@pytest.mark.parametrize("password, problem", [
    ("short1", "at least 8"),
    ("x" * 129, "at most 128"),
    ("password", "too common"),
    ("Password123", "too common"),
    ("QWERTY123", "too common"),
    ("hr@tena.example", "email"),
    ("OPS", "at least 8"),
])
def test_password_policy_refuses(password, problem):
    assert problem in (security.password_problem(password, "hr@tena.example") or "")


@pytest.mark.parametrize("password", ["abcdefgh-not-common", "all lowercase is fine here", "12345678x", "x" * 128])
def test_password_policy_has_no_composition_rules(password):
    assert security.password_problem(password, "hr@tena.example") is None


def test_the_local_part_of_the_email_is_refused():
    assert "email" in security.password_problem("opsadmin", "opsadmin@endod.example")


def test_passwords_are_argon2id():
    stored = security.hash_password("a fine passphrase")
    assert stored.startswith("$argon2id$")
    assert security.verify_password("a fine passphrase", stored)
    assert not security.verify_password("another passphrase", stored)
    assert not security.verify_password("anything", None)
    assert not security.verify_password("anything", "not-a-hash")


def test_totp_secrets_are_sealed_at_rest():
    secret = totp.new_secret()
    sealed = security.seal(secret)
    assert secret not in sealed and sealed.startswith("v1:")
    assert security.unseal(sealed) == secret
    assert security.seal(secret) != sealed  # a fresh nonce each time


def test_a_different_session_secret_cannot_unseal(monkeypatch):
    sealed = security.seal(totp.new_secret())
    monkeypatch.setenv("SESSION_SECRET", "another-secret-0123456789abcdefghijklmnopqrstu")
    with pytest.raises(Exception):
        security.unseal(sealed)


def test_token_hashes_are_keyed(monkeypatch):
    first = security.token_hash("token")
    assert len(first) == 64 and first != security.token_hash("token2")
    monkeypatch.setenv("SESSION_SECRET", "another-secret-0123456789abcdefghijklmnopqrstu")
    assert security.token_hash("token") != first


def test_recovery_codes():
    codes = {security.new_recovery_code() for _ in range(50)}
    assert len(codes) == 50
    sample = codes.pop()
    assert len(sample) == 14 and sample.count("-") == 2
    # Typed in upper case or without dashes, it still matches.
    assert security.recovery_code_hash(sample.upper().replace("-", " ")) == security.recovery_code_hash(sample)


def test_production_needs_a_session_secret(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ORG_ENVIRONMENT", "production")
    monkeypatch.delenv("SESSION_SECRET")
    with pytest.raises(RuntimeError):
        get_settings().session_secret()
    monkeypatch.setenv("SESSION_SECRET", "too-short")
    with pytest.raises(RuntimeError):
        get_settings().session_secret()


def test_totp_window_and_replay():
    secret = totp.new_secret()
    now = 1_800_000_000.0
    step = totp.current_step(now)
    assert totp.verify(secret, totp.code_at(secret, step), None, now) == step
    assert totp.verify(secret, totp.code_at(secret, step - 1), None, now) == step - 1
    assert totp.verify(secret, totp.code_at(secret, step + 1), None, now) == step + 1
    assert totp.verify(secret, totp.code_at(secret, step - 2), None, now) is None
    assert totp.verify(secret, totp.code_at(secret, step + 2), None, now) is None
    # Used once: that step and anything older is refused.
    assert totp.verify(secret, totp.code_at(secret, step), step, now) is None
    assert totp.verify(secret, totp.code_at(secret, step - 1), step, now) is None
    assert totp.verify(secret, totp.code_at(secret, step + 1), step, now) == step + 1
    assert totp.verify(secret, "12345", None, now) is None
    assert totp.verify(secret, "abcdef", None, now) is None


def test_totp_matches_google_authenticator_settings():
    import pyotp

    secret = totp.new_secret()
    uri = totp.provisioning_uri(secret, "hr@tena.example")
    assert uri.startswith("otpauth://totp/TenaCare:hr%40tena.example?")
    assert f"secret={secret}" in uri and "issuer=TenaCare" in uri
    assert pyotp.TOTP(secret).at(1_800_000_000) == totp.code_at(secret, totp.current_step(1_800_000_000))
