"""Configuration for TextForge."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RewriteProfile(str, Enum):
    MINIMAL = "minimal"
    NATURAL = "natural"
    ACADEMIC = "academic"
    PROFESSIONAL = "professional"
    CONCISE = "concise"
    CREATIVE = "creative"


class ProfileConfig(BaseModel):
    max_edit_ratio: float = 0.5
    allow_sentence_split: bool = True
    allow_sentence_merge: bool = True
    allow_paragraph_reordering: bool = False
    preserve_paragraph_count: bool = True
    preserve_register: bool = True
    preserve_technical_terms: bool = True
    max_retries: int = 2


PROFILE_DEFAULTS: dict[RewriteProfile, ProfileConfig] = {
    RewriteProfile.MINIMAL: ProfileConfig(
        max_edit_ratio=0.15,
        allow_sentence_split=False,
        allow_sentence_merge=False,
        allow_paragraph_reordering=False,
        preserve_paragraph_count=True,
        preserve_register=True,
        preserve_technical_terms=True,
        max_retries=1,
    ),
    RewriteProfile.NATURAL: ProfileConfig(
        max_edit_ratio=0.35,
        allow_sentence_split=True,
        allow_sentence_merge=True,
        allow_paragraph_reordering=False,
        preserve_paragraph_count=True,
        preserve_register=True,
        preserve_technical_terms=True,
        max_retries=2,
    ),
    RewriteProfile.ACADEMIC: ProfileConfig(
        max_edit_ratio=0.30,
        allow_sentence_split=True,
        allow_sentence_merge=False,
        allow_paragraph_reordering=False,
        preserve_paragraph_count=True,
        preserve_register=True,
        preserve_technical_terms=True,
        max_retries=2,
    ),
    RewriteProfile.PROFESSIONAL: ProfileConfig(
        max_edit_ratio=0.35,
        allow_sentence_split=True,
        allow_sentence_merge=True,
        allow_paragraph_reordering=False,
        preserve_paragraph_count=True,
        preserve_register=True,
        preserve_technical_terms=True,
        max_retries=2,
    ),
    RewriteProfile.CONCISE: ProfileConfig(
        max_edit_ratio=0.50,
        allow_sentence_split=False,
        allow_sentence_merge=True,
        allow_paragraph_reordering=False,
        preserve_paragraph_count=False,
        preserve_register=True,
        preserve_technical_terms=True,
        max_retries=2,
    ),
    RewriteProfile.CREATIVE: ProfileConfig(
        max_edit_ratio=0.60,
        allow_sentence_split=True,
        allow_sentence_merge=True,
        allow_paragraph_reordering=True,
        preserve_paragraph_count=False,
        preserve_register=False,
        preserve_technical_terms=False,
        max_retries=3,
    ),
}


class PreserveConfig(BaseModel):
    math: bool = True
    numbers: bool = True
    citations: bool = True
    code: bool = True
    urls: bool = True
    quotes: bool = True


class RewriteSettings(BaseModel):
    enabled: bool = True
    profile: RewriteProfile = RewriteProfile.ACADEMIC
    provider: str = "anthropic"
    model: str | None = None
    max_retries: int = 2


class ValidationSettings(BaseModel):
    semantic_threshold: float = 0.94
    enforce_numbers: bool = True
    enforce_entities: bool = True
    enforce_claims: bool = True


class ProvenanceSettings(BaseModel):
    enabled: bool = True
    database: str = "./textforge.db"


class WatermarkSettings(BaseModel):
    enabled: bool = False
    detector: str = "synthid_reference"


class TextForgeConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEXTFORGE_",
        env_nested_delimiter="__",
    )

    anthropic_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./textforge.db"
    log_level: str = "INFO"
    log_raw_text: bool = False
    default_rewrite_model: str = "claude-sonnet-4-20250514"

    rewrite: RewriteSettings = Field(default_factory=RewriteSettings)
    preserve: PreserveConfig = Field(default_factory=PreserveConfig)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    provenance: ProvenanceSettings = Field(default_factory=ProvenanceSettings)
    watermark: WatermarkSettings = Field(default_factory=WatermarkSettings)

    def get_profile_config(self, profile: RewriteProfile | None = None) -> ProfileConfig:
        p = profile or self.rewrite.profile
        return PROFILE_DEFAULTS.get(p, PROFILE_DEFAULTS[RewriteProfile.ACADEMIC])

    @classmethod
    def from_yaml(cls, path: str | Path) -> TextForgeConfig:
        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return cls(**data)
