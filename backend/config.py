"""
Configuration management using pydantic-settings.

This module handles loading and validating environment variables
from .env files and the system environment.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
import logging


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    Environment variables are loaded from .env file if present,
    otherwise from system environment.
    
    Attributes:
        GITHUB_TOKEN: GitHub Personal Access Token for API authentication
        OPENAI_API_KEY: OpenAI API key for LLM access
        PORT: Port for FastAPI server (default: 8000)
        LOG_LEVEL: Logging level (default: INFO)
    """
    
    # Required settings
    GITHUB_TOKEN: str
    OPENAI_API_KEY: str
    
    # Optional settings with defaults
    PORT: int = 8000
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra environment variables
    )
    
    def configure_logging(self) -> None:
        """Configure logging based on LOG_LEVEL setting."""
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


# Global settings instance
# This is loaded once at application startup
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance.
    
    This function implements a singleton pattern to ensure settings
    are loaded only once.
    
    Returns:
        Settings instance with loaded configuration
        
    Raises:
        ValidationError: If required environment variables are missing
    """
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore
        _settings.configure_logging()
    return _settings
