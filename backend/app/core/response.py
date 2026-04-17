from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    code: int
    data: T | None = None
    detail: str = ""


def success_response(
    data: Any = None,
    detail: str = "success",
    status_code: int = 200,
) -> JSONResponse:
    body = ApiResponse[Any](success=True, code=status_code, data=data, detail=detail)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def failure_response(code: int, detail: str) -> JSONResponse:
    body = ApiResponse[Any](success=False, code=code, data=None, detail=detail)
    return JSONResponse(status_code=code, content=body.model_dump(mode="json"))
