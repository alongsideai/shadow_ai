"""Executive Brief Generator for Shadow AI Detection Platform.

This module generates a Markdown "AI Usage & Value Brief" from enriched
event data, suitable for copy-pasting into Notion, email, or slides.

Usage:
    from shadowai.exec_brief import generate_exec_brief_markdown

    markdown = generate_exec_brief_markdown(events, period_label="Last 7 days")
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# AGGREGATION HELPERS
# =============================================================================

def total_events(events: List[Dict[str, Any]]) -> int:
    """Return total number of events."""
    return len(events)


def total_enriched_events(events: List[Dict[str, Any]]) -> int:
    """Return count of events with value enrichment data."""
    return sum(1 for e in events if e.get('value_category'))


def total_minutes_saved(events: List[Dict[str, Any]]) -> int:
    """Return total minutes saved across all enriched events."""
    return sum(e.get('estimated_minutes_saved', 0) or 0 for e in events)


def rounded_hours_saved(events: List[Dict[str, Any]]) -> float:
    """Return hours saved, rounded to nearest 0.5."""
    minutes = total_minutes_saved(events)
    hours = minutes / 60
    return round(hours * 2) / 2


def value_category_distribution(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return value category counts and percentages.

    Returns:
        Dict mapping category name to {'count': int, 'percentage': float}
    """
    enriched = [e for e in events if e.get('value_category')]
    if not enriched:
        return {}

    counts: Dict[str, int] = {}
    for e in enriched:
        cat = e.get('value_category', 'Unknown')
        counts[cat] = counts.get(cat, 0) + 1

    total = len(enriched)
    return {
        cat: {
            'count': count,
            'percentage': round((count / total) * 100, 1)
        }
        for cat, count in sorted(counts.items(), key=lambda x: -x[1])
    }


