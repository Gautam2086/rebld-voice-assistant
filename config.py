from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openrouter_api_key: str = ""
    deepgram_api_key: str = ""
    openai_api_key: str = ""

    # LLM
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-4o-mini"

    # Audio
    sample_rate: int = 16000
    record_seconds: int = 10  # max recording length


settings = Settings()
