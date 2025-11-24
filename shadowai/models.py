"""Data models for Shadow AI Detection Platform."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Provider(str, Enum):
    """Known AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GITHUB_COPILOT = "github_copilot"
    PERPLEXITY = "perplexity"
    UNKNOWN = "unknown"


class Service(str, Enum):
    """Types of AI services."""
    CHAT = "chat"
    EMBEDDINGS = "embeddings"
    CODE_ASSIST = "code_assist"
    WEB_UI = "web_ui"
    API = "api"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """Risk classification levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# High-sensitivity departments
HIGH_SENSITIVITY_DEPARTMENTS = {
    "Clinical", "Claims", "Legal", "Trading", "Underwriting", "Wealth Management"
}

# Medium-sensitivity departments
MEDIUM_SENSITIVITY_DEPARTMENTS = {
    "Finance", "HR"
}

# Allowed/sanctioned providers (empty for now - all AI is shadow AI)
ALLOWED_PROVIDERS = set()


@dataclass
class AIUsageEvent:
    """Represents a single AI usage event detected in logs."""

    id: str
    timestamp: datetime
    user_email: Optional[str]
    department: Optional[str]
    source_ip: Optional[str]
    provider: str
    service: str
    url: str
    bytes_sent: Optional[int]
    bytes_received: Optional[int]
    risk_level: str
    risk_reasons: list[str] = field(default_factory=list)
    source_system: str = "network_logs_v1"
    notes: Optional[str] = None
    # PII/PHI detection fields
    pii_risk: bool = False
    pii_reasons: list[str] = field(default_factory=list)
    # Use-case classification
    use_case: str = "unknown"
    # Value enrichment fields (optional, populated by worker)
    value_category: Optional[str] = None
    estimated_minutes_saved: Optional[int] = None
    business_outcome: Optional[str] = None
    policy_alignment: Optional[str] = None
    value_summary: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_email": self.user_email,
            "department": self.department,
            "source_ip": self.source_ip,
            "provider": self.provider,
            "service": self.service,
            "url": self.url,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "risk_level": self.risk_level,
            "risk_reasons": self.risk_reasons,
            "source_system": self.source_system,
            "notes": self.notes,
            "pii_risk": self.pii_risk,
            "pii_reasons": self.pii_reasons,
            "use_case": self.use_case,
            "value_category": self.value_category,
            "estimated_minutes_saved": self.estimated_minutes_saved,
            "business_outcome": self.business_outcome,
            "policy_alignment": self.policy_alignment,
            "value_summary": self.value_summary
        }
