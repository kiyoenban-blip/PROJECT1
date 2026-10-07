from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field

class Severity(str, Enum):
    CRITICAL = 'CRITICAL'
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'

class RecommendationType(str, Enum):
    LIKELY_FIX = 'LIKELY_FIX'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED'
    INVESTIGATE = 'INVESTIGATE'
    INFORMATION = 'INFORMATION'

class FindingCategory(str, Enum):
    RECONCILIATION = 'RECONCILIATION'
    EXCEL = 'EXCEL'
    STRUCTURE = 'STRUCTURE'
    CONSISTENCY = 'CONSISTENCY'
    VERSION = 'VERSION'
    FOOTING = 'FOOTING'

class Fact(BaseModel):
    concept: str
    value: Decimal
    period: str
    unit: str
    entity: str
    scope: str
    location: str
    source: str
    dimensions: str = ''
    decimals: str | None = None
    raw_value: str | None = None
    raw_unit: str | None = None
    extraction_confidence: float = 1.0
    def key(self):
        return (self.concept, self.period, self.unit, self.entity, self.scope, self.dimensions)

class Finding(BaseModel):
    finding_id: str = ''
    issue_id: str = ''
    rule_id: str
    severity: Severity
    category: FindingCategory
    primary_file: str
    page: int | None = None
    sheet: str | None = None
    cell: str | None = None
    section: str | None = None
    original_text: str | None = None
    actual: str | None = None
    expected: str | None = None
    difference: str | None = None
    reference_file: str | None = None
    reference_location: str | None = None
    message: str
    evidence: list[str] = Field(min_length=1)
    suggestion: str | None = None
    suggested_text: str | None = None
    recommendation_type: RecommendationType = RecommendationType.REVIEW_REQUIRED
    confidence: float = Field(default=.8, ge=0, le=1)
    difference_numeric: Decimal | None = None
    materiality_ratio: Decimal | None = None
    performance_materiality_ratio: Decimal | None = None
    trivial_threshold_ratio: Decimal | None = None
    anchor: str
    clearing: str = 'NEW'
    status: str = '미확인'
    owner: str = ''
    reviewer: str = ''
    memo: str = ''
    unit: str | None = None
    match_key: str | None = None
    verification: str | None = None
    target_contexts: list[str] = Field(default_factory=list)

class Document(BaseModel):
    path: str
    sha256: str
    facts: list[Fact] = Field(default_factory=list)
    texts: dict[str, str] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    logs: list[dict] = Field(default_factory=list)
    # Successful evaluation targets, not merely parsed locations.
    checked: list[str] = Field(default_factory=list)

    tables: list[dict] = Field(default_factory=list)
    calculations: list[dict] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    dependencies: dict[str, str] = Field(default_factory=dict)
    kind: str = ''
    parse_complete: bool = True
    target_signatures: dict[str, str] = Field(default_factory=dict)
    target_counts: dict[str, int] = Field(default_factory=dict)
