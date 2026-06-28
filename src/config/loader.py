from pathlib import Path

import yaml
from pydantic import BaseModel


class ViewportConfig(BaseModel):
    width: int = 1280
    height: int = 800


class BrowserConfig(BaseModel):
    headless: bool = True
    timeout: int = 30000
    viewport: ViewportConfig = ViewportConfig()
    user_data_dir: str = "storage/browser_profile"
    storage_state: str | None = "storage/session.json"


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "gemma3"
    base_url: str = "http://localhost:11434"
    timeout: int = 60


class StorageConfig(BaseModel):
    database: str = "storage/app.db"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str | None = "storage/app.log"


class GreenhouseConfig(BaseModel):
    enabled: bool = False
    board_slugs: list[str] = []


class LeverConfig(BaseModel):
    enabled: bool = False
    company_slugs: list[str] = []


class LinkedInConfig(BaseModel):
    enabled: bool = False
    keywords: list[str] = []
    location: str | None = None


class SchedulerConfig(BaseModel):
    enabled: bool = False
    interval_minutes: int = 60
    max_jobs_per_run: int = 50


class ScreenConfig(BaseModel):
    enabled: bool = True
    hotkey: str = "cmd+j"
    auto_scroll: bool = True
    max_scroll_attempts: int = 5
    scroll_pause: float = 0.5
    ask_before_submit: bool = True


class AppConfig(BaseModel):
    name: str = "job-bot"
    data_dir: str = "storage"


class Config(BaseModel):
    app: AppConfig = AppConfig()
    browser: BrowserConfig = BrowserConfig()
    greenhouse: GreenhouseConfig = GreenhouseConfig()
    lever: LeverConfig = LeverConfig()
    linkedin: LinkedInConfig = LinkedInConfig()
    llm: LLMConfig = LLMConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    screen: ScreenConfig = ScreenConfig()
    storage: StorageConfig = StorageConfig()
    logging: LoggingConfig = LoggingConfig()


class ConfigLoader:
    def __init__(self, config_dir: str | Path = "config"):
        self.config_dir = Path(config_dir)

    def load(self, filename: str = "default.yaml") -> Config:
        path = self.config_dir / filename
        if not path.exists():
            return Config()
        with open(path) as f:
            data = yaml.safe_load(f)
        return Config(**data)
