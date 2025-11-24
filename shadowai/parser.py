"""CSV log parser for Shadow AI Detection Platform."""

import csv
import hashlib
from datetime import datetime
from typing import List, Optional
from pathlib import Path
from .models import AIUsageEvent
from .providers import detect_provider_and_service, is_ai_related


def parse_csv_file(file_path: str, source_system: str = "network_logs_v1") -> List[AIUsageEvent]:
    """
    Parse a single CSV file and extract AI usage events.

    Args:
        file_path: Path to the CSV log file
        source_system: Identifier for the source system

    Returns:
        List of AIUsageEvent objects for AI-related requests
    """
    return _parse_csv_file_internal(file_path, source_system)


def parse_multiple_csv_files(file_paths: List[str], source_system: str = "network_logs_v1") -> List[AIUsageEvent]:
    """
    Parse multiple CSV files and merge events.

    Args:
        file_paths: List of paths to CSV log files
        source_system: Identifier for the source system

    Returns:
        List of AIUsageEvent objects merged from all files, sorted by timestamp
    """
    all_events = []

    for file_path in file_paths:
        events = _parse_csv_file_internal(file_path, source_system)
        all_events.extend(events)

    # Sort by timestamp ascending
    all_events.sort(key=lambda e: e.timestamp)

    return all_events


def parse_csv_logs(file_path: str, source_system: str = "network_logs_v1") -> List[AIUsageEvent]:
    """
    Parse network logs from CSV file and extract AI usage events.
    (Wrapper for backward compatibility)

    Args:
        file_path: Path to the CSV log file
        source_system: Identifier for the source system

    Returns:
        List of AIUsageEvent objects for AI-related requests
    """
    return _parse_csv_file_internal(file_path, source_system)


def _parse_csv_file_internal(file_path: str, source_system: str = "network_logs_v1") -> List[AIUsageEvent]:
    """
    Internal function to parse a single CSV file.

    Expected CSV columns:
    - timestamp: ISO8601 format (e.g., "2025-11-24T14:03:12Z")
    - user_email: User's email address
    - department: Department name
    - source_ip: Source IP address
    - method: HTTP method (GET, POST, etc.)
    - url: Full URL
    - bytes_sent: Number of bytes sent
    - bytes_received: Number of bytes received

    Args:
        file_path: Path to the CSV log file
        source_system: Identifier for the source system

    Returns:
        List of AIUsageEvent objects for AI-related requests
    """
    events = []

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=1):
            try:
                # Only process AI-related URLs
                url = row.get('url', '').strip()
                if not url or not is_ai_related(url):
                    continue

                # Parse timestamp
                timestamp_str = row.get('timestamp', '').strip()
                timestamp = _parse_timestamp(timestamp_str)

                # Detect provider and service
                provider, service = detect_provider_and_service(url)

                # Parse numeric fields
                bytes_sent = _parse_int(row.get('bytes_sent'))
                bytes_received = _parse_int(row.get('bytes_received'))

                # Generate unique ID based on content
                event_id = _generate_event_id(row, row_num)

                # Create event (risk classification happens later)
                event = AIUsageEvent(
                    id=event_id,
                    timestamp=timestamp,
                    user_email=row.get('user_email', '').strip() or None,
                    department=row.get('department', '').strip() or None,
                    source_ip=row.get('source_ip', '').strip() or None,
                    provider=provider,
                    service=service,
                    url=url,
                    bytes_sent=bytes_sent,
                    bytes_received=bytes_received,
                    risk_level="low",  # Will be updated by risk classifier
                    risk_reasons=[],
                    source_system=source_system,
                    notes=None
                )

                events.append(event)

            except Exception as e:
                print(f"Warning: Failed to parse row {row_num}: {e}")
                continue

    return events


def _parse_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO8601 timestamp string."""
    if not timestamp_str:
        return datetime.now()

    # Try common ISO8601 formats
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue

    # If all formats fail, try fromisoformat
    try:
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError:
        print(f"Warning: Could not parse timestamp '{timestamp_str}', using current time")
        return datetime.now()


def _parse_int(value: Optional[str]) -> Optional[int]:
    """Parse string to int, return None if invalid."""
    if not value:
        return None
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return None


def _generate_event_id(row: dict, row_num: int) -> str:
    """Generate a unique event ID based on row content."""
    # Create a hash of key fields to generate a stable ID
    content = f"{row.get('timestamp', '')}-{row.get('user_email', '')}-{row.get('url', '')}-{row_num}"
    hash_obj = hashlib.md5(content.encode('utf-8'))
    return f"evt_{hash_obj.hexdigest()[:12]}"
