"""Validated server-side application configuration."""
import os
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    api_base_url: str = ""
    connect_timeout: float = 3
    read_timeout: float = 10
    token: str = field(default="", repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        """Fail closed when API mode has incomplete or invalid configuration."""
        mode = os.getenv("SEWS_MODE", "demo").lower()
        url = os.getenv("API_BASE_URL", "").rstrip("/")
        if mode not in {"demo", "api"}:
            raise ValueError("SEWS_MODE는 demo 또는 api여야 합니다.")
        parsed = urlparse(url)
        if mode == "api" and (parsed.scheme not in {"http", "https"} or not parsed.netloc
                              or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("API_BASE_URL에 유효한 HTTP(S) 서버 주소를 설정하세요.")
        connect = float(os.getenv("API_CONNECT_TIMEOUT", "3"))
        read = float(os.getenv("API_READ_TIMEOUT", "10"))
        if not (0 < connect <= 120 and 0 < read <= 120):
            raise ValueError("API 타임아웃은 0초 초과 120초 이하여야 합니다.")
        return cls(mode, url, connect, read, os.getenv("SEWS_API_TOKEN", ""))
