"""Central configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application-wide settings, populated from .env or environment."""

    # ── Space-Track.org ──
    spacetrack_user: str = Field("", env="SPACETRACK_USER")
    spacetrack_pass: str = Field("", env="SPACETRACK_PASS")

    # ── Anthropic ──
    anthropic_api_key: str = Field("", env="ANTHROPIC_API_KEY")

    # ── Redis ──
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")

    # ── Database ──
    database_url: str = Field("sqlite:///data/sietch_sentinel.db", env="DATABASE_URL")

    # ── ChromaDB ──
    chroma_persist_dir: str = Field("./chroma_data", env="CHROMA_PERSIST_DIR")

    # ── Splunk ──
    splunk_hec_url: str = Field("", env="SPLUNK_HEC_URL")
    splunk_hec_token: str = Field("", env="SPLUNK_HEC_TOKEN")

    # ── Elasticsearch ──
    elasticsearch_url: str = Field("http://localhost:9200", env="ELASTICSEARCH_URL")

    # ── Logging ──
    log_level: str = Field("INFO", env="LOG_LEVEL")

    # ── Agent budgets ──
    agent_max_tool_calls: int = Field(15, env="AGENT_MAX_TOOL_CALLS")
    agent_max_tokens: int = Field(8000, env="AGENT_MAX_TOKENS")
    agent_timeout_seconds: int = Field(90, env="AGENT_TIMEOUT_SECONDS")

    # ── Paths ──
    project_root: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Field(default=None)
    models_dir: Path = Field(default=None)
    logs_dir: Path = Field(default=None)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def model_post_init(self, __context):
        if self.data_dir is None:
            self.data_dir = self.project_root / "data"
        if self.models_dir is None:
            self.models_dir = self.project_root / "models"
        if self.logs_dir is None:
            self.logs_dir = self.project_root / "logs"

        # Ensure directories exist
        for d in [self.data_dir, self.models_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
