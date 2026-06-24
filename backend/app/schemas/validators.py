"""
Общие валидаторы для Pydantic-схем.
"""

import re

PASSWORD_MIN_LENGTH = 8


def validate_password_strength(password: str) -> str:
    """
    Проверить сложность пароля.

    Минимум 8 символов, хотя бы одна буква и одна цифра.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов")
    if not re.search(r"[A-Za-zА-Яа-я]", password):
        raise ValueError("Пароль должен содержать хотя бы одну букву")
    if not re.search(r"\d", password):
        raise ValueError("Пароль должен содержать хотя бы одну цифру")
    return password
