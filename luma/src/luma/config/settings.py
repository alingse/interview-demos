"""Configuration settings."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    """Application settings."""

    # Database
    db_path: str = "data/anime.db"

    # Checkpoint
    checkpoint_path: str = "data/checkpoint.json"

    # API
    jikan_api_rate: float = 3.0  # requests per second
    jikan_timeout: float = 30.0
    jikan_max_retries: int = 3

    # Pipeline
    batch_size: int = 10
    max_concurrent: int = 5

    # Output
    output_dir: str = "output"
    default_export_path: str = "output/anime.jsonl"

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        return cls(
            db_path=os.getenv("LUMA_DB_PATH", "data/anime.db"),
            checkpoint_path=os.getenv("LUMA_CHECKPOINT_PATH", "data/checkpoint.json"),
            jikan_api_rate=float(os.getenv("LUMA_JIKAN_RATE", "3.0")),
            jikan_timeout=float(os.getenv("LUMA_JIKAN_TIMEOUT", "30.0")),
            jikan_max_retries=int(os.getenv("LUMA_JIKAN_RETRIES", "3")),
            batch_size=int(os.getenv("LUMA_BATCH_SIZE", "10")),
            max_concurrent=int(os.getenv("LUMA_MAX_CONCURRENT", "5")),
            output_dir=os.getenv("LUMA_OUTPUT_DIR", "output"),
            default_export_path=os.getenv("LUMA_EXPORT_PATH", "output/anime.jsonl"),
            log_level=os.getenv("LUMA_LOG_LEVEL", "INFO"),
        )

    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
