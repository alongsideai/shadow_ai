# Interactive Dashboard Features

## Overview
The `report.html` has been extended into a fully interactive dashboard with event drilling, filtering, and detail views.

## Key Features Implemented

### 1. Event Data Embedding
- All AIUsageEvent objects are serialized to JSON and embedded in the HTML
- Data is available via `window.SHADOW_AI_EVENTS` and `window.SHADOW_AI_SUMMARY`
- Events include full details: timestamp, user, department, provider, risk level, etc.

### 2. Event Table Section
Located below the charts, includes:
- **Columns**: Time, User, Department, Provider, Risk, Summary
- **Summary column**: Auto-generated human-readable descriptions like:
  - "Clinical user sarah.chen@company.com used OpenAI chat (5.7 KB sent) – High Risk"

### 3. Interactive Filters
Four filter controls that update the table in real-time:

- **Risk Level**: All, High, Medium, Low (dropdown)
- **Department**: All departments + specific selection (dropdown, dynamically populated)
- **Provider**: All providers + specific selection (dropdown, dynamically populated)
- **Text Search**: Case-insensitive search across user email, department, provider, and URL

### 4. Chart Interactivity
Click-to-filter functionality:

- **Risk Breakdown Chart (Donut)**: Click a segment (Low/Medium/High) to filter events by that risk level
- **Department Chart (Bar)**: Click a bar to filter events by that department
- Both automatically scroll to the Event Details section after filtering

### 5. Event Detail Modal
Click any table row to open a detailed modal with:

- Full event metadata (timestamp, user, department, provider, service, URL)
- Data transfer details (bytes sent/received)
- Color-coded risk badge
- **Risk Factors**: Human-readable explanations for each risk reason:
  - "Department is classified as high-sensitivity..."
  - "Large payload suggests full documents or records..."
  - "This is an unknown AI provider..."
- **Recommended Follow-up**: Risk-specific action items (2-3 bullets)
  - High risk: "Confirm whether sensitive/regulated data is being shared"
  - Medium risk: "Review usage with the team and align with policy"
  - Low risk: "Consider adding this to the sanctioned toolkit"

Modal can be closed by:
- Clicking the X button
- Clicking outside the modal content area

### 6. Responsive Design
- Mobile-friendly layouts
- Filters stack vertically on small screens
- Table remains readable with adjusted font sizes
- Modal adapts to viewport size

## JavaScript Functions

### Core Functions
- `initializeFilters()` - Populates filter dropdowns from event data
- `filterEvents()` - Applies all active filters to event list
- `renderTable()` - Renders up to 50 filtered events in the table
- `formatTime()` - Formats timestamps for display (HH:MM)
- `generateEventSummary()` - Creates readable event summaries

### Modal Functions
- `showEventModal(eventId)` - Displays detailed event information
- `closeModal()` - Hides the modal
- `getFollowUpRecommendations(riskLevel)` - Generates risk-specific guidance
- `truncateUrl(url, maxLength)` - Truncates long URLs

### Event Handlers
- Filter change listeners (risk, department, provider, search)
- Chart click handlers (risk chart, department chart)
- Modal close handlers (button, overlay click)

## User Workflow Examples

### Example 1: Drill into High-Risk Events
1. Click "High Risk" segment on the Risk Breakdown chart
2. Automatically scrolls to Event Details section
3. Table shows only high-risk events (8 events)
4. Click any row to see full details and recommended actions

### Example 2: Investigate Clinical Department Usage
1. Click "Clinical" bar on the Department chart
2. Table filters to show 3 Clinical department events
3. See all are high-risk (sensitive department + large transfers)
4. Click an event to review specifics and get follow-up guidance

### Example 3: Search for Specific User
1. Type "sarah.chen" in the Search box
2. Table instantly filters to show 1 matching event
3. Click to see full details about Sarah's OpenAI usage

### Example 4: Find Unknown AI Tools
1. Select "Unknown" from Provider dropdown
2. Table shows 2 events using unidentified AI services
3. Review details to assess risk and plan governance actions

## Styling Highlights

- **Risk Badges**: Color-coded (red/amber/green) with consistent styling
- **Hover States**: Table rows highlight on hover to indicate clickability
- **Modal Overlay**: Semi-transparent dark background focuses attention
- **Filter Bar**: Clean, organized layout with labeled inputs
- **Responsive Grid**: Adapts to different screen sizes automatically

## Performance Notes

- Table limited to 50 rows for optimal performance
- All filtering happens client-side (no server calls)
- Event data embedded once at generation time
- Smooth scrolling and transitions for better UX

## File Size
- Original report.html: 14 KB
- Interactive report.html: 45 KB (includes all event data + JavaScript)
- Still easily shareable and loads instantly
