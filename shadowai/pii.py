"""PII/PHI risk detection for Shadow AI Detection Platform."""

import re
from typing import Tuple, List
from .models import AIUsageEvent, HIGH_SENSITIVITY_DEPARTMENTS


# Thresholds for PII risk detection
LARGE_PAYLOAD_THRESHOLD = 10_000  # bytes
HIGH_SENS_MODERATE_PAYLOAD_THRESHOLD = 4_096  # bytes

# PII-related keywords to search for in URLs
PII_KEYWORDS = [
    'patient', 'claim', 'record', 'ssn', 'dob', 'mrn',
    'medical', 'diagnosis', 'prescription', 'phi', 'pii',
    'confidential', 'hipaa'
]

# Regex patterns for PII detection
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


def assess_pii_risk(event: AIUsageEvent) -> Tuple[bool, List[str]]:
    """
    Assess PII/PHI risk for an AI usage event using heuristics.

    Since we don't have request bodies, we use coarse rules based on:
    - Payload size (bytes_sent)
    - Department sensitivity
    - URL patterns and keywords

    Rules:
    A. Large payloads (>= 10KB) suggest document/record uploads
    B. High-sensitivity department + moderate payload (>= 4KB)
    C. PII-related keywords in URL
    D. SSN pattern in URL
    E. Email pattern in URL path/query

    Args:
        event: AIUsageEvent to assess

    Returns:
        Tuple of (has_pii_risk: bool, reasons: List[str])
    """
    reasons = []

    # Rule A: Large payloads
    if event.bytes_sent is not None and event.bytes_sent >= LARGE_PAYLOAD_THRESHOLD:
        reasons.append("large_payload")

    # Rule B: High-sensitivity department + moderately large payload
    if (event.department in HIGH_SENSITIVITY_DEPARTMENTS and
        event.bytes_sent is not None and
        event.bytes_sent >= HIGH_SENS_MODERATE_PAYLOAD_THRESHOLD):
        reasons.append("high_sensitivity_large_payload")

    # Rule C: PII keywords in URL (case-insensitive)
    url_lower = event.url.lower()
    for keyword in PII_KEYWORDS:
        if keyword in url_lower:
            reasons.append(f"pii_keyword_in_url:{keyword}")
            break  # Only add one keyword reason to avoid clutter

    # Rule D: SSN pattern in URL
    if SSN_PATTERN.search(event.url):
        reasons.append("ssn_pattern_in_url")

    # Rule E: Email pattern in URL path/query
    # Extract path and query (exclude domain to avoid false positives)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(event.url)
        path_and_query = parsed.path + parsed.query
        if EMAIL_PATTERN.search(path_and_query):
            reasons.append("email_pattern_in_url")
    except Exception:
        pass  # If URL parsing fails, skip this check

    # Return result
    has_pii_risk = len(reasons) > 0
    return has_pii_risk, reasons


def apply_pii_assessment(events: List[AIUsageEvent]) -> None:
    """
    Apply PII risk assessment to a list of events in-place.

    Args:
        events: List of AIUsageEvent objects to assess
    """
    for event in events:
        pii_risk, pii_reasons = assess_pii_risk(event)
        event.pii_risk = pii_risk
        event.pii_reasons = pii_reasons


def get_pii_reason_explanation(reason: str) -> str:
    """
    Get human-readable explanation for a PII risk reason.

    Args:
        reason: PII risk reason code

    Returns:
        Human-readable explanation
    """
    if reason.startswith("pii_keyword_in_url:"):
        keyword = reason.split(":", 1)[1]
        return f"URL contains PII-related keyword '{keyword}'"

    explanations = {
        "large_payload": "Large payload (>10KB) suggests document or record upload",
        "high_sensitivity_large_payload": "High-sensitivity department with large payload (>4KB)",
        "ssn_pattern_in_url": "Social Security Number pattern detected in URL",
        "email_pattern_in_url": "Email address pattern detected in URL",
    }

    return explanations.get(reason, reason)