def department_usage_distribution(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return department usage counts and percentages.

    Returns:
        Dict mapping department name to {'count': int, 'percentage': float}
    """
    if not events:
        return {}

    counts: Dict[str, int] = {}
    for e in events:
        dept = e.get('department', 'Unknown')
        counts[dept] = counts.get(dept, 0) + 1

    total = len(events)
    return {
        dept: {
            'count': count,
            'percentage': round((count / total) * 100, 1)
        }
        for dept, count in sorted(counts.items(), key=lambda x: -x[1])
    }


def revenue_usage_percentage(events: List[Dict[str, Any]]) -> float:
    """Return percentage of enriched events that are revenue-related."""
    enriched = [e for e in events if e.get('value_category')]
    if not enriched:
        return 0.0

    revenue_count = sum(1 for e in enriched if e.get('value_category') == 'Revenue')
    return round((revenue_count / len(enriched)) * 100, 1)


def most_active_department(events: List[Dict[str, Any]]) -> Tuple[str, int, float]:
    """Return the most active department (ignoring 'Unknown' if others exist).

    Returns:
        Tuple of (department_name, event_count, percentage)
    """
    if not events:
        return ('Unknown', 0, 0.0)

    dist = department_usage_distribution(events)

    # Filter out 'Unknown' if there are other departments
    candidates = {k: v for k, v in dist.items() if k != 'Unknown'}
    if not candidates:
        candidates = dist

    if not candidates:
        return ('Unknown', 0, 0.0)

    top_dept = max(candidates.items(), key=lambda x: x[1]['count'])
    return (top_dept[0], top_dept[1]['count'], top_dept[1]['percentage'])


def underutilized_departments(events: List[Dict[str, Any]], threshold: float = 5.0) -> List[str]:
    """Return list of departments with less than threshold% of events.

    Args:
        events: List of event dicts
        threshold: Percentage threshold (default 5%)

    Returns:
        List of department names
    """
    dist = department_usage_distribution(events)
    return [
        dept for dept, data in dist.items()
        if data['percentage'] < threshold and dept != 'Unknown'
    ]


def risk_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize risk profile of events.

    Returns:
        Dict with keys:
        - high_risk_count: int
        - high_risk_percentage: float
        - policy_violations: int (events with policy_alignment == 'Non-compliant' or 'LikelyViolation')
        - high_risk_departments: List[str]
        - overall_posture: str ('low', 'emerging', or 'meaningful')
    """
    if not events:
        return {
            'high_risk_count': 0,
            'high_risk_percentage': 0.0,
            'policy_violations': 0,
            'high_risk_departments': [],
            'overall_posture': 'low'
        }

    high_risk = [e for e in events if str(e.get('risk_level', '')).lower() == 'high']
    high_risk_count = len(high_risk)
    high_risk_pct = round((high_risk_count / len(events)) * 100, 1) if events else 0

    # Count policy violations
    violation_terms = {'non-compliant', 'likelyviolation', 'likely_violation'}
    policy_violations = sum(
        1 for e in events
        if str(e.get('policy_alignment', '')).lower().replace('-', '').replace(' ', '') in violation_terms
    )

    # High-risk departments
    high_risk_depts = list(set(e.get('department', 'Unknown') for e in high_risk))

    # Determine overall posture
    if high_risk_pct >= 20 or policy_violations >= 5:
        posture = 'meaningful'
    elif high_risk_pct >= 5 or policy_violations >= 1:
        posture = 'emerging'
    else:
        posture = 'low'

    return {
        'high_risk_count': high_risk_count,
        'high_risk_percentage': high_risk_pct,
        'policy_violations': policy_violations,
        'high_risk_departments': high_risk_depts,
        'overall_posture': posture
    }


def compute_all_metrics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute all metrics for the executive brief.

    Returns:
        Dict containing all aggregated metrics
    """
    top_dept, top_dept_count, top_dept_pct = most_active_department(events)

    return {
        'total_events': total_events(events),
        'enriched_events': total_enriched_events(events),
        'minutes_saved': total_minutes_saved(events),
        'hours_saved': rounded_hours_saved(events),
        'value_categories': value_category_distribution(events),
        'department_distribution': department_usage_distribution(events),
        'revenue_pct': revenue_usage_percentage(events),
        'top_department': top_dept,
        'top_department_count': top_dept_count,
        'top_department_pct': top_dept_pct,
        'underutilized_depts': underutilized_departments(events),
        'risk': risk_summary(events),
    }


# =============================================================================
# HEADLINE GENERATION
# =============================================================================

def generate_headlines(metrics: Dict[str, Any], period_label: str) -> List[str]:
    """Generate 3 headline bullets from metrics.

    Args:
        metrics: Dict from compute_all_metrics()
        period_label: Human-readable period string

    Returns:
        List of 3 headline strings
    """
    headlines = []

    # Headline 1: AI adoption + time saved
    hours = metrics['hours_saved']
    total = metrics['total_events']
    enriched = metrics['enriched_events']

    if hours > 0:
        hour_text = f"{hours:.1f} hour" if hours == 1 else f"{hours:.1f} hours"
        headlines.append(
            f"Employees saved an estimated **{hour_text}** of manual work during {period_label} using AI."
        )
    elif enriched > 0:
        headlines.append(
            f"**{enriched}** AI events were enriched with value data during {period_label}, "
            f"though time savings have not yet been quantified."
        )
    else:
        headlines.append(
            f"**{total}** AI events were detected during {period_label}. "
            f"Value enrichment is pending."
        )

    # Headline 2: Department concentration / underutilization
    top_dept = metrics['top_department']
    top_pct = metrics['top_department_pct']
    underutil = metrics['underutilized_depts']

    if top_pct >= 30 and top_dept != 'Unknown':
        headlines.append(
            f"AI usage is concentrated in **{top_dept}** ({top_pct:.0f}% of events); "
            f"other departments are earlier in their adoption."
        )
    elif len(underutil) >= 3:
        dept_list = ', '.join(underutil[:3])
        headlines.append(
            f"Several departments ({dept_list}) show minimal AI adoption, "
            f"indicating opportunity for enablement programs."
        )
    elif top_dept != 'Unknown':
        headlines.append(
            f"**{top_dept}** leads AI adoption with {top_pct:.0f}% of events, "
            f"with usage spreading across the organization."
        )
    else:
        headlines.append(
            "AI usage is distributed across multiple departments without a dominant leader."
        )

    # Headline 3: Risk posture / revenue opportunity
    risk = metrics['risk']
    revenue_pct = metrics['revenue_pct']

    if risk['overall_posture'] == 'meaningful':
        risk_depts = ', '.join(risk['high_risk_departments'][:2]) if risk['high_risk_departments'] else 'multiple areas'
        headlines.append(
            f"**{risk['high_risk_count']}** high-risk AI events were detected, "
            f"mainly in {risk_depts}; these require governance attention."
        )
    elif risk['overall_posture'] == 'emerging':
        headlines.append(
            f"A small number of high-risk events ({risk['high_risk_count']}) were flagged, "
            f"suggesting emerging risk that should be monitored."
        )
    elif revenue_pct == 0:
        headlines.append(
            "No revenue-facing AI use cases were detected yet, indicating significant "
            "upside once workflows are defined."
        )
    else:
        headlines.append(
            f"**{revenue_pct:.0f}%** of AI usage is aligned to revenue-generating activities, "
            f"with overall risk posture remaining low."
        )

    return headlines


# =============================================================================
# OPPORTUNITIES GENERATION
# =============================================================================

def generate_opportunities(metrics: Dict[str, Any]) -> List[str]:
    """Generate 3-5 opportunity/next step bullets from metrics.

    Args:
        metrics: Dict from compute_all_metrics()

    Returns:
        List of opportunity strings
    """
    opportunities = []

    # Check for dominant department to scale
    top_dept = metrics['top_department']
    top_pct = metrics['top_department_pct']
    value_cats = metrics['value_categories']

    if top_pct >= 30 and top_dept != 'Unknown':
        opportunities.append(
            f"**Scale successful patterns in {top_dept}**: Document and formalize "
            f"the AI workflows driving adoption in this team, then share best practices across the organization."
        )

    # Check for value category concentration
    if value_cats:
        top_cat = list(value_cats.keys())[0]
        top_cat_pct = value_cats[top_cat]['percentage']
        if top_cat_pct >= 40:
            cat_display = top_cat.replace('CostReduction', 'cost reduction')
            opportunities.append(
                f"**Double down on {cat_display} use cases**: With {top_cat_pct:.0f}% of value "
                f"coming from {cat_display.lower()}, consider expanding these workflows to additional teams."
            )

    # Check for underutilized departments
    underutil = metrics['underutilized_depts']
    if underutil:
        dept_list = ', '.join(underutil[:3])
        opportunities.append(
            f"**Enable underutilized teams**: Launch AI pilots or training programs "
            f"in {dept_list} to accelerate adoption where usage is currently low."
        )

    # Check for high-risk events
    risk = metrics['risk']
    if risk['high_risk_count'] > 0:
        opportunities.append(
            f"**Address governance gaps**: Review the {risk['high_risk_count']} high-risk events "
            f"and consider migrating users to approved enterprise AI tools with appropriate data controls."
        )

    # Check for policy violations
    if risk['policy_violations'] > 0:
        opportunities.append(
            f"**Strengthen policy training**: {risk['policy_violations']} events were flagged "
            f"for potential policy misalignment. Conduct refresher training on AI acceptable use policies."
        )

    # Revenue opportunity
    revenue_pct = metrics['revenue_pct']
    if revenue_pct == 0 and metrics['enriched_events'] > 0:
        opportunities.append(
            "**Identify revenue-aligned use cases**: No direct revenue-facing AI usage was detected. "
            "Work with Sales, Customer Success, and Product teams to define value-driving workflows."
        )

    # Ensure we have at least 3 opportunities
    if len(opportunities) < 3:
        if metrics['total_events'] > 0:
            opportunities.append(
                "**Continue monitoring**: Maintain visibility into AI usage patterns as adoption matures, "
                "tracking both value delivery and risk indicators."
            )
        if len(opportunities) < 3:
            opportunities.append(
                "**Expand value enrichment**: Run the value enrichment worker on remaining events "
                "to build a more complete picture of AI-driven business impact."
            )

    return opportunities[:5]  # Cap at 5


# =============================================================================
# MARKDOWN BUILDER
# =============================================================================

def generate_exec_brief_markdown(
    events: List[Dict[str, Any]],
    *,
    period_label: Optional[str] = None
) -> str:
    """Generate a Markdown executive brief from enriched event data.

    Args:
        events: List of event dicts (may include value enrichment fields)
        period_label: Optional period label (e.g., "Last 7 days", "Oct 2025").
                      Defaults to "This report period".

    Returns:
        Markdown string suitable for Notion, email, or slides
    """
    if period_label is None:
        period_label = "This report period"

    today = datetime.now().strftime("%Y-%m-%d")
    metrics = compute_all_metrics(events)

    # Build sections
    sections = []

    # --- Title & Metadata ---
    sections.append(f"""# AI Usage & Value Brief

**Period:** {period_label}
**Generated on:** {today}
""")

    # --- Low data warning ---
    if metrics['enriched_events'] < 3:
        sections.append("""---

> **Note:** Insights are based on early, low-volume usage and may not fully reflect organization-wide patterns yet.
""")

    # --- Headline Summary ---
    headlines = generate_headlines(metrics, period_label)
    headline_bullets = '\n'.join(f"- {h}" for h in headlines)
    sections.append(f"""---

## Headline Summary

{headline_bullets}
""")

    # --- Usage Snapshot ---
    hours_display = f"{metrics['hours_saved']:.1f}" if metrics['hours_saved'] > 0 else "0"
    sections.append(f"""---

## Usage Snapshot

| Metric | Value |
|--------|-------|
| Total AI events | {metrics['total_events']} |
| Enriched events | {metrics['enriched_events']} |
| Most active department | {metrics['top_department']} ({metrics['top_department_pct']:.0f}% of events) |
| Revenue-related usage | {metrics['revenue_pct']:.0f}% of enriched events |
| Estimated hours saved | {hours_display} |
""")

    # --- Value Overview ---
    value_cats = metrics['value_categories']
    if value_cats:
        cat_lines = []
        for cat, data in value_cats.items():
            cat_display = cat.replace('CostReduction', 'Cost Reduction')
            cat_lines.append(f"| {cat_display} | {data['percentage']:.0f}% | {data['count']} events |")
        cat_table = '\n'.join(cat_lines)

        # Generate summary paragraph
        top_cats = list(value_cats.keys())[:2]
        top_cats_text = ' and '.join(c.replace('CostReduction', 'cost reduction').lower() for c in top_cats)

        top_depts = list(metrics['department_distribution'].keys())[:2]
        top_depts_text = ' and '.join(d for d in top_depts if d != 'Unknown')[:50] or 'various teams'

        sections.append(f"""---

## Value Overview

| Category | Share | Count |
|----------|-------|-------|
{cat_table}

Most value today comes from **{top_cats_text}**-oriented use cases, primarily in {top_depts_text}. This indicates early success in automating knowledge work, with room to expand into additional value categories.
""")
    else:
        sections.append("""---

## Value Overview

*No value enrichment data available yet.* Run the value enrichment worker to classify events by business value category.
""")

    # --- Risk & Governance ---
    risk = metrics['risk']
    if risk['high_risk_count'] > 0 or risk['policy_violations'] > 0:
        risk_depts_text = ', '.join(risk['high_risk_departments'][:3]) if risk['high_risk_departments'] else 'multiple areas'

        if risk['overall_posture'] == 'meaningful':
            risk_para = (
                f"There is **meaningful risk concentration** in the current AI usage patterns. "
                f"**{risk['high_risk_count']}** events ({risk['high_risk_percentage']:.0f}% of total) were classified as high-risk, "
                f"concentrated in {risk_depts_text}. "
            )
            if risk['policy_violations'] > 0:
                risk_para += f"Additionally, **{risk['policy_violations']}** events were flagged for potential policy misalignment. "
            risk_para += "Immediate governance attention is recommended."
        else:
            risk_para = (
                f"There is **emerging risk** that warrants monitoring. "
                f"**{risk['high_risk_count']}** high-risk events were detected"
            )
            if risk['high_risk_departments']:
                risk_para += f", primarily in {risk_depts_text}"
            risk_para += ". "
            if risk['policy_violations'] > 0:
                risk_para += f"**{risk['policy_violations']}** events showed potential policy concerns. "
            risk_para += "Continue monitoring and consider proactive governance measures."
    else:
        risk_para = (
            "The current AI usage profile shows **low risk**. No significant high-risk events or policy "
            "violations were detected. This is a good foundation for scaling AI adoption, though continued "
            "monitoring is recommended as usage grows."
        )

    sections.append(f"""---

## Risk & Governance

{risk_para}
""")

    # --- Opportunities & Next Steps ---
    opportunities = generate_opportunities(metrics)
    opp_bullets = '\n'.join(f"{i+1}. {opp}" for i, opp in enumerate(opportunities))
    sections.append(f"""---

## Opportunities & Recommended Next Steps

{opp_bullets}
""")

    # --- Footer ---
    sections.append(f"""---

*This brief was auto-generated from {metrics['total_events']} AI usage events. For detailed event data, see the full Shadow AI Scan Report.*
""")

    return '\n'.join(sections)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI entry point for generating executive briefs."""
    parser = argparse.ArgumentParser(
        description="Generate Markdown executive brief from AI usage events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m shadowai.exec_brief --input output/events.json
  python -m shadowai.exec_brief --input output/events.json --period "Last 7 days"
  python -m shadowai.exec_brief --input output/events.json --output exec_brief.md
        """
    )

    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Path to events JSON file (e.g., output/events.json)'
    )

    parser.add_argument(
        '--period', '-p',
        default=None,
        help='Period label (e.g., "Last 7 days", "Oct 2025"). Default: "This report period"'
    )

    parser.add_argument(
        '--output', '-o',
        default=None,
        help='Output file path. If not specified, prints to stdout.'
    )

    args = parser.parse_args()

    # Load events
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            events = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(events, list):
        print("Error: Expected a JSON array of events", file=sys.stderr)
        sys.exit(1)

    # Generate brief
    markdown = generate_exec_brief_markdown(events, period_label=args.period)

    # Output
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        print(f"Executive brief written to: {output_path}")
    else:
        print(markdown)


if __name__ == '__main__':
    main()
