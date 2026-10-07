"""Explicit review scope and mappings; no authoritative metadata guessing."""
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class UnitMapping(StrictModel):
    unit: str
    multiplier: Decimal = Field(gt=0, default=Decimal(1), allow_inf_nan=False)

class TextExpectation(StrictModel):
    id: str
    label: str
    expected: str
    selector: str
    kind: Literal['company', 'date', 'phrase'] = 'phrase'

class ReviewConfig(StrictModel):
    metadata: dict[str, str] = Field(default_factory=dict)
    document_metadata: dict[str, dict[str, str]] = Field(default_factory=dict)
    concept_aliases: dict[str, str] = Field(default_factory=dict)
    unit_mappings: dict[str, UnitMapping] = Field(default_factory=dict)
    period_mappings: dict[str, str] = Field(default_factory=dict)
    entity_aliases: dict[str, str] = Field(default_factory=dict)
    scope_aliases: dict[str, str] = Field(default_factory=dict)
    terminology: dict[str, str] = Field(default_factory=lambda: {'유형 자산':'유형자산', '무형 자산':'무형자산'})
    expectations: list[TextExpectation] = Field(default_factory=list)
    sign_constraints: dict[str, Literal['nonnegative','nonpositive']] = Field(default_factory=dict)
    materiality_unit: str | None = None
    numeric_tolerance: Decimal = Field(default=Decimal(0), ge=0, allow_inf_nan=False)
    infer_table_totals: bool = True
    require_references: bool = True
    check_note_references: bool = True
    xbrl_validation: Literal['native','arelle'] = 'arelle'
    taxonomy_packages: list[str] = Field(default_factory=list)
    reference_roles: dict[str, str] = Field(default_factory=dict)
    max_file_bytes: int = Field(default=50_000_000, gt=0, le=500_000_000)
    max_archive_bytes: int = Field(default=100_000_000, gt=0, le=500_000_000)
    max_archive_members: int = Field(default=200, gt=0, le=2000)
    max_cells: int = Field(default=500_000, gt=0, le=5_000_000)

    @field_validator('expectations')
    @classmethod
    def unique_expectations(cls, values):
        if len({v.id for v in values}) != len(values) or any(not v.selector or not v.expected or not v.id for v in values):
            raise ValueError('expectations에는 고유 id와 비어 있지 않은 selector/expected가 필요합니다.')
        return values
