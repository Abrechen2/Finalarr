import pytest
from cryptography.fernet import Fernet

from finalarr.crypto import SecretBox, SecretDecryptError, mask


@pytest.fixture
def box():
    return SecretBox(Fernet.generate_key().decode())


def test_round_trip(box):
    token = box.encrypt("tgram://123:abc/456")
    assert "abc" not in token
    assert box.decrypt(token) == "tgram://123:abc/456"


def test_encryption_is_not_deterministic(box):
    assert box.encrypt("same") != box.encrypt("same")


def test_wrong_key_raises_a_clear_error(box):
    other = SecretBox(Fernet.generate_key().decode())
    with pytest.raises(SecretDecryptError):
        other.decrypt(box.encrypt("value"))


def test_garbage_raises_a_clear_error(box):
    with pytest.raises(SecretDecryptError):
        box.decrypt("garbage")


@pytest.mark.parametrize(
    ("value", "masked"),
    [("", ""), ("abc", "***"), ("0123456789abcdef", "***cdef"), (None, "")],
)
def test_mask(value, masked):
    assert mask(value) == masked
