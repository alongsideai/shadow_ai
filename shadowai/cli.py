"""Command-line interface for Shadow AI Detection Platform."""

import argparse
import sys
from pathlib import Path
from .parser import parse_csv_logs, parse_multiple_csv_files
from .pii import apply_pii_assessment
from .use_cases import apply_use_case_classification
from .risk_rules import apply_risk_classification
from .aggregator import aggregate_events
from .report import write_events_json, write_summary_json, render_dashboard
from .database import Database


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Shadow AI Detection Platform - Detect and analyze shadow AI usage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m shadowai.cli --input data/sample_logs.csv
  python -m shadowai.cli --input data/logs.csv --output-dir results
  python -m shadowai.cli --input-dir data/logs_week_01 --output-dir output
  python -m shadowai.cli --input data/logs.csv --use-db-enrichment

Note: Events are automatically saved to shadowai.db. To enrich them with value data:
  1. Run: python -m shadowai.value_enrichment_worker
  2. Re-run with --use-db-enrichment to see enriched data in reports
        """
    )

    parser.add_argument(
        '--input',
        help='Path to a single CSV log file'
    )

    parser.add_argument(
        '--input-dir',
        help='Path to directory containing multiple CSV log files'
    )

    parser.add_argument(
        '--output-dir',
        default='output',
        help='Output directory for generated files (default: output)'
    )

    parser.add_argument(
        '--source-system',
        default='network_logs_v1',
        help='Source system identifier (default: network_logs_v1)'
    )

    parser.add_argument(
        '--db-path',
        default='shadowai.db',
        help='Path to SQLite database file (default: shadowai.db)'
    )

    parser.add_argument(
        '--no-db',
        action='store_true',
        help='Skip saving events to database (faster for one-off analysis)'
    )

    parser.add_argument(
        '--use-db-enrichment',
        action='store_true',
        help='Load enriched data from database when generating reports (requires --db-path)'
    )

    args = parser.parse_args()

    # Validate that exactly one of --input or --input-dir is provided
    if args.input and args.input_dir:
        print("Error: Please provide either --input OR --input-dir, not both.", file=sys.stderr)
        sys.exit(1)

    if not args.input and not args.input_dir:
        print("Error: Please provide either --input (single file) or --input-dir (directory).", file=sys.stderr)
        sys.exit(1)

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Shadow AI Detection Platform")
    print("=" * 60)
    print()

    # Step 1: Parse CSV logs (single file or directory)
    if args.input:
        # Single file mode
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)

        print(f"[1/5] Parsing log file: {args.input}")
        try:
            events = parse_csv_logs(str(input_path), args.source_system)
            print(f"      → Found {len(events)} AI-related events")
        except Exception as e:
            print(f"Error: Failed to parse log file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Directory mode
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            print(f"Error: Input directory not found: {args.input_dir}", file=sys.stderr)
            sys.exit(1)

        if not input_dir.is_dir():
            print(f"Error: Path is not a directory: {args.input_dir}", file=sys.stderr)
            sys.exit(1)

        # Find all CSV files in directory
        csv_files = sorted(input_dir.glob("*.csv"))
        if not csv_files:
            print(f"Error: No CSV files found in directory: {args.input_dir}", file=sys.stderr)
            sys.exit(1)

        print(f"[1/5] Parsing {len(csv_files)} log files from: {args.input_dir}")
        try:
            events = parse_multiple_csv_files(
                [str(f) for f in csv_files],
                args.source_system
            )
            print(f"      → Found {len(events)} AI-related events across all files")
        except Exception as e:
            print(f"Error: Failed to parse log files: {e}", file=sys.stderr)
            sys.exit(1)

    if not events:
        print("\nNo AI usage detected in the provided logs.")
        print("The log file may not contain any AI-related requests.")
        sys.exit(0)

    # Step 2: Apply PII assessment and use-case classification
    print(f"[2/6] Applying PII/PHI risk assessment and use-case classification")
    apply_pii_assessment(events)
    apply_use_case_classification(events)
    pii_risk_count = sum(1 for e in events if e.pii_risk)
    print(f"      → {pii_risk_count} events with potential PII/PHI risk")

    # Step 3: Apply risk classification
    print(f"[3/7] Applying security risk classification rules")
    apply_risk_classification(events)
    high_risk_count = sum(1 for e in events if e.risk_level == "high")
    medium_risk_count = sum(1 for e in events if e.risk_level == "medium")
    low_risk_count = sum(1 for e in events if e.risk_level == "low")
    print(f"      → High risk: {high_risk_count}, Medium risk: {medium_risk_count}, Low risk: {low_risk_count}")

    # Step 4: Save to database (if enabled)
    db = None
    if not args.no_db:
        print(f"[4/7] Saving events to database: {args.db_path}")
        try:
            db = Database(args.db_path)
            for event in events:
                db.upsert_event(event)
            db_stats = db.get_stats()
            print(f"      → Saved {len(events)} events ({db_stats['total_events']} total in DB, {db_stats['enriched_events']} enriched)")
        except Exception as e:
            print(f"      ⚠ Warning: Failed to save to database: {e}")
            db = None
    else:
        print(f"[4/7] Skipping database save (--no-db flag set)")

    # Step 4.5: Load enriched data from database if requested
    if args.use_db_enrichment and db:
        print(f"[4.5/7] Loading enriched data from database")
        try:
            enriched_events = db.get_all_events_with_enrichment()
            # Create a lookup by event ID
            enriched_lookup = {e.id: e for e in enriched_events}
            # Merge enrichment data into current events
            for event in events:
                if event.id in enriched_lookup:
                    enriched = enriched_lookup[event.id]
                    event.value_category = enriched.value_category
                    event.estimated_minutes_saved = enriched.estimated_minutes_saved
                    event.business_outcome = enriched.business_outcome
                    event.policy_alignment = enriched.policy_alignment
                    event.value_summary = enriched.value_summary
            enriched_count = sum(1 for e in events if e.value_category is not None)
            print(f"      → Loaded enrichment for {enriched_count} events")
        except Exception as e:
            print(f"      ⚠ Warning: Failed to load enrichment: {e}")

    # Step 5: Aggregate summary
    print(f"[5/7] Aggregating usage data and generating insights")
    summary = aggregate_events(events)
    unique_users = summary['kpis']['unique_users']
    shadow_ai_pct = summary['kpis']['shadow_ai_percentage']
    print(f"      → {unique_users} unique users, {shadow_ai_pct}% shadow AI")

    # Step 6: Write output files
    print(f"[6/7] Writing output files to: {output_dir}")

    events_path = output_dir / "events.json"
    write_events_json(events, events_path)
    print(f"      → {events_path}")

    summary_path = output_dir / "summary.json"
    write_summary_json(summary, summary_path)
    print(f"      → {summary_path}")

    # Step 7: Generate HTML dashboard
    print(f"[7/7] Generating executive dashboard")
    report_path = output_dir / "report.html"
    render_dashboard(events, summary, report_path)
    print(f"      → {report_path}")

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Processed: {len(events)} AI events")
    print(f"High-risk events: {high_risk_count}")
    print(f"Unique users: {unique_users}")
    print(f"Shadow AI share: {shadow_ai_pct}%")
    if summary.get('value_enrichment', {}).get('enriched_count', 0) > 0:
        value_data = summary['value_enrichment']
        print(f"Value enrichment: {value_data['enriched_count']} events enriched")
        print(f"  → {value_data['total_hours_saved']:.1f} hours saved, avg {value_data['average_minutes_per_event']:.1f} min/event")
    print()
    print("Outputs:")
    print(f"  • Events data: {events_path}")
    print(f"  • Summary data: {summary_path}")
    print(f"  • Dashboard: {report_path}")
    if not args.no_db:
        print(f"  • Database: {args.db_path}")
        if db:
            db_stats = db.get_stats()
            if db_stats['unenriched_events'] > 0:
                print()
                print(f"💡 Tip: {db_stats['unenriched_events']} events ready for value enrichment.")
                print(f"   Run: python -m shadowai.value_enrichment_worker")
                print(f"   Then re-run with --use-db-enrichment to see enriched data in reports.")
    print()
    print(f"Open {report_path} in your browser to view the executive dashboard.")
    print("=" * 60)


if __name__ == '__main__':
    main()
