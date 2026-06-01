from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GitHub
    GITHUB_WEBHOOK_SECRET: str
    GITHUB_TOKEN: str

    # Hermes Agent (OpenRouter)
    HERMES_API_URL: str = "https://openrouter.ai/api/v1"
    HERMES_API_KEY: str = ""
    HERMES_MODEL: str = "qwen/qwen-2.5-coder-32b-instruct"

    # App
    APP_ENV: str = "production"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
