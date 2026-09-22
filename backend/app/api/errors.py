from fastapi import HTTPException


class AppError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "details": details or {}},
        )


def bad_request(code: str, message: str, details: dict | None = None) -> AppError:
    return AppError(400, code, message, details)


def not_found(code: str, message: str) -> AppError:
    return AppError(404, code, message)


def conflict(code: str, message: str) -> AppError:
    return AppError(409, code, message)
