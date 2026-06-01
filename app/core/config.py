from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GitHub
    GITHUB_WEBHOOK_SECRET: str
    GITHUB_TOKEN: str

    # Hermes Agent (OpenRouter)
    HERMES_API_URL: str = "https://openrouter.ai/api/v1"
    HERMES_API_KEY: str = ""
    HERMES_MODEL: str = "nousresearch/hermes-3-llama-3.1-405b:free"

    # App
    APP_ENV: str = "production"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
