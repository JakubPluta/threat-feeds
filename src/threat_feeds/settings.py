"""Runtime settings. The feeds themselves are defined in feeds.py."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """THREAT_FEEDS_* env vars locally; the notebook passes widget values."""

    model_config = SettingsConfigDict(env_prefix="THREAT_FEEDS_")

    catalog: str = "workspace"
    schema_name: str = "threat_intel"
    volume: str = "snapshots"
    mode: Literal["replay", "live"] = "replay"  # replay: load committed snapshots; live: download a new one
    snapshots_dir: Path = Path("snapshots")  # read by replay, written by `make snapshot`

    connect_timeout_s: float = 10
    read_timeout_s: float = 60
    retries: int = 3
    backoff_factor: float = 2
    user_agent: str = "threat-feeds/0.1"

    @property
    def volume_path(self) -> Path:
        return Path(f"/Volumes/{self.catalog}/{self.schema_name}/{self.volume}")
