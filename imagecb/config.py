"""Environment-driven configuration.

Loaded once at import time. All paths are resolved to absolute paths so
modules don't depend on the process working directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _abspath(p: str | os.PathLike[str]) -> Path:
    return Path(p).expanduser().resolve()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val


@dataclass(frozen=True)
class Settings:
    # Providers
    vlm_provider: str = field(default_factory=lambda: _env("VLM_PROVIDER", "bedrock") or "bedrock")
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "bedrock") or "bedrock")

    # API keys (only needed for cloud providers)
    openai_api_key: Optional[str] = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    anthropic_api_key: Optional[str] = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))

    # AWS region for Bedrock. Bedrock auth (AWS_BEARER_TOKEN_BEDROCK or standard
    # AWS credentials) is resolved implicitly by boto3 from the environment.
    aws_region: str = field(default_factory=lambda: _env("AWS_REGION", "us-east-1") or "us-east-1")

    # Caption / query-parser models. Defaults assume Bedrock cross-region
    # inference profiles; override per provider via env.
    vlm_model: str = field(
        default_factory=lambda: _env("VLM_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
        or "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    llm_model: str = field(
        default_factory=lambda: _env("LLM_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
        or "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )

    # Bedrock embedding / reranking models
    embedding_model: str = field(
        default_factory=lambda: _env("EMBEDDING_MODEL", "amazon.titan-embed-image-v1")
        or "amazon.titan-embed-image-v1"
    )
    embedding_dim: int = field(
        default_factory=lambda: int(_env("EMBEDDING_DIM", "1024") or "1024")
    )
    reranker_model: str = field(
        default_factory=lambda: _env("RERANKER_MODEL", "cohere.rerank-v3-5:0")
        or "cohere.rerank-v3-5:0"
    )

    # Storage paths
    data_dir: Path = field(default_factory=lambda: _abspath(_env("DATA_DIR", "./data") or "./data"))
    chroma_dir: Path = field(default_factory=lambda: _abspath(_env("CHROMA_DIR", "./data/chroma") or "./data/chroma"))
    sqlite_path: Path = field(default_factory=lambda: _abspath(_env("SQLITE_PATH", "./data/imagecb.db") or "./data/imagecb.db"))
    image_cache_dir: Path = field(default_factory=lambda: _abspath(_env("IMAGE_CACHE_DIR", "./data/images") or "./data/images"))
    uploads_dir: Path = field(
        default_factory=lambda: _abspath(
            _env("UPLOADS_DIR")
            or str(_abspath(_env("DATA_DIR", "./data") or "./data") / "uploads")
        )
    )
    bm25_path: Path = field(default_factory=lambda: _abspath(_env("BM25_PATH", "./data/bm25.pkl") or "./data/bm25.pkl"))

    # OCR
    tesseract_cmd: Optional[str] = field(default_factory=lambda: _env("TESSERACT_CMD"))

    # Tunables
    dense_top_k: int = 50
    sparse_top_k: int = 50
    rrf_k: int = 60
    rerank_top_n: int = 50
    default_top_k: int = 10
    enable_conversational_llm: bool = field(
        default_factory=lambda: (_env("ENABLE_CONVERSATIONAL_LLM", "true") or "true").lower()
        in ("1", "true", "yes", "on")
    )
    suggestions_cache_ttl_sec: int = field(
        default_factory=lambda: int(_env("SUGGESTIONS_CACHE_TTL_SEC", "300") or "300")
    )
    suggestions_limit: int = field(
        default_factory=lambda: int(_env("SUGGESTIONS_LIMIT", "4") or "4")
    )

    # Ingest performance
    ingest_workers: int = field(
        default_factory=lambda: int(_env("INGEST_WORKERS", "4") or "4")
    )
    ingest_max_image_side: int = field(
        default_factory=lambda: int(_env("INGEST_MAX_IMAGE_SIDE", "1024") or "1024")
    )
    ingest_batch_upsert: int = field(
        default_factory=lambda: int(_env("INGEST_BATCH_UPSERT", "16") or "16")
    )

    # Admin / telemetry
    admin_api_key: str = field(default_factory=lambda: _env("ADMIN_API_KEY", "") or "")
    weak_result_score_threshold: float = field(
        default_factory=lambda: float(_env("WEAK_RESULT_SCORE_THRESHOLD", "0.25") or "0.25")
    )
    duplicate_similarity_threshold: float = field(
        default_factory=lambda: float(_env("DUPLICATE_SIMILARITY_THRESHOLD", "0.95") or "0.95")
    )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.image_cache_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.bm25_path.parent.mkdir(parents=True, exist_ok=True)


SETTINGS = Settings()
SETTINGS.ensure_dirs()
