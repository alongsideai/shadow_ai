# Value Enrichment Feature

## Overview

The Value Enrichment feature adds a **business value lens** to Shadow AI detection events using OpenAI's GPT-4o-mini model. For each detected AI usage event, the system classifies:

- **Value Category**: Productivity, Quality, Revenue, Cost Reduction, or Innovation
- **Estimated Time Savings**: Minutes saved per event
- **Business Outcome**: Short description of the likely business impact
- **Department**: Inferred from metadata or content
- **Risk Assessment**: Governance risk level and policy alignment
- **Summary**: Plain-language explanation of value and risk

This enrichment runs **asynchronously** and does not block event ingestion.

---

## Architecture

### Components

1. **Database Layer** (`shadowai/database.py`)
   - SQLite-based persistence for events and enrichments
   - `events` table: Stores raw AI usage events
   - `value_enrichment` table: Stores LLM-generated value insights
   - Indexed for efficient queries

2. **Enrichment Service** (`shadowai/value_enrichment_service.py`)
   - Builds enrichment payloads from events
   - Calls OpenAI GPT-4o-mini API
   - Parses and validates JSON responses
   - Includes retry logic with exponential backoff

3. **Worker Process** (`shadowai/value_enrichment_worker.py`)
   - Long-running background service
   - Fetches unenriched events in batches
   - Calls enrichment service for each event
   - Persists results to database
   - Idempotent (skips already-enriched events)

4. **Seeding Utility** (`shadowai/seed_database.py`)
   - Loads events from existing JSON files into database
   - Makes events available for enrichment

---

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs `openai>=1.0.0` (the only new dependency).

### 2. Set OpenAI API Key

The worker requires an OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Or create a `.env` file:

```
OPENAI_API_KEY=sk-...
```

### 3. Generate Events (if needed)

If you don't have events in the database yet:

```bash
# Parse logs to generate events.json
python -m shadowai.cli --input data/sample_logs.csv

# Seed database from events.json
python -m shadowai.seed_database --input output/events.json
```

---

## Usage

### Running the Worker

**Continuous Mode** (recommended for production):

```bash
python -m shadowai.value_enrichment_worker
```

The worker will:
- Process 50 events per batch (default)
- Sleep 10 seconds between batches
- Run indefinitely until stopped (Ctrl+C)

**Single Iteration** (useful for testing):

```bash
python -m shadowai.value_enrichment_worker --once
```

**Custom Configuration**:

```bash
# Custom batch size and sleep interval
python -m shadowai.value_enrichment_worker --batch-size 100 --sleep 30

# Custom database path
python -m shadowai.value_enrichment_worker --db-path /path/to/shadowai.db

# Verbose logging
python -m shadowai.value_enrichment_worker --verbose
```

### Checking Status

```python
from shadowai.database import Database

db = Database("shadowai.db")
stats = db.get_stats()

print(stats)
# Output:
# {
#     'total_events': 100,
#     'enriched_events': 75,
#     'unenriched_events': 25,
#     'total_enrichments': 75,
#     'failed_enrichments': 2
# }
```

### Retrieving Enriched Data

```python
from shadowai.database import Database

db = Database("shadowai.db")

# Get all enriched events with value data
enriched = db.get_enriched_events_with_value(limit=10)

for event in enriched:
    print(f"Event {event['id']}:")
    print(f"  Value: {event['value_category']}")
    print(f"  Time saved: {event['estimated_minutes_saved']} min")
    print(f"  Outcome: {event['business_outcome']}")
    print(f"  Risk: {event['enriched_risk_level']}")
    print(f"  Policy: {event['policy_alignment']}")
    print()
```

---

## Enrichment Schema

Each event is enriched with the following structured data:

