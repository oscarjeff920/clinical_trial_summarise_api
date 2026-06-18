from typing import Optional

from pydantic_settings import BaseSettings


class ApiSettings(BaseSettings):
    API_HOST: Optional[str] = "0.0.0.0"
    API_PORT: Optional[int] = 8000

def get_api_settings():
    return ApiSettings()