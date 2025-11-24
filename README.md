# Shadow AI Detection Platform

A lightweight discovery tool that helps organizations detect and analyze "Shadow AI" usage—employees using AI tools like ChatGPT, Claude, Gemini, Copilot, etc. with no IT visibility.

## Features

- **Multi-file / Multi-day Log Support**: Process single files or entire directories of daily exports
- **AI Provider Detection**: Identifies OpenAI, Anthropic, Google/Gemini, GitHub Copilot, Perplexity, and unknown AI tools
- **Security Risk Classification**: Categorizes events as low/medium/high risk based on department sensitivity and data transfer patterns
- **PII/PHI Risk Detection**: Heuristic-based detection of potential sensitive data exposure
- **Use-Case Classification**: Automatically categorizes AI usage into business-friendly categories
- **Interactive HTML Dashboard**: Exec-friendly dashboard with drill-down capabilities, filtering, and event details
- **Structured Data Export**: JSON exports for further analysis and integration

## Quick Start

### Installation

This tool uses only Python standard library (3.10+), so no external dependencies are required.

```bash
# Clone or download this repository
cd shadow_ai

# Optional: Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Usage

#### Single File Mode

Run the tool against a single CSV log file:

```bash
python -m shadowai.cli --input data/sample_logs.csv
```

#### Multi-File / Directory Mode

Process multiple log files from a directory (e.g., daily exports):

```bash
python -m shadowai.cli --input-dir data/logs_multi
```

#### Custom Output Directory

```bash
python -m shadowai.cli --input data/sample_logs.csv --output-dir results
```

### View the Dashboard

After running the tool, open the generated interactive HTML dashboard:

```bash
open output/report.html  # macOS
# or
xdg-open output/report.html  # Linux
# or just double-click the file in Windows Explorer
```

## Output Files

The tool generates three files in the output directory:

1. **`events.json`** - All detected AI usage events with full details including:
   - Basic event data (timestamp, user, department, provider, URL)
   - Security risk classification
   - PII/PHI risk flags
   - Use-case classification

2. **`summary.json`** - Aggregated metrics and insights:
   - KPIs (total events, unique users, shadow AI %, high-risk %, PII risk %)
   - Time range and per-day breakdown
   - Events by provider, department, use-case
   - Top risks with actionable recommendations

3. **`report.html`** - Interactive executive dashboard with:
   - KPI cards
   - Risk breakdown charts
   - Department usage charts
   - Event details table with filters
   - Drill-down modals for individual events

## CSV Log Format

The tool expects CSV logs with the following columns:

- `timestamp` - ISO8601 format (e.g., "2025-11-24T14:03:12Z")
- `user_email` - User's email address
- `department` - Department name
- `source_ip` - Source IP address
- `method` - HTTP method (GET, POST, etc.)
- `url` - Full URL
- `bytes_sent` - Number of bytes sent
- `bytes_received` - Number of bytes received

See `data/sample_logs.csv` or `data/logs_multi/*.csv` for examples.

## Security Risk Classification

The tool automatically classifies each AI event into three risk levels:

### HIGH RISK
- External AI usage by high-sensitivity departments (Clinical, Claims, Legal, Trading, Underwriting, Wealth Management)
- Large data transfers (>4KB) to AI providers
- Unknown/unidentified AI tools

### MEDIUM RISK
- External AI usage by medium-sensitivity departments (Finance, HR)
- External AI usage by other departments

### LOW RISK
- Other AI usage not matching above criteria

## PII/PHI Risk Detection

The platform uses heuristic rules to flag potential PII/PHI exposure. These are **indicators, not definitive classifications**.

### Detection Rules

- **Large Payloads** (≥10KB): Suggests document or record uploads
- **High-Sensitivity + Large Payload** (≥4KB): Sensitive department with substantial data transfer
- **PII Keywords in URL**: Detects keywords like `patient`, `claim`, `record`, `ssn`, `dob`, `mrn`, `medical`, `diagnosis`, `prescription`, `phi`, `pii`, `confidential`, `hipaa`
- **SSN Pattern in URL**: Matches XXX-XX-XXXX format
- **Email Pattern in URL**: Detects email addresses in URL paths or query strings

### Important Notes

- These are **heuristic flags based on network-level data only**
- We do NOT have access to request bodies or response content
- Flagged events warrant further investigation, not automatic policy enforcement
- Use PII flags as a starting point for deeper analysis

## Use-Case Classification

Each AI event is automatically categorized into business-friendly use cases:

| Use Case | Description | Example Activities |
|----------|-------------|-------------------|
| **Content Generation** | Creating or editing content through web interfaces | Documents, emails, presentations, creative writing |
| **Code Assistance** | Programming support | Code completion, debugging, refactoring (GitHub Copilot) |
| **Data Extraction** | Uploading documents/records for analysis | Large payloads (>10KB) to chat/API endpoints, embedding services |
| **Analysis / Q&A** | General question-answering and analysis | Conversational AI interactions, research queries |
| **Unknown** | Cannot determine from available data | Insufficient information or unrecognized patterns |

### Classification Logic

- GitHub Copilot → Always **Code Assistance**
- Web UI usage (chat.openai.com, claude.ai, etc.) → **Content Generation**
- Chat/API with large payloads (≥10KB) → **Data Extraction**
- Chat/API with normal payloads → **Analysis / Q&A**
- Embeddings service → **Data Extraction**

## Supported AI Providers

- **OpenAI**: api.openai.com, chat.openai.com
- **Anthropic**: api.anthropic.com, claude.ai
- **Google/Gemini**: generativelanguage.googleapis.com
- **GitHub Copilot**: api.githubcopilot.com
- **Perplexity**: perplexity.ai
- **Unknown AI Tools**: Heuristic detection based on URL patterns

## Project Structure

```
shadow_ai/
├── README.md
├── requirements.txt
├── data/
│   ├── sample_logs.csv          # Single-day example
│   └── logs_multi/               # Multi-day examples
│       ├── logs_2025-11-23.csv
│       └── logs_2025-11-24.csv
├── shadowai/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                    # CLI entrypoint (single/multi-file support)
│   ├── models.py                 # Data models (AIUsageEvent, enums)
│   ├── providers.py              # Provider detection logic
│   ├── parser.py                 # CSV parsing (single/multi-file)
│   ├── risk_rules.py             # Security risk classification
│   ├── pii.py                    # PII/PHI risk detection
│   ├── use_cases.py              # Use-case classification
│   ├── aggregator.py             # Metrics aggregation
│   └── report.py                 # JSON and HTML report generation
└── output/
    ├── events.json
    ├── summary.json
    └── report.html               # Interactive dashboard
```

## Interactive Dashboard Features

The HTML dashboard includes:

1. **KPI Cards**: Total events, unique users, shadow AI %, high-risk events
2. **Risk Breakdown Chart**: Visual distribution of low/medium/high risk events
3. **Department Usage Chart**: AI usage by department with high-risk overlay
4. **Event Details Table**: Searchable, filterable table of all AI events
5. **Drill-Down Modals**: Click any event for full details, risk explanations, and recommended actions

### Dashboard Interactions

- **Click chart segments** to filter events by risk level or department
- **Use filters** to search by risk, department, provider, or text
- **Click table rows** to open detailed event modals with:
  - Full event metadata
  - Human-readable risk factor explanations
  - Risk-specific follow-up recommendations

## Use Cases

- **Security and Compliance Teams**: Assess AI-related risk exposure
- **IT Teams**: Gain visibility into shadow AI usage patterns
- **Executives**: Understand AI adoption across the organization
- **Consultants**: Demonstrate AI governance gaps to clients
- **Risk Assessments**: Identify departments and use cases requiring governance

## Demo and Sharing

The HTML dashboard is designed to be:
- **Self-contained**: Works offline after generation (no external dependencies except Chart.js CDN)
- **Visually compelling**: Professional design suitable for executive presentations
- **Easy to share**: Single HTML file can be emailed or posted
- **Demo-ready**: Suitable for LinkedIn posts, sales demos, and client presentations

## Advanced Usage

### Multi-Day Analysis

When analyzing multiple days of logs:

```bash
# Directory should contain multiple CSV files
data/logs_multi/
  ├── logs_2025-11-23.csv
  ├── logs_2025-11-24.csv
  └── logs_2025-11-25.csv

python -m shadowai.cli --input-dir data/logs_multi
```

The tool will:
- Parse all CSV files in the directory
- Merge events from all files
- Sort by timestamp
- Calculate per-day metrics
- Show date range in dashboard

### Custom Source System Identifier

```bash
python -m shadowai.cli --input data/logs.csv --source-system "firewall_logs_v2"
```

## Limitations and Considerations

### Data Limitations
- Analysis is based on **network-level logs only**
- No access to request/response bodies
- Cannot confirm actual data sensitivity
- May miss AI usage through VPNs, proxies, or encrypted tunnels

### PII/PHI Detection
- **Heuristic-based**, not definitive
- False positives are possible (e.g., large legitimate payloads)
- False negatives are possible (e.g., small but sensitive data)
- Always investigate flagged events before taking action

### Use-Case Classification
- Based on observable patterns (provider, service type, payload size)
- May misclassify edge cases
- "Unknown" category captures ambiguous usage
- Best used as a starting point for deeper analysis

### Risk Classification
- Calibrated for typical enterprise security postures
- Adjust department sensitivity lists in `models.py` for your organization
- Thresholds (4KB, 10KB) are configurable in respective modules

## Customization

### Adjusting Department Sensitivity

Edit `shadowai/models.py`:

```python
HIGH_SENSITIVITY_DEPARTMENTS = {
    "Clinical", "Claims", "Legal", "Trading", "Underwriting",
    "Wealth Management", "YourCustomDept"
}

MEDIUM_SENSITIVITY_DEPARTMENTS = {
    "Finance", "HR", "YourOtherDept"
}
```

### Adjusting PII Detection Thresholds

Edit `shadowai/pii.py`:

```python
LARGE_PAYLOAD_THRESHOLD = 10_000  # bytes
HIGH_SENS_MODERATE_PAYLOAD_THRESHOLD = 4_096  # bytes
```

### Adjusting Use-Case Thresholds

Edit `shadowai/use_cases.py`:

```python
DATA_EXTRACTION_THRESHOLD = 10_000  # bytes
```

## Troubleshooting

### No events detected
- Verify CSV format matches expected columns
- Check that URLs contain recognizable AI provider domains
- Review `data/sample_logs.csv` for format reference

### Multi-file parsing errors
- Ensure all CSV files have consistent column headers
- Check file permissions in the input directory
- Verify CSV files are properly formatted (no corrupted rows)

### Dashboard not loading
- Ensure you have internet connectivity (for Chart.js CDN)
- Try opening in a different browser
- Check browser console for JavaScript errors

## License

This is a prototype/demo tool. Use at your own discretion.

## Support

For questions or issues, contact your organization's IT security team or open an issue on the project repository.

## Version History

### v0.2.0 (Current)
- Added multi-file / multi-day log support
- Added PII/PHI risk detection with heuristic rules
- Added use-case classification
- Enhanced aggregator with per-day metrics
- Updated dashboard with new KPI metrics

### v0.1.0 (Initial)
- Single-file CSV parsing
- Basic AI provider detection
- Security risk classification
- Interactive HTML dashboard with filtering and drill-down
