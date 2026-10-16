import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file (supports both app/.env and parent .env)
env_path_app = Path(__file__).resolve().parent / ".env"
env_path_parent = Path(__file__).resolve().parent.parent / ".env"
if env_path_app.exists():
    load_dotenv(env_path_app)
else:
    load_dotenv(env_path_parent)

def get_database_url() -> str:
    default_railway_url = "mysql+pymysql://root:EakUYgSJCpLWfjlYZhFiDRzXaabexVCz@altaria.proxy.rlwy.net:10750/railway"
    url = os.getenv("DATABASE_URL", default_railway_url)
    if not url or not str(url).strip():
        url = default_railway_url
    else:
        url = str(url).strip()
    if url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    return url

class Settings:
    PROJECT_NAME: str = "ECOMPROFF API"
    VERSION: str = "2.0.0"
    DATABASE_URL: str = get_database_url()
    SECRET_KEY: str = os.getenv("SECRET_KEY", "ecomproff_super_secret_jwt_key_2026_modern_secure_9847192834")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) # 24 hours
    CORS_ORIGINS: list = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "mysql+pymysql://root:EakUYgSJCpLWfjlYZhFiDRzXaabexVCz@altaria.proxy.rlwy.net:10750/railway").split(",")]

settings = Settings()
