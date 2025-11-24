"""Aggregation and summary generation for AI usage events."""

from collections import Counter, defaultdict
from typing import List, Dict, Any
from .models import AIUsageEvent, RiskLevel, ALLOWED_PROVIDERS


def aggregate_events(events: List[AIUsageEvent]) -> Dict[str, Any]:
    """
    Aggregate AI usage events into a summary with KPIs and insights.

    Args:
        events: List of AIUsageEvent objects

    Returns:
        Dictionary containing aggregated summary data
    """
    if not events:
        return _empty_summary()

    # Basic counts
    total_events = len(events)
    unique_users = len(set(e.user_email for e in events if e.user_email))

    # Risk counts
    risk_counts = Counter(e.risk_level for e in events)

    # Provider counts
    provider_counts = Counter(e.provider for e in events)

    # Department counts
    department_counts = Counter(e.department for e in events if e.department)

    # High-risk events by department
    high_risk_by_dept = Counter(
        e.department for e in events
        if e.risk_level == RiskLevel.HIGH.value and e.department
    )

    # Shadow AI calculation (providers not in allowed list)
    shadow_ai_events = sum(
        1 for e in events
        if e.provider not in ALLOWED_PROVIDERS
    )
    shadow_ai_percentage = (shadow_ai_events / total_events * 100) if total_events > 0 else 0

    # Time range
    timestamps = [e.timestamp for e in events]
    time_range = {
        "start": min(timestamps).isoformat() if timestamps else None,
        "end": max(timestamps).isoformat() if timestamps else None
    }

    # Events per day (for multi-day analysis)
    events_per_day = Counter(e.timestamp.date().isoformat() for e in events)

    # PII/PHI metrics
    pii_events = [e for e in events if e.pii_risk]
    pii_events_count = len(pii_events)
    pii_events_percentage = (pii_events_count / total_events * 100) if total_events > 0 else 0

    # PII events by department
    pii_events_by_dept = Counter(
        e.department for e in pii_events
        if e.department
    )

    # Use-case metrics
    use_case_counts = Counter(e.use_case for e in events)

    # High-risk events by use case
    high_risk_by_use_case = Counter(
        e.use_case for e in events
        if e.risk_level == RiskLevel.HIGH.value
    )

    # Value enrichment metrics
    enriched_events = [e for e in events if e.value_category is not None]
    total_minutes_saved = sum(e.estimated_minutes_saved for e in enriched_events if e.estimated_minutes_saved)
    total_hours_saved = round(total_minutes_saved / 60, 1) if total_minutes_saved else 0
    value_category_counts = Counter(e.value_category for e in enriched_events if e.value_category)

    # Top departments
    top_departments = department_counts.most_common(3)

    # Top users by high-risk events
    high_risk_user_counts = Counter(
        e.user_email for e in events
        if e.risk_level == RiskLevel.HIGH.value and e.user_email
    )
    top_high_risk_users = high_risk_user_counts.most_common(5)

    # Generate insights
    top_risks = _generate_top_risks(
        events,
        department_counts,
        high_risk_by_dept,
        provider_counts,
        risk_counts
    )

    shadow_ai_profile = _generate_shadow_ai_profile(
        department_counts,
        shadow_ai_events,
        total_events
    )

    # Build summary
    summary = {
        "kpis": {
            "total_events": total_events,
            "unique_users": unique_users,
            "shadow_ai_events": shadow_ai_events,
            "shadow_ai_percentage": round(shadow_ai_percentage, 1),
            "high_risk_events": risk_counts.get(RiskLevel.HIGH.value, 0),
            "high_risk_percentage": round(
                (risk_counts.get(RiskLevel.HIGH.value, 0) / total_events * 100)
                if total_events > 0 else 0,
                1
            ),
            "pii_events_count": pii_events_count,
            "pii_events_percentage": round(pii_events_percentage, 1),
            "enriched_events_count": len(enriched_events),
            "enriched_events_percentage": round(
                (len(enriched_events) / total_events * 100) if total_events > 0 else 0,
                1
            ),
            "total_minutes_saved": total_minutes_saved,
            "total_hours_saved": total_hours_saved
        },
        "risk_counts": {
            "low": risk_counts.get(RiskLevel.LOW.value, 0),
            "medium": risk_counts.get(RiskLevel.MEDIUM.value, 0),
            "high": risk_counts.get(RiskLevel.HIGH.value, 0)
        },
        "events_by_provider": dict(provider_counts),
        "events_by_department": dict(department_counts),
        "high_risk_events_by_department": dict(high_risk_by_dept),
        "time_range": time_range,
        "events_per_day": dict(events_per_day),
        "pii_events_by_department": dict(pii_events_by_dept),
        "events_by_use_case": dict(use_case_counts),
        "high_risk_events_by_use_case": dict(high_risk_by_use_case),
        "top_departments": [
            {"name": dept, "count": count}
            for dept, count in top_departments
        ],
        "top_high_risk_users": [
            {"email": email, "high_risk_count": count}
            for email, count in top_high_risk_users
        ],
        "top_risks": top_risks,
        "shadow_ai_profile": shadow_ai_profile,
        "value_enrichment": {
            "enriched_count": len(enriched_events),
            "total_minutes_saved": total_minutes_saved,
            "total_hours_saved": total_hours_saved,
            "value_category_counts": dict(value_category_counts),
            "average_minutes_per_event": round(
                total_minutes_saved / len(enriched_events), 1
            ) if enriched_events else 0
        }
    }

    return summary


