from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./mitcho.db"

    # Security
    SECRET_KEY: str = "dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Email
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "alertes@mitchobenin.org"
    FROM_NAME: str = "MITCHÔ Alertes"

    # RAG / ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION: str = "mitcho_knowledge"

    # Data
    GDELT_MAX_RECORDS: int = 50
    WFP_COUNTRY_CODE: str = "BEN"

    # Google BigQuery — GDELT historique
    # Laisser vide pour utiliser le DOC API classique
    # Valeur : ID de votre projet Google Cloud (ex: "mitcho-analytics-2026")
    GOOGLE_CLOUD_PROJECT: str = ""
    # Chemin vers le fichier JSON du compte de service (optionnel si gcloud CLI est configuré)
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # CORS — includes "null" for file:// origins and common dev ports
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:5500,http://localhost:5500,http://localhost:8080,null"

    @property
    def origins_list(self):
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()
