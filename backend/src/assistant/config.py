"""
config.py – Application configuration via pydantic-settings.

All values come from environment variables or the .env file.
No secrets live here; see .env.example for the full list.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Clinic timezone (IANA name)
    clinic_tz: str = "America/New_York"

    # Pin the clock for demos/tests.  Empty string → use system clock.
    assistant_now: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Feature flags
    demo_endpoints_enabled: bool = True
    log_utterances: bool = False

    # ── derived ────────────────────────────────────────────────────────────────

    @field_validator("clinic_tz")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {v!r}") from exc
        return v

    @model_validator(mode="after")
    def _valid_now(self) -> "Settings":
        if self.assistant_now:
            # Must be parseable as an aware ISO-8601 datetime
            try:
                dt = datetime.fromisoformat(self.assistant_now)
            except ValueError as exc:
                raise ValueError(
                    f"ASSISTANT_NOW must be an ISO-8601 datetime, got {self.assistant_now!r}"
                ) from exc
            if dt.tzinfo is None:
                raise ValueError("ASSISTANT_NOW must include timezone offset (e.g. -04:00)")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def clinic_zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.clinic_tz)


# Module-level singleton – import this everywhere
settings = Settings()
