"""Utility script to seed database from existing JSON event files.

This script loads events from output/events.json and populates the database,
making them available for value enrichment.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from .database import Database
from .models import AIUsageEvent


def load_events_from_json(json_path: str) -> List[Dict[str, Any]]:
    """Load events from a JSON file.

    Args:
        json_path: Path to events.json file

    Returns:
        List of event dictionaries
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Handle both direct list and wrapped format
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and 'events' in data:
        return data['events']
    else:
        raise ValueError("Unexpected JSON format. Expected list or {'events': [...]}")


def dict_to_event(event_dict: Dict[str, Any]) -> AIUsageEvent:
    """Convert event dictionary to AIUsageEvent dataclass.

    Args:
        event_dict: Event dictionary

    Returns:
        AIUsageEvent instance
    """
    # Parse timestamp
    timestamp_str = event_dict.get('timestamp')
    if isinstance(timestamp_str, str):
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    else:
        timestamp = datetime.utcnow()

    return AIUsageEvent(
        id=event_dict['id'],
        timestamp=timestamp,
        user_email=event_dict.get('user_email'),
        department=event_dict.get('department'),
        source_ip=event_dict.get('source_ip'),
        provider=event_dict['provider'],
        service=event_dict['service'],
        url=event_dict['url'],
        bytes_sent=event_dict.get('bytes_sent'),
        bytes_received=event_dict.get('bytes_received'),
        risk_level=event_dict['risk_level'],
        risk_reasons=event_dict.get('risk_reasons', []),
        source_system=event_dict.get('source_system', 'network_logs_v1'),
        notes=event_dict.get('notes'),
        pii_risk=event_dict.get('pii_risk', False),
        pii_reasons=event_dict.get('pii_reasons', []),
        use_case=event_dict.get('use_case', 'unknown')
    )


def seed_database(
    json_path: str,
    db_path: str = "shadowai.db",
    overwrite: bool = False
) -> Dict[str, int]:
    """Seed database with events from JSON file.

    Args:
        json_path: Path to events.json file
        db_path: Path to SQLite database
        overwrite: If True, existing enrichments are preserved

    Returns:
        Dictionary with seeding statistics
    """
    print("=" * 60)
    print("Database Seeding Utility")
    print("=" * 60)
    print(f"JSON file: {json_path}")
    print(f"Database: {db_path}")
    print("=" * 60)

    # Load events from JSON
    print(f"\n[1/3] Loading events from JSON...")
    try:
        event_dicts = load_events_from_json(json_path)
        print(f"      → Loaded {len(event_dicts)} events")
    except Exception as e:
        print(f"Error: Failed to load JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize database
    print(f"\n[2/3] Initializing database...")
    db = Database(db_path)
    initial_stats = db.get_stats()
    print(f"      → Database initialized")
    print(f"      → Current stats: {initial_stats}")

    # Insert events
    print(f"\n[3/3] Inserting events into database...")
    inserted = 0
    updated = 0
    errors = 0

    for event_dict in event_dicts:
        try:
            event = dict_to_event(event_dict)
            db.upsert_event(event)

            # Check if this was an update or insert
            existing = db.get_event_by_id(event.id)
            if existing:
                if existing.get('value_enriched', 0) == 0:
                    inserted += 1
                else:
                    updated += 1
            else:
                inserted += 1

        except Exception as e:
            print(f"      ✗ Error inserting event {event_dict.get('id')}: {e}")
            errors += 1

    # Final stats
    final_stats = db.get_stats()
    print()
    print("=" * 60)
    print("Seeding Complete")
    print("=" * 60)
    print(f"Events processed: {len(event_dicts)}")
    print(f"Events inserted/updated: {inserted + updated}")
    print(f"Errors: {errors}")
    print()
    print("Database stats:")
    print(f"  Total events: {final_stats['total_events']}")
    print(f"  Enriched events: {final_stats['enriched_events']}")
    print(f"  Unenriched events: {final_stats['unenriched_events']}")
    print("=" * 60)

    return {
        'events_loaded': len(event_dicts),
        'events_inserted': inserted,
        'events_updated': updated,
        'errors': errors
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed database from events JSON file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed from default location
  python -m shadowai.seed_database

  # Seed from custom JSON file
  python -m shadowai.seed_database --input output/events.json

  # Use custom database path
  python -m shadowai.seed_database --db-path /path/to/shadowai.db
        """
    )

    parser.add_argument(
        '--input',
        default='output/events.json',
        help='Path to events JSON file (default: output/events.json)'
    )

    parser.add_argument(
        '--db-path',
        default='shadowai.db',
        help='Path to SQLite database (default: shadowai.db)'
    )

    args = parser.parse_args()

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        print("\nTip: Run the main CLI first to generate events.json:")
        print("  python -m shadowai.cli --input data/sample_logs.csv")
        sys.exit(1)

    # Seed database
    try:
        seed_database(str(input_path), args.db_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
