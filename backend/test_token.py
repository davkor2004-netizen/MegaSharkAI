import datetime
import os
import uuid

from jose import jwt


def main() -> None:
    """
    Dev-скрипт для ручной генерации тестового JWT.
    Не выполняется при pytest collection.
    """
    payload = {
        "sub": str(uuid.uuid4()),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.utcnow(),
        "type": "access",
    }
    secret_key = os.getenv("SECRET_KEY", "test-secret-key-for-debug-only-12345")
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
