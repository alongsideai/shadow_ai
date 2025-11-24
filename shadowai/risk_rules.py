"""Risk classification rules for AI usage events."""

from typing import List, Tuple
from .models import (
    AIUsageEvent,
    RiskLevel,
    HIGH_SENSITIVITY_DEPARTMENTS,
    MEDIUM_SENSITIVITY_DEPARTMENTS,
    Provider
)


# Threshold for large data transfers (bytes)
LARGE_DATA_THRESHOLD = 4096


def classify_risk(event: AIUsageEvent) -> Tuple[str, List[str]]:
    """
    Classify the risk level of an AI usage event.

    Rules (v1):
    1. HIGH RISK if:
       - External AI provider AND high-sensitivity department, OR
       - Large data transfer (bytes_sent >= 4096) to any known AI provider, OR
       - Unknown AI provider with "ai" in hostname

    2. MEDIUM RISK if:
       - External AI provider AND medium-sensitivity department, OR
       - External AI provider AND lower-sensitivity department (not matching high-risk)

    3. LOW RISK:
       - Any other AI usage event

    Args:
        event: The AI usage event to classify

    Returns:
        Tuple of (risk_level, risk_reasons)
    """
    risk_reasons = []

    # Check department sensitivity
    department = event.department or ""
    is_high_sensitivity = department in HIGH_SENSITIVITY_DEPARTMENTS
    is_medium_sensitivity = department in MEDIUM_SENSITIVITY_DEPARTMENTS

    # Check if provider is known
    is_known_provider = event.provider != Provider.UNKNOWN.value
    is_unknown_with_ai = (
        event.provider == Provider.UNKNOWN.value and
        "ai" in event.url.lower()
    )

    # Check data transfer size
    is_large_transfer = (
        event.bytes_sent is not None and
        event.bytes_sent >= LARGE_DATA_THRESHOLD
    )

    # HIGH RISK CONDITIONS
    # Condition 1: External AI + High-sensitivity department
    if is_known_provider and is_high_sensitivity:
        risk_reasons.append("high_sensitivity_department")

    # Condition 2: Large data transfer to any known AI provider
    if is_large_transfer and is_known_provider:
        risk_reasons.append("large_data_transfer")

    # Condition 3: Unknown AI provider (heuristic)
    if is_unknown_with_ai:
        risk_reasons.append("unknown_ai_provider")

    # If any HIGH risk conditions met, classify as HIGH
    if risk_reasons:
        return RiskLevel.HIGH.value, risk_reasons

    # MEDIUM RISK CONDITIONS
    # Condition 1: External AI + Medium-sensitivity department
    if is_known_provider and is_medium_sensitivity:
        risk_reasons.append("medium_sensitivity_department")
        return RiskLevel.MEDIUM.value, risk_reasons

    # Condition 2: External AI + Lower-sensitivity department
    if is_known_provider:
        risk_reasons.append("external_ai_usage")
        return RiskLevel.MEDIUM.value, risk_reasons

    # LOW RISK (fallback)
    risk_reasons.append("low_risk_ai_usage")
    return RiskLevel.LOW.value, risk_reasons


def apply_risk_classification(events: List[AIUsageEvent]) -> None:
    """
    Apply risk classification to a list of events in-place.

    Args:
        events: List of AIUsageEvent objects to classify
    """
    for event in events:
        risk_level, risk_reasons = classify_risk(event)
        event.risk_level = risk_level
        event.risk_reasons = risk_reasons


def get_risk_explanation(risk_reasons: List[str]) -> str:
    """
    Get a human-readable explanation for risk reasons.

    Args:
        risk_reasons: List of risk reason codes

    Returns:
        Human-readable explanation
    """
    explanations = {
        "high_sensitivity_department": "High-sensitivity department using external AI",
        "large_data_transfer": "Large data transfer detected",
        "unknown_ai_provider": "Unknown/unsanctioned AI tool detected",
        "medium_sensitivity_department": "Medium-sensitivity department using external AI",
        "external_ai_usage": "External AI tool usage",
        "low_risk_ai_usage": "Standard AI usage"
    }

    return "; ".join(explanations.get(reason, reason) for reason in risk_reasons)
