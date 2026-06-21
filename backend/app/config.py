import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Travelo AI"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/travelo"
    GEMINI_API_KEY: str = ""
    OPENWEATHER_API_KEY: str = ""
    SERPAPI_KEY: str = ""
    SERPAPI_MAPS_KEY: str = ""
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    REDIS_URL: str = ""
    
    class Config:
        env_file = ".env"

settings = Settings()