```json
{
  "value_category": "Productivity | Quality | Revenue | CostReduction | Innovation",
  "estimated_minutes_saved": 5,
  "business_outcome": "Faster drafting of outbound sales email",
  "department": "Sales",
  "risk_level": "Low",
  "policy_alignment": "Compliant",
  "summary": "User drafted a sales email using ChatGPT, saving ~5 minutes. Low risk as no sensitive data appears involved."
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `value_category` | String | **Productivity**: drafting, summarizing, translation<br>**Quality**: error reduction, clarity, decision support<br>**Revenue**: sales, proposals, customer content<br>**CostReduction**: automation, vendor replacement<br>**Innovation**: new ideas, prototypes, concepts |
| `estimated_minutes_saved` | Integer | Estimated time saved (0 if not applicable) |
| `business_outcome` | String | Short description of business impact |
| `department` | String | Inferred department (or "Unknown") |
| `risk_level` | String | Low, Medium, or High |
| `policy_alignment` | String | **Compliant**: approved tools, no sensitive data<br>**Questionable**: ambiguous compliance<br>**LikelyViolation**: clear policy breach patterns |
| `summary` | String | 1-2 sentence plain-language explanation |

---

## Database Schema

### `events` Table

Stores raw AI usage events:

```sql
CREATE TABLE events (
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
    risk_reasons TEXT NOT NULL,  -- JSON array
    source_system TEXT NOT NULL,
    notes TEXT,
    pii_risk INTEGER NOT NULL,
    pii_reasons TEXT NOT NULL,  -- JSON array
    use_case TEXT NOT NULL,
    value_enriched INTEGER DEFAULT 0,  -- Flag: 0 = unenriched, 1 = enriched
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### `value_enrichment` Table

Stores LLM-generated value insights:

```sql
CREATE TABLE value_enrichment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    value_category TEXT NOT NULL,
    estimated_minutes_saved INTEGER NOT NULL,
    business_outcome TEXT NOT NULL,
    department TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    policy_alignment TEXT NOT NULL,
    summary TEXT NOT NULL,
    raw_llm_response TEXT,  -- Full JSON response from LLM
    enrichment_error TEXT,  -- Error message if enrichment failed
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id)
);
```

---

## Integration with Reports

### Current Integration

The enrichment data is stored in a separate table and can be joined with events for reporting:

```python
from shadowai.database import Database

db = Database("shadowai.db")

# Get enriched events
enriched_events = db.get_enriched_events_with_value()

# Calculate value metrics
total_minutes_saved = sum(e['estimated_minutes_saved'] for e in enriched_events)
total_hours_saved = total_minutes_saved / 60

productivity_count = sum(1 for e in enriched_events if e['value_category'] == 'Productivity')

print(f"Total time saved: {total_hours_saved:.1f} hours")
print(f"Productivity events: {productivity_count}")
```

### Future Enhancement Ideas

To display enrichment in the HTML dashboard (`shadowai/report.py`):

1. **Value KPI Cards**:
   - Total hours saved
   - Events by value category
   - Average minutes per event

2. **Enhanced Event Table**:
   - Add "Value" column showing category
   - Add "Time Saved" column
   - Filter by value category

3. **Value Distribution Chart**:
   - Pie chart of events by value category
   - Bar chart of time saved by department

4. **ROI Calculations**:
   - Assume average hourly rate (e.g., $50/hour)
   - Calculate total value: `hours_saved * hourly_rate`

---

## Performance & Cost

### OpenAI API Costs

**Model**: GPT-4o-mini (cheapest GPT-4o tier)

**Estimated Costs** (as of Nov 2024):
- Input: ~$0.15 per 1M tokens
- Output: ~$0.60 per 1M tokens

**Per Event**:
- Input: ~300 tokens (event metadata)
- Output: ~150 tokens (JSON response)
- **Cost per event**: ~$0.0001 (approximately $0.10 per 1,000 events)

For 10,000 events/month: **~$1.00/month**

### Rate Limits

The worker includes:
- Built-in retry logic with exponential backoff
- 0.5 second delay between events
- Configurable batch sizes

At default settings (50 events/batch, 10s sleep):
- **~180 events/hour**
- **~4,320 events/day**

Adjust `--batch-size` and `--sleep` parameters to increase/decrease throughput.

---

## Error Handling

### Retry Logic

The enrichment service retries failed requests up to 3 times with exponential backoff:

1. First attempt: immediate
2. Second attempt: 1 second delay
3. Third attempt: 2 second delay

### Error Types

| Error Type | Handling |
|------------|----------|
| Rate limit exceeded | Extended backoff (4-8 seconds) |
| API timeout | Retry with exponential backoff |
| JSON parse error | Log raw response, retry |
| Missing fields | Log warning, retry |
| Unknown error | Log with stack trace, skip event |

### Failed Enrichments

Events that fail after max retries are marked with:
- `enrichment_error` field populated with error message
- `value_enriched` remains 0 (can be retried later)
- Partial enrichment data saved (with safe defaults)

---

## Troubleshooting

### Worker won't start

**Error**: `ValueError: OpenAI API key not found`

**Solution**: Set the `OPENAI_API_KEY` environment variable:
```bash
export OPENAI_API_KEY="sk-..."
```

### No events to process

**Error**: Worker logs "No events to process"

**Solution**: Seed the database first:
```bash
python -m shadowai.seed_database --input output/events.json
```

### Import error for openai

**Error**: `ImportError: openai package not found`

**Solution**: Install dependencies:
```bash
pip install -r requirements.txt
```

### Rate limit errors

**Error**: Worker logs "OpenAI rate limit exceeded"

**Solutions**:
- Increase sleep interval: `--sleep 30`
- Decrease batch size: `--batch-size 25`
- Check your OpenAI tier limits

---

## Development

### Running Tests

```bash
# Test single event enrichment
python -c "
from shadowai.value_enrichment_service import create_enrichment_service
from shadowai.database import Database

db = Database('shadowai.db')
events = db.get_unenriched_events(limit=1)

if events:
    service = create_enrichment_service()
    enrichment, raw, error = service.enrich_event(events[0])
    print('Enrichment:', enrichment)
    print('Error:', error)
else:
    print('No events found')
"
```

### Inspecting Database

```bash
# SQLite CLI
sqlite3 shadowai.db

# Show tables
.tables

# Show enrichments
SELECT event_id, value_category, estimated_minutes_saved, business_outcome
FROM value_enrichment
LIMIT 10;

# Show unenriched events
SELECT id, timestamp, provider, department
FROM events
WHERE value_enriched = 0
LIMIT 10;
```

---

## Future Enhancements

### Batch Processing

Currently, the worker processes events one-by-one. Future optimization:

```python
# Process multiple events in a single API call
# (requires modifying the LLM prompt to handle arrays)
enrichments = service.enrich_events_batch(events)
```

### Caching

Cache enrichments for similar events to reduce API calls:

```python
# Hash event metadata to create cache key
cache_key = hash_event_signature(event)
if cache_key in enrichment_cache:
    return enrichment_cache[cache_key]
```

### Custom Prompts

Allow users to customize the system prompt for domain-specific classification:

```python
service = ValueEnrichmentService(
    custom_prompt="Your custom industry-specific prompt..."
)
```

### Real-time Enrichment

Integrate enrichment into the ingestion pipeline for near-real-time classification:

```python
# In cli.py after risk classification
if config.get('enable_value_enrichment'):
    enrich_events_inline(events)
```

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review worker logs for error messages
3. Inspect database with SQLite CLI
4. Verify OpenAI API key is valid

---

## Example Enriched Event

Here's a complete example of an event with enrichment:

```json
{
  "id": "evt_20240324_001",
  "timestamp": "2024-03-24T14:23:45Z",
  "user_email": "jane.doe@company.com",
  "department": "Sales",
  "provider": "openai",
  "service": "chat",
  "risk_level": "low",
  "pii_risk": false,
  "use_case": "content_generation",

  // Value enrichment data:
  "value_category": "Revenue",
  "estimated_minutes_saved": 7,
  "business_outcome": "Faster drafting of customer proposal email",
  "enriched_risk_level": "Low",
  "policy_alignment": "Compliant",
  "value_summary": "Sales team member used ChatGPT to draft a customer proposal, saving approximately 7 minutes. Low risk as no sensitive customer data was included in the prompt."
}
```
