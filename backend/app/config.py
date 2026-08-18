"""Environment-driven configuration.

Nothing security-relevant is hardcoded. Every secret comes from the environment;
`.env.example` documents the full set.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Development-only secret store.
#
# Generating a fresh random master key per process looks harmless but is not: the
# seeder and the API server are separate processes, so wrapped data keys written
# by one become permanently undecryptable by the other. Persisting the generated
# value to a gitignored file keeps a zero-configuration run working across
# processes and restarts.
#
# This is a convenience for local development only. Production must supply
# ENCRYPTION_MASTER_KEY from a KMS/HSM; see docs/SECURITY.md.
_DEV_SECRETS_PATH = BACKEND_DIR / ".dev-secrets.json"


def _dev_secret(name: str, generator) -> str:
    """Read a generated secret, creating and persisting it on first use."""
    store: dict[str, str] = {}
    if _DEV_SECRETS_PATH.exists():
        try:
            store = json.loads(_DEV_SECRETS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            store = {}

    if name not in store:
        store[name] = generator()
        try:
            _DEV_SECRETS_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
            _DEV_SECRETS_PATH.chmod(0o600)
        except OSError:
            logger.warning(
                "Could not persist the generated %s. It will change on restart, "
                "which will make already-encrypted rows unreadable. Set it in .env.",
                name,
            )
        logger.warning(
            "%s was not configured. Generated one and stored it in %s "
            "(development fallback -- set it explicitly in .env for anything real).",
            name,
            _DEV_SECRETS_PATH.name,
        )
    return store[name]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SecureLock"
    environment: str = "development"
    api_prefix: str = "/api"

    # ------------------------------------------------------------------
    # Database. SQLite by default so the demo runs with zero setup; the ORM
    # layer is plain SQLAlchemy so a PostgreSQL URL works unchanged.
    # ------------------------------------------------------------------
    database_url: str = Field(default=f"sqlite:///{(BACKEND_DIR / 'securelock.db').as_posix()}")

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    jwt_secret: str = Field(default="")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 8

    # ------------------------------------------------------------------
    # Crypto. The master key wraps every per-question / per-paper data key.
    # In production this is an HSM or cloud KMS; the interface in
    # app.security.keyvault is deliberately narrow so it can be swapped.
    # ------------------------------------------------------------------
    encryption_master_key: str = Field(default="")

    # ------------------------------------------------------------------
    # Blockchain
    # ------------------------------------------------------------------
    blockchain_enabled: bool = True
    blockchain_rpc_url: str = "http://127.0.0.1:8545"
    blockchain_private_key: str = ""
    blockchain_chain_id: int | None = None
    question_contract_address: str = ""
    paper_contract_address: str = ""
    blockchain_timeout_seconds: int = 20

    # ------------------------------------------------------------------
    # Synthesis engine
    # ------------------------------------------------------------------
    synthesis_seed: int = 20260818
    duplicate_similarity_threshold: float = 0.72
    llm_api_key: str = ""  # entirely optional; demo must work without it

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("jwt_secret")
    @classmethod
    def _default_jwt_secret(cls, v: str) -> str:
        # Persisted rather than per-process, so sessions survive a reload.
        return v or _dev_secret("JWT_SECRET", lambda: secrets.token_urlsafe(48))

    @field_validator("encryption_master_key")
    @classmethod
    def _validate_master_key(cls, v: str) -> str:
        if not v:
            # Must be stable across processes: the seeder and the API server both
            # need it to unwrap the same data keys.
            v = _dev_secret(
                "ENCRYPTION_MASTER_KEY",
                lambda: base64.b64encode(secrets.token_bytes(32)).decode(),
            )
        try:
            raw = base64.b64decode(v)
        except Exception as exc:  # pragma: no cover - configuration error path
            raise ValueError("ENCRYPTION_MASTER_KEY must be base64-encoded") from exc
        if len(raw) != 32:
            raise ValueError("ENCRYPTION_MASTER_KEY must decode to exactly 32 bytes (AES-256)")
        return v

    @property
    def master_key_bytes(self) -> bytes:
        return base64.b64decode(self.encryption_master_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def resolve_contract_addresses(self) -> None:
        """Pick up addresses from the Hardhat deployment file if unset.

        Avoids hand-copying addresses between terminals, which is exactly the
        kind of step that breaks a live demo.
        """
        if self.question_contract_address and self.paper_contract_address:
            return
        for name in ("localhost", "hardhat"):
            path = PROJECT_ROOT / "blockchain" / "deployments" / f"{name}.json"
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            contracts = data.get("contracts", {})
            self.question_contract_address = (
                self.question_contract_address or contracts.get("QuestionRegistry", "")
            )
            self.paper_contract_address = (
                self.paper_contract_address or contracts.get("PaperTimeLock", "")
            )
            if self.question_contract_address and self.paper_contract_address:
                return


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.resolve_contract_addresses()
    return settings


settings = get_settings()
