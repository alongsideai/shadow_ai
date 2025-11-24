"""Value enrichment worker for Shadow AI Detection Platform.

This worker:
1. Periodically fetches unenriched events from the database
2. Calls OpenAI GPT-4o-mini to classify value and risk
3. Stores enrichment results
4. Runs continuously as a background service
"""

import sys
import time
import logging
import argparse
from pathlib import Path
from typing import Optional

from .database import Database
from .value_enrichment_service import ValueEnrichmentService, create_enrichment_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValueEnrichmentWorker:
    """Worker that enriches AI usage events with business value insights."""

    def __init__(
        self,
        db_path: str = "shadowai.db",
        batch_size: int = 50,
        sleep_interval: int = 10,
        max_errors_per_event: int = 3
    ):
        """Initialize the worker.

        Args:
            db_path: Path to SQLite database
            batch_size: Number of events to process per batch
            sleep_interval: Seconds to sleep between batches
            max_errors_per_event: Max retry attempts per event
        """
        self.db = Database(db_path)
        self.batch_size = batch_size
        self.sleep_interval = sleep_interval
        self.max_errors_per_event = max_errors_per_event
        self.enrichment_service: Optional[ValueEnrichmentService] = None

        # Statistics
        self.stats = {
            'events_processed': 0,
            'events_enriched': 0,
            'events_failed': 0,
            'batches_processed': 0
        }

    def initialize_service(self):
        """Initialize the enrichment service (lazy loading)."""
        if self.enrichment_service is None:
            try:
                self.enrichment_service = create_enrichment_service()
                logger.info("Enrichment service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize enrichment service: {e}")
                raise

    def process_event(self, event: dict) -> bool:
        """Process a single event for enrichment.

        Args:
            event: Event dictionary from database

        Returns:
            True if successfully enriched, False otherwise
        """
        event_id = event['id']

        try:
            logger.info(f"Processing event {event_id}")

            # Enrich the event
            enrichment, raw_response, error = self.enrichment_service.enrich_event(event)

            if enrichment and not error:
                # Success - save enrichment
                self.db.save_value_enrichment(
                    event_id=event_id,
                    enrichment=enrichment,
                    raw_response=raw_response
                )
                logger.info(
                    f"✓ Enriched event {event_id}: "
                    f"{enrichment.get('value_category')} - "
                    f"{enrichment.get('estimated_minutes_saved')} min saved"
                )
                self.stats['events_enriched'] += 1
                return True

            else:
                # Error - save partial enrichment with error
                partial_enrichment = enrichment or {
                    'value_category': 'Unknown',
                    'estimated_minutes_saved': 0,
                    'business_outcome': '',
                    'department': 'Unknown',
                    'risk_level': 'Medium',
                    'policy_alignment': 'Questionable',
                    'summary': 'Enrichment failed'
                }

                self.db.save_value_enrichment(
                    event_id=event_id,
                    enrichment=partial_enrichment,
                    raw_response=raw_response,
                    error=error
                )
                logger.warning(f"✗ Failed to enrich event {event_id}: {error}")
                self.stats['events_failed'] += 1
                return False

        except Exception as e:
            logger.error(f"Error processing event {event_id}: {e}", exc_info=True)
            self.stats['events_failed'] += 1
            return False

    def process_batch(self) -> int:
        """Process a batch of unenriched events.

        Returns:
            Number of events processed in this batch
        """
        # Fetch unenriched events
        events = self.db.get_unenriched_events(limit=self.batch_size)

        if not events:
            logger.debug("No unenriched events found")
            return 0

        logger.info(f"Found {len(events)} unenriched events to process")

        # Process each event
        for event in events:
            self.process_event(event)
            self.stats['events_processed'] += 1

            # Small delay between events to avoid rate limits
            time.sleep(0.5)

        self.stats['batches_processed'] += 1
        return len(events)

    def run_once(self):
        """Run one iteration of the worker (useful for testing)."""
        logger.info("Running value enrichment worker (single iteration)")

        self.initialize_service()

        # Show initial stats
        stats = self.db.get_stats()
        logger.info(f"Database stats: {stats}")

        # Process one batch
        processed = self.process_batch()

        # Show final stats
        logger.info(f"Processed {processed} events in this iteration")
        logger.info(f"Worker stats: {self.stats}")

    def run(self):
        """Run the worker continuously."""
        logger.info("=" * 60)
        logger.info("Value Enrichment Worker Starting")
        logger.info("=" * 60)
        logger.info(f"Database: {self.db.db_path}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Sleep interval: {self.sleep_interval}s")
        logger.info("=" * 60)

        # Initialize service
        self.initialize_service()

        # Show initial stats
        stats = self.db.get_stats()
        logger.info(f"Initial database stats: {stats}")

        try:
            while True:
                try:
                    # Process batch
                    processed = self.process_batch()

                    if processed == 0:
                        logger.info(
                            f"No events to process. "
                            f"Sleeping for {self.sleep_interval}s..."
                        )
                    else:
                        logger.info(
                            f"Batch complete. Processed {processed} events. "
                            f"Sleeping for {self.sleep_interval}s..."
                        )

                    # Show progress stats periodically
                    if self.stats['batches_processed'] % 10 == 0:
                        logger.info(f"Worker stats: {self.stats}")
                        db_stats = self.db.get_stats()
                        logger.info(f"Database stats: {db_stats}")

                    # Sleep before next batch
                    time.sleep(self.sleep_interval)

                except KeyboardInterrupt:
                    raise  # Re-raise to handle in outer try

                except Exception as e:
                    logger.error(f"Error in worker loop: {e}", exc_info=True)
                    logger.info(f"Waiting {self.sleep_interval}s before retry...")
                    time.sleep(self.sleep_interval)

        except KeyboardInterrupt:
            logger.info("\nShutting down worker (Ctrl+C received)...")
            logger.info("=" * 60)
            logger.info("Final Statistics")
            logger.info("=" * 60)
            logger.info(f"Events processed: {self.stats['events_processed']}")
            logger.info(f"Events enriched: {self.stats['events_enriched']}")
            logger.info(f"Events failed: {self.stats['events_failed']}")
            logger.info(f"Batches processed: {self.stats['batches_processed']}")
            logger.info("=" * 60)


def main():
    """Main entry point for the worker."""
    parser = argparse.ArgumentParser(
        description="Value Enrichment Worker for Shadow AI Detection Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run continuously
  python -m shadowai.value_enrichment_worker

  # Run with custom database
  python -m shadowai.value_enrichment_worker --db-path /path/to/shadowai.db

  # Run once (for testing)
  python -m shadowai.value_enrichment_worker --once

  # Custom batch size and interval
  python -m shadowai.value_enrichment_worker --batch-size 100 --sleep 30
        """
    )

    parser.add_argument(
        '--db-path',
        default='shadowai.db',
        help='Path to SQLite database (default: shadowai.db)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Number of events to process per batch (default: 50)'
    )

    parser.add_argument(
        '--sleep',
        type=int,
        default=10,
        help='Seconds to sleep between batches (default: 10)'
    )

    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (useful for testing)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create and run worker
    try:
        worker = ValueEnrichmentWorker(
            db_path=args.db_path,
            batch_size=args.batch_size,
            sleep_interval=args.sleep
        )

        if args.once:
            worker.run_once()
        else:
            worker.run()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
