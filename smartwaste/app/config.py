from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./smartwaste.db"
    secret_key: str = "dev-only-change-me"
    access_token_minutes: int = 60
    admin_password: str = "admin123"
    anthropic_api_key: str | None = None
    max_upload_mb: int = 10
    ai_model: str = "claude-sonnet-5-5"
    vision_backend: str = "yolo"
    vision_model: str = ""
    depot_lat: float = 12.9716
    depot_lng: float = 77.5946
    cors_origins: list[str] = [
"http://127.0.0.1:5500",
"http://localhost:5500",
"http://localhost:3000",
"http://localhost:5173",
]

model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
