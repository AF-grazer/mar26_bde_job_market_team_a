import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    france_travail_client_id: str = os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "")
    france_travail_client_secret: str = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "")
    france_travail_scope: str = os.getenv("FRANCE_TRAVAIL_SCOPE", "")
    france_travail_token_url: str = os.getenv("FRANCE_TRAVAIL_TOKEN_URL", "")
    france_travail_base_url: str = os.getenv("FRANCE_TRAVAIL_BASE_URL", "")
    indeed_base_url: str = os.getenv("INDEED_BASE_URL", "https://fr.indeed.com")
    user_agent: str = os.getenv("USER_AGENT", "Mozilla/5.0")
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))


settings = Settings()