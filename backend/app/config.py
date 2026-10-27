from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_prefix="",
        extra="ignore",
    )

    # Storage
    data_dir: Path = Field(default=REPO_DIR / "data")
    database_url: str | None = None

    # Public URL of this app, used for links in push notifications
    app_url: str = "http://localhost:8000"

    # Home location for distance calculations (4-digit postcode is enough)
    home_postcode: str = "3511"

    # Sources: comma-separated subset of autoscout24,marktplaats,demo
    sources: str = "demo"
    demo_mode: bool = True
    crawl_interval_min: int = 30
    crawl_request_delay_s: float = 4.0
    crawl_max_pages: int = 3
    scheduler_enabled: bool = True
    user_agent: str = "Autozoeker/0.1 (personal use; +https://github.com/pietjeprecies123/autozoeker)"

    # Alerts (ntfy)
    ntfy_server: str = "https://ntfy.sh"
    ntfy_topic: str = ""
    ntfy_token: str = ""
    digest_hour: int = 8

    # Claude API (optional): enables AI research, natural-language search and ad scans
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    issue_research_ttl_days: int = 180

    # External services (RDW open data, PDOK geocoding)
    rdw_base_url: str = "https://opendata.rdw.nl/resource"
    rdw_app_token: str = ""
    rdw_cache_days: int = 7
    pdok_url: str = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
    online_enrichment: bool = True

    # Optional HTTP basic auth for the whole app (set both to enable)
    basic_auth_user: str = ""
    basic_auth_password: str = ""

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'autozoeker.sqlite'}"

    @property
    def source_list(self) -> list[str]:
        return [s.strip() for s in self.sources.split(",") if s.strip()]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
