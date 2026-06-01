from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GitHub
    GITHUB_WEBHOOK_SECRET: str
    GITHUB_TOKEN: str

    # Hermes Agent (Ollama local)
    HERMES_API_URL: str = "http://localhost:11434/v1"
    HERMES_API_KEY: str = "ollama"
    HERMES_MODEL: str = "qwen2.5-coder:1.5b"

    # App
    APP_ENV: str = "production"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
