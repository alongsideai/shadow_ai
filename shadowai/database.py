"""Database module for Shadow AI Detection Platform.

Provides SQLite-based persistence for events and value enrichment data.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from .models import AIUsageEvent


class Database:
    """SQLite database manager for Shadow AI events and enrichments."""

    def __init__(self, db_path: str = "shadowai.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file (default: shadowai.db)
        """
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_email TEXT,
                    department TEXT,
                    source_ip TEXT,
                    provider TEXT NOT NULL,
                    service TEXT NOT NULL,
                    url TEXT NOT NULL,
                    bytes_sent INTEGER,
                    bytes_received INTEGER,
                    risk_level TEXT NOT NULL,
                    risk_reasons TEXT NOT NULL,
                    source_system TEXT NOT NULL,
                    notes TEXT,
                    pii_risk INTEGER NOT NULL,
                    pii_reasons TEXT NOT NULL,
                    use_case TEXT NOT NULL,
                    value_enriched INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Value enrichment table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS value_enrichment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    value_category TEXT NOT NULL,
                    estimated_minutes_saved INTEGER NOT NULL,
                    business_outcome TEXT NOT NULL,
                    department TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    policy_alignment TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    raw_llm_response TEXT,
                    enrichment_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(id)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_value_enriched
                ON events(value_enriched)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_enrichment_event_id
                ON value_enrichment(event_id)
            """)

    def upsert_event(self, event: AIUsageEvent) -> None:
        """Insert or update an event.

        Args:
            event: AIUsageEvent instance to persist
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            now = datetime.utcnow().isoformat()

            cursor.execute("""
                INSERT INTO events (
                    id, timestamp, user_email, department, source_ip,
                    provider, service, url, bytes_sent, bytes_received,
                    risk_level, risk_reasons, source_system, notes,
                    pii_risk, pii_reasons, use_case, value_enriched,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    timestamp=excluded.timestamp,
                    user_email=excluded.user_email,
                    department=excluded.department,
                    source_ip=excluded.source_ip,
                    provider=excluded.provider,
                    service=excluded.service,
                    url=excluded.url,
                    bytes_sent=excluded.bytes_sent,
                    bytes_received=excluded.bytes_received,
                    risk_level=excluded.risk_level,
                    risk_reasons=excluded.risk_reasons,
                    notes=excluded.notes,
                    pii_risk=excluded.pii_risk,
                    pii_reasons=excluded.pii_reasons,
                    use_case=excluded.use_case,
                    updated_at=excluded.updated_at
            """, (
                event.id,
                event.timestamp.isoformat(),
                event.user_email,
                event.department,
                event.source_ip,
                event.provider,
                event.service,
                event.url,
                event.bytes_sent,
                event.bytes_received,
                event.risk_level,
                json.dumps(event.risk_reasons),
                event.source_system,
                event.notes,
                1 if event.pii_risk else 0,
                json.dumps(event.pii_reasons),
                event.use_case,
                0,  # value_enriched defaults to False
                now,
                now
            ))

    def get_unenriched_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch events that haven't been value-enriched yet.

        Args:
            limit: Maximum number of events to fetch (default: 50)

        Returns:
            List of event dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events
                WHERE value_enriched = 0
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single event by ID.

        Args:
            event_id: Event identifier

        Returns:
            Event dictionary or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_value_enrichment(
        self,
        event_id: str,
        enrichment: Dict[str, Any],
        raw_response: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """Save value enrichment for an event.

        Args:
            event_id: Event identifier
            enrichment: Parsed enrichment data
            raw_response: Raw LLM response (optional)
            error: Error message if enrichment failed (optional)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()

            # Insert or update enrichment
            cursor.execute("""
                INSERT INTO value_enrichment (
                    event_id, value_category, estimated_minutes_saved,
                    business_outcome, department, risk_level, policy_alignment,
                    summary, raw_llm_response, enrichment_error,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    value_category=excluded.value_category,
                    estimated_minutes_saved=excluded.estimated_minutes_saved,
                    business_outcome=excluded.business_outcome,
                    department=excluded.department,
                    risk_level=excluded.risk_level,
                    policy_alignment=excluded.policy_alignment,
                    summary=excluded.summary,
                    raw_llm_response=excluded.raw_llm_response,
                    enrichment_error=excluded.enrichment_error,
                    updated_at=excluded.updated_at
            """, (
                event_id,
                enrichment.get('value_category', 'Unknown'),
                enrichment.get('estimated_minutes_saved', 0),
                enrichment.get('business_outcome', ''),
                enrichment.get('department', 'Unknown'),
                enrichment.get('risk_level', 'Medium'),
                enrichment.get('policy_alignment', 'Questionable'),
                enrichment.get('summary', ''),
                raw_response,
                error,
                now,
                now
            ))

            # Mark event as enriched (only if no error)
            if not error:
                cursor.execute("""
                    UPDATE events
                    SET value_enriched = 1, updated_at = ?
                    WHERE id = ?
                """, (now, event_id))

    def get_enrichment_for_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Fetch value enrichment for a specific event.

        Args:
            event_id: Event identifier

        Returns:
            Enrichment dictionary or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM value_enrichment
                WHERE event_id = ?
            """, (event_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_enriched_events_with_value(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch events with their value enrichment data.

        Args:
            limit: Maximum number of events to fetch (optional)

        Returns:
            List of events with enrichment data joined
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    e.*,
                    v.value_category,
                    v.estimated_minutes_saved,
                    v.business_outcome,
                    v.risk_level as enriched_risk_level,
                    v.policy_alignment,
                    v.summary as value_summary
                FROM events e
                INNER JOIN value_enrichment v ON e.id = v.event_id
                WHERE e.value_enriched = 1
                ORDER BY e.timestamp DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics.

        Returns:
            Dictionary with counts of events and enrichments
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM events")
            total_events = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE value_enriched = 1")
            enriched_events = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM value_enrichment")
            total_enrichments = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM value_enrichment WHERE enrichment_error IS NOT NULL")
            failed_enrichments = cursor.fetchone()[0]

            return {
                'total_events': total_events,
                'enriched_events': enriched_events,
                'unenriched_events': total_events - enriched_events,
                'total_enrichments': total_enrichments,
                'failed_enrichments': failed_enrichments
            }

    def get_all_events_with_enrichment(self) -> List[AIUsageEvent]:
        """Load all events from database with enrichment data if available.

        Returns:
            List of AIUsageEvent objects with enrichment fields populated
        """
        events = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    e.*,
                    v.value_category,
                    v.estimated_minutes_saved,
                    v.business_outcome,
                    v.policy_alignment,
                    v.summary as value_summary
                FROM events e
                LEFT JOIN value_enrichment v ON e.id = v.event_id
                ORDER BY e.timestamp DESC
            """)
            rows = cursor.fetchall()

            for row in rows:
                row_dict = dict(row)
                # Parse JSON fields
                risk_reasons = json.loads(row_dict.get('risk_reasons', '[]'))
                pii_reasons = json.loads(row_dict.get('pii_reasons', '[]'))
                
                # Parse timestamp
                timestamp = datetime.fromisoformat(row_dict['timestamp'].replace('Z', '+00:00'))
                
                event = AIUsageEvent(
                    id=row_dict['id'],
                    timestamp=timestamp,
                    user_email=row_dict.get('user_email'),
                    department=row_dict.get('department'),
                    source_ip=row_dict.get('source_ip'),
                    provider=row_dict['provider'],
                    service=row_dict['service'],
                    url=row_dict['url'],
                    bytes_sent=row_dict.get('bytes_sent'),
                    bytes_received=row_dict.get('bytes_received'),
                    risk_level=row_dict['risk_level'],
                    risk_reasons=risk_reasons,
                    source_system=row_dict.get('source_system', 'network_logs_v1'),
                    notes=row_dict.get('notes'),
                    pii_risk=bool(row_dict.get('pii_risk', 0)),
                    pii_reasons=pii_reasons,
                    use_case=row_dict.get('use_case', 'unknown'),
                    # Enrichment fields (None if not enriched)
                    value_category=row_dict.get('value_category'),
                    estimated_minutes_saved=row_dict.get('estimated_minutes_saved'),
                    business_outcome=row_dict.get('business_outcome'),
                    policy_alignment=row_dict.get('policy_alignment'),
                    value_summary=row_dict.get('value_summary')
                )
                events.append(event)

        return events
