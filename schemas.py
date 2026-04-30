from enum import IntEnum
from typing import List, Optional, Union

from pydantic import BaseModel


class JoiErrorCode(IntEnum):
    SUCCESS = 0

    # 1xxx: 입력 관련
    INVALID_REQUEST = 1001
    NO_DEVICES = 1002
    MISSING_DESCRIPTOR = 1003
    NO_SERVICES = 1004

    # 2xxx: vLLM 관련
    VLLM_TIMEOUT = 2001
    VLLM_UNAVAILABLE = 2002
    EMPTY_GENERATION = 2003

    # 9xxx: 기타
    INTERNAL_ERROR = 9999


class JoiCodeItem(BaseModel):
    name: str
    cron: str = ""
    period: int = -1
    code: str = ""


class JoiLog(BaseModel):
    response_time: Optional[str] = None
    translated_sentence: Optional[str] = None
    logs: str = ""


class JoiLLMResponse(BaseModel):
    success: bool
    error_code: int = JoiErrorCode.SUCCESS
    error_message: str = ""

    code: Optional[Union[List[JoiCodeItem], str]] = None
    command: Optional[str] = None
    log: Optional[JoiLog] = None
