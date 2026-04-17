import pytest

from app.core.exceptions import AppError
from app.services.password_policy import validate_password


def test_rejects_short_password() -> None:
    with pytest.raises(AppError) as e:
        validate_password("Short1!")
    assert e.value.detail == "weak_password"


def test_rejects_two_classes_only() -> None:
    with pytest.raises(AppError):
        validate_password("abcdefghij")  # 只有 lower


def test_accepts_three_classes() -> None:
    validate_password("Abcdefghij1")  # lower + upper + digit


def test_accepts_four_classes() -> None:
    validate_password("Abcdefg1!!")
