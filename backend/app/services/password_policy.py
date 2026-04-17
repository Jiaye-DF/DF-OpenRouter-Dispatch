import re

from app.core.exceptions import AppError

_CLASSES = (
    re.compile(r"[a-z]"),
    re.compile(r"[A-Z]"),
    re.compile(r"\d"),
    re.compile(r"[^A-Za-z0-9]"),
)


def validate_password(plain: str) -> None:
    """10–128 字；四類至少三類；違反 → AppError('weak_password', 400)。"""
    if not (10 <= len(plain) <= 128):
        raise AppError("weak_password", code=400)
    matched = sum(1 for rx in _CLASSES if rx.search(plain))
    if matched < 3:
        raise AppError("weak_password", code=400)