def _empty_summary() -> Dict[str, Any]:
    """Return an empty summary structure."""
    return {
        "kpis": {
            "total_events": 0,
            "unique_users": 0,
            "shadow_ai_events": 0,
            "shadow_ai_percentage": 0,
            "high_risk_events": 0,
            "high_risk_percentage": 0,
            "pii_events_count": 0,
            "pii_events_percentage": 0,
            "enriched_events_count": 0,
            "enriched_events_percentage": 0,
            "total_minutes_saved": 0,
            "total_hours_saved": 0
        },
        "risk_counts": {"low": 0, "medium": 0, "high": 0},
        "events_by_provider": {},
        "events_by_department": {},
        "high_risk_events_by_department": {},
        "time_range": {"start": None, "end": None},
        "events_per_day": {},
        "pii_events_by_department": {},
        "events_by_use_case": {},
        "high_risk_events_by_use_case": {},
        "top_departments": [],
        "top_high_risk_users": [],
        "top_risks": [],
        "shadow_ai_profile": "No AI usage detected.",
        "value_enrichment": {
            "enriched_count": 0,
            "total_minutes_saved": 0,
            "total_hours_saved": 0,
            "value_category_counts": {},
            "average_minutes_per_event": 0
        }
    }


def _generate_top_risks(
    events: List[AIUsageEvent],
    department_counts: Counter,
    high_risk_by_dept: Counter,
    provider_counts: Counter,
    risk_counts: Counter
) -> List[Dict[str, str]]:
    """Generate top 3 risk items with descriptions and next steps."""
    risks = []

    # Risk 1: High-sensitivity departments using AI
    if high_risk_by_dept:
        top_dept = high_risk_by_dept.most_common(1)[0]
        dept_name, count = top_dept
        risks.append({
            "title": f"{dept_name} team using public AI tools",
            "description": f"Detected {count} high-risk AI events from the {dept_name} department. "
                          f"This department handles sensitive data that should not be processed by external AI systems.",
            "suggested_next_step": f"Immediately review {dept_name} team's AI usage policies and provide approved alternatives."
        })

    # Risk 2: Unknown/unsanctioned AI tools
    unknown_count = sum(
        1 for e in events
        if "unknown_ai_provider" in e.risk_reasons
    )
    if unknown_count > 0:
        risks.append({
            "title": "Unknown AI tools in use with no governance",
            "description": f"Found {unknown_count} events using unidentified AI services. "
                          f"These tools are outside IT visibility and may pose compliance risks.",
            "suggested_next_step": "Conduct an AI tool inventory and establish an approved vendor list."
        })

    # Risk 3: Large data transfers
    large_transfer_count = sum(
        1 for e in events
        if "large_data_transfer" in e.risk_reasons
    )
    if large_transfer_count > 0:
        risks.append({
            "title": "Significant data being sent to AI providers",
            "description": f"Detected {large_transfer_count} events with large data transfers (>4KB). "
                          f"This may indicate employees uploading documents or sensitive information.",
            "suggested_next_step": "Implement DLP controls and train employees on data handling policies."
        })

    # Risk 4: Widespread shadow AI adoption
    if len(risks) < 3 and risk_counts.get(RiskLevel.MEDIUM.value, 0) > 10:
        risks.append({
            "title": "Widespread shadow AI adoption across organization",
            "description": f"AI usage detected across {len(department_counts)} departments with "
                          f"{risk_counts.get(RiskLevel.MEDIUM.value, 0)} medium-risk events. "
                          f"This indicates a strong demand for AI capabilities.",
            "suggested_next_step": "Launch an AI enablement program with sanctioned tools and governance."
        })

    # Risk 5: Generic fallback
    if len(risks) < 3:
        risks.append({
            "title": "Limited visibility into AI tool usage",
            "description": "Current monitoring only captures network-level data. Actual AI usage may be higher.",
            "suggested_next_step": "Deploy comprehensive AI usage monitoring across endpoints and SaaS apps."
        })

    return risks[:3]


def _generate_shadow_ai_profile(
    department_counts: Counter,
    shadow_ai_events: int,
    total_events: int
) -> str:
    """Generate a plain-language summary of shadow AI usage."""
    if not total_events:
        return "No AI usage detected in the analyzed logs."

    shadow_pct = round(shadow_ai_events / total_events * 100, 1)

    if not department_counts:
        return f"Detected {total_events} AI events. About {shadow_pct}% involve unsanctioned tools."

    top_depts = department_counts.most_common(2)
    dept_summary = " and ".join(
        f"{dept} ({round(count/total_events*100)}%)"
        for dept, count in top_depts
    )

    return (
        f"Most AI usage is in {dept_summary}. "
        f"About {shadow_pct}% of all AI events go to unsanctioned or unknown AI tools."
    )
