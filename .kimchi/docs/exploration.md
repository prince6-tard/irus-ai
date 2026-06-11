# IRUS AI Outreach Pipeline - Codebase Exploration Summary

## Overview
The IRUS AI Outreach Pipeline is a system designed to automate lead discovery, enrichment, email drafting, and outreach for defence and medical sectors. It consists of a Python backend (FastAPI) and a Next.js frontend dashboard.

## 1. Backend Data Models and Storage

### backend/config.py
**Purpose**: Central configuration file containing tunable parameters, file paths, and constants for the pipeline.

**Key Data Structures**:
- Job title lists: `DEFENCE_JOB_TITLES`, `MEDICAL_JOB_TITLES`
- Industry lists: `DEFENCE_INDUSTRIES`, `MEDICAL_INDUSTRIES`
- Volume limits: `MAX_DEFENCE_LEADS`, `MAX_MEDICAL_LEADS`, `APOLLO_PER_PAGE`
- Model settings: `XAI_MODEL`, `XAI_MAX_TOKENS`
- File paths: `LEADS_RAW_FILE`, `LEADS_ENRICHED_FILE`, `LOG_FILE`, `EMAIL_DRAFTS_FILE`, `PRODUCTS_FILE`
- Behavioral flags: `ENRICH_WITH_HUNTER`, `DRY_RUN`, `REVIEW_BEFORE_SEND`, `DELAY_MIN_SECONDS`, `DELAY_MAX_SECONDS`, `MAX_SENDS_PER_RUN`

**Important Functions**: None (configuration constants only)

**File Paths**: Defines paths for all CSV files used in the pipeline.

### backend/email_drafts.py
**Purpose**: Manages storage and retrieval of AI-drafted emails for manual review before sending.

**Key Data Structures** (CSV columns in email_drafts.csv):
- `timestamp`: ISO format timestamp
- `email`: Recipient email address
- `name`: Recipient name
- `organization`: Organization name
- `subject`: Email subject line
- `body`: Email body content
- `status`: Draft status (`drafted`, `edited`, `sent`, `failed`)
- `lead_json`: JSON string of the original lead data

**Important Functions**:
- `get_all_drafts(status=None)`: Retrieve all drafts with optional status filter
- `get_draft(email)`: Get single draft by email address
- `save_draft(lead, subject, body, status="drafted")`: Append new draft to CSV
- `update_draft(email, subject=None, body=None)`: Update draft content, sets status to 'edited'
- `mark_sent(email)` / `mark_failed(email)`: Update draft status
- `clear_drafts()`: Delete drafts file (used between campaigns)
- `get_sendable_drafts()`: Get drafts ready to send (status=drafted or edited)

**File Paths**: Reads/writes to `EMAIL_DRAFTS_FILE` (defined in config.py)

### backend/lead_enricher.py
**Purpose**: Enriches raw leads with verified email addresses using Hunter.io API.

**Key Data Structures** (CSV columns in leads_enriched.csv):
- All columns from leads_raw.csv plus:
- `email_source`: Source of email (`apollo`, `hunter`, `none`)
- `has_phone`: Boolean string indicating if phone exists
- `notes`: Enrichment notes/status

**Important Functions**:
- `_hunter_get(url, params)`: GET request to Hunter API with rate-limit handling
- `_domain_search(domain)`: Hunter Domain Search for email discovery
- `_email_finder(domain, first_name, last_name)`: Hunter Email Finder
- `_enrich_single(lead)`: Enrich one lead with Hunter.io if needed
- `enrich_leads()`: Main function - reads leads_raw.csv, enriches, writes leads_enriched.csv

**File Paths**: 
- Reads: `LEADS_RAW_FILE` 
- Writes: `LEADS_ENRICHED_FILE`

### backend/lead_finder.py
**Purpose**: Discovers leads using Serper Places API and Hunter.io (alternative to Apollo).

**Key Data Structures** (CSV columns in leads_raw.csv):
- `name`: Organization/contact name
- `email`: Email address
- `phone`: Phone number
- `organization`: Organization name
- `organization_domain`: Domain extracted from website
- `role`: Job title/position
- `category`: "Defence" or "Medical"
- `linkedin_url`: (Currently empty)
- `city`: City location
- `country`: Country (always "India")
- `apollo_id`: Fake ID for deduplication
- `source`: Lead source (`scraped` or `hunter`)

**Important Functions**:
- `_serper_search(query, gl, hl)`: Search organizations via Serper Places API
- `_extract_city(address)`: Extract city from address string
- `_scrape_website(website)`: Scrape contact page for phones/emails
- `_get_domain(website)`: Extract clean domain from URL
- `_hunter_domain_search(domain)`: Hunter Domain Search for management emails
- `_build_search_queries(domain, location)`: Build Serper queries based on domain/location
- `_append_to_csv(leads)`: Append leads to leads_raw.csv
- `find_leads(domain, locations)`: Main function - discover leads via Serper/Hunter

**File Paths**: 
- Reads: None (discovers new leads)
- Writes: `LEADS_RAW_FILE` (via `_append_to_csv`)

### backend/logger.py
**Purpose**: Handles logging and deduplication for pipeline actions.

**Key Data Structures** (CSV columns in log.csv):
- `timestamp`: ISO format timestamp
- `email`: Recipient email address
- `name`: Recipient name
- `organization`: Organization name
- `status`: Action status (`sent`, `dry_run`, `skipped_no_email`, `skipped_already_sent`, `error_draft`, `error_send`)
- `subject`: Email subject line (if applicable)
- `note`: Free-form note/error message
- `apollo_id`: Apollo ID for deduplication

**Important Functions**:
- `already_contacted(email)`: Check if email already exists in log (deduplication)
- `write_log(lead, status, subject="", note="")`: Append action to log.csv
- `print_summary()`: Print aggregate metrics from log.csv

**File Paths**: 
- Reads: `LOG_FILE` (for deduplication and summary)
- Writes: `LOG_FILE` (logging actions)

### backend/api.py
**Purpose**: FastAPI application bridging Next.js frontend with Python orchestration engine.

**Key Data Structures**: 
- In-memory status tracker: `_campaign_status` (running state and last result)

**Important Endpoints**:
- `GET /products`: Return product catalogue JSON
- `POST /launch`: Start campaign with payload (domain, locations, selected_products, dry_run)
- `GET /drafts`: Get all drafts (optional status filter)
- `GET /drafts/pending`: Get drafts ready to send
- `PUT /drafts/{email}`: Update draft content
- `POST /drafts/{email}/send`: Send single drafted email
- `POST /drafts/send-all`: Send all pending drafts
- `GET /logs`: Get log entries (with limit)
- `GET /status`: Get campaign running status and last result

**File Paths**: 
- Reads: Various backend modules (no direct file reads)
- Writes: None directly (delegates to backend modules)

### backend/main.py
**Purpose**: Master orchestrator executing the full pipeline: discovery → enrichment → drafting → storage → sending.

**Key Data Structures**: 
- Uses lead dictionaries with fields matching CSV columns
- Campaign results dictionary with counts and status

**Important Functions**:
- `run_campaign(payload)`: Main pipeline executor (discovery → enrichment → drafting)
  - Payload keys: domain, locations, selected_products, dry_run, review_before_send
  - Returns: Summary dict with status, counts, leads processed
- `send_single(email)`: Send single drafted email after review
- `send_all()`: Send all pending drafted emails

**File Paths**: 
- Reads: All CSV files through backend modules
- Writes: All CSV files through backend modules

### backend/email_sender.py
**Purpose**: Sends emails via Gmail SMTP with SSL and retry logic.

**Key Data Structures**: 
- Uses environment variables: `GMAIL_USER`, `GMAIL_APP_PASS`, `FROM_NAME`
- SMTP constants: `SMTP_HOST`, `SMTP_PORT`

**Important Functions**:
- `send_email(to_email, to_name, subject, body)`: Send email via Gmail SMTP with one retry

**File Paths**: 
- Reads: None (uses environment variables and SMTP)
- Writes: None (sends via network)

### backend/claude_drafter.py
**Purpose**: Drafts personalized cold emails using xAI API (grok-3-latest).

**Key Data Structures**: 
- Uses environment variable: `XAI_API_KEY`
- API constants: `XAI_API_URL`, `FROM_NAME`
- Config values: `XAI_MODEL`, `XAI_MAX_TOKENS`

**Important Functions**:
- `_build_system_prompt(domain, selected_products_text)`: Assemble xAI system prompt
- `_build_user_content(lead)`: Build user message from lead metadata
- `draft_email(lead, selected_products_text)`: Main function - draft email for lead
  - Returns: (subject, body) tuple
- `_parse_response(raw, lead)`: Parse xAI response into subject/body
- `_fallback_email(lead)`: Safe fallback when xAI unavailable

**File Paths**: 
- Reads: None (uses xAI API over network)
- Writes: None

### backend/product_loader.py
**Purpose**: Loads product catalogue from CSV and serves it to frontend and drafting module.

**Key Data Structures** (from irus_products.csv):
- `product_name`: Product name
- `description`: Product description
- `domain`: "Defence" or "Medical"

**Important Functions**:
- `get_catalogue_json()`: Return full product catalogue as list of dicts
- `format_selected_catalogue(selected_products)`: Format selected products for Claude's system prompt
  - Returns: Text block "- PRODUCT NAME: Short description (first 120 chars)"

**File Paths**: 
- Reads: `PRODUCTS_FILE` (irus_products.csv)
- Writes: None

## 2. Frontend Dashboard

### frontend/src/app/dashboard/page.tsx
**Purpose**: Live dashboard showing pipeline progress, logs, drafts, and sending controls.

**Key Data Structures** (TypeScript interfaces):
- `LogEntry`: Matches log.csv columns
- `Draft`: Matches email_drafts.csv columns
- `CampaignResult`: Matches run_campaign return dict

**State Variables**:
- `logs`: Array of log entries from `/logs` endpoint
- `drafts`: Array of drafts from `/drafts/pending` endpoint
- `status`: Campaign running status and last result
- `error`: Error messages
- UI state flags: `sendingAll`, `sendingOne`, `editingDraft`, `editSubject`, `editBody`, `activeTab`

**Key Functions**:
- `useEffect` polling: Fetches logs, status, and pending drafts every 3 seconds
- `handleSendOne(email)`: Send single draft via API
- `handleSendAll()`: Send all pending drafts via API
- `openEditModal(draft)` / `closeEditModal()` / `saveEdit()`: Edit draft functionality
- Rendering: Tabs for Drafts/Logs, metric cards, draft listing with edit/send controls

**File Paths**: 
- Reads: None (fetches data from backend API)
- Writes: None (sends actions to backend API)

### frontend/src/app/page.tsx
**Purpose**: Main campaign launcher with 4-step wizard (Domain → Products → Location → Launch).

**Key Data Structures** (TypeScript interfaces):
- `Product`: Matches product catalogue structure
- STEPS: ["Domain", "Products", "Location", "Launch"]

**State Variables**:
- `currentStep`: Active wizard step (1-4)
- `domain`: Selected domain ("Defence" | "Medical" | null)
- `products`: Full product catalogue from `/products` endpoint
- `selectedProducts`: Array of selected product names
- `location`: Target geography string
- `launching`: Boolean for launch button state
- `error`: Error messages

**Key Functions**:
- `useEffect`: Fetch products on mount
- `toggleProduct(name)`: Add/remove product from selection
- `handleLaunch()`: Validate form and launch campaign via `/launch` endpoint
- Step renderers: Conditional rendering for each wizard step

**File Paths**: 
- Reads: None (fetches data from backend API)
- Writes: None (sends launch command to backend API)

## 3. CSV Files Data Structure

### leads_raw.csv
**Columns**: name, email, phone, organization, organization_domain, role, category, linkedin_url, city, country, apollo_id, source
**Sample Data**: 
- Contains scraped medical leads with emails like reachus@ckbhospital.comrequest (note: appears to have formatting issue with "request" appended)
- Source indicates "scraped" for Serper-discovered leads

### leads_enriched.csv
**Columns**: All leads_raw.csv columns plus: email_source, phone, has_phone, organization, organization_domain, role, category, linkedin_url, city, country, apollo_id, notes, source
**Sample Data**: 
- Email_source shows "apollo" for all entries (indicating Hunter enrichment disabled or not used)
- Notes show "Email provided by Apollo."
- Has_phone shows "true" for all entries

### log.csv
**Columns**: timestamp, email, name, organization, status, subject, note, apollo_id
**Sample Data**: 
- Shows pipeline actions: drafted → sent → skipped_already_sent
- Status values: drafted, sent, skipped_already_sent
- Note field provides context (e.g., "AI drafted, queued for review.", "Sent after manual review.", "Previously contacted.")

### email_drafts.csv
**Columns**: timestamp, email, name, organization, subject, body, status, lead_json
**Sample Data**: 
- Status values: drafted, sent
- Subject: "Exploring synergies with IRUS" (fallback template)
- Body: Personalized cold email template
- Lead_json: JSON string of original lead data

### irus_products.csv
**Columns**: Product Name, Description, Domain
**Sample Data**: 
- Contains 50+ products split between Defence and Medical domains
- Defence examples: LOGISTICS | MULTI ROLE DRONE (LMRD), LOITERING MUNITION DRONE (LMD)
- Medical examples: Holistic Healing Travel, Advanced Cancer Detection Vehicle, Dental Van

## 4. Database Dependencies
**requirements.txt** contains:
```
fastapi
uvicorn
anthropic
requests
python-dotenv
beautifulsoup4
lxml
```

**Analysis**: 
- No traditional database dependencies (like PostgreSQL, MongoDB, etc.)
- The system uses CSV files as its primary data storage mechanism
- Dependencies are focused on:
  - Web framework: FastAPI, Uvicorn
  - AI integration: Anthropic (though xAI is used via direct API calls)
  - HTTP requests: Requests
  - Environment management: Python-dotenv
  - HTML parsing: BeautifulSoup4, lxml (for web scraping in lead_finder.py)

## 5. Summary of Key Insights

### Architecture
- **Modular Design**: Backend is split into specialized modules (config, lead_finder, lead_enricher, email_drafts, logger, etc.)
- **CSV-Based Storage**: All data persistence uses CSV files rather than a traditional database
- **API-First**: FastAPI backend serves the Next.js frontend via REST endpoints
- **Polling Dashboard**: Frontend uses polling (every 3 seconds) to get real-time updates from backend

### Data Flow
1. **Lead Generation**: Either lead_finder.py (Serper/Hunter) or would use Apollo (not implemented in current code)
2. **Enrichment**: lead_enricher.py adds verified emails via Hunter.io (if enabled)
3. **Deduplication**: logger.py prevents duplicate outreach via already_contacted()
4. **Drafting**: claude_drafter.py creates personalized emails using xAI
5. **Storage**: email_drafts.py saves drafts for manual review
6. **Review**: Dashboard shows drafts for human approval
7. **Sending**: email_sender.py sends approved emails via Gmail SMTP
8. **Logging**: logger.py records all actions for audit trail

### Key Features
- **Manual Review System**: Drafts must be reviewed before sending (REVIEW_BEFORE_SEND = True by default)
- **Deduplication**: Prevents contacting same lead twice
- **Rate Limiting**: Built-in delays for API calls and email sending
- **Error Handling**: Comprehensive try/catch blocks with logging
- **Configuration**: Tunable parameters in config.py
- **Domain Specific**: Separate handling for Defence vs Medical sectors with different job titles, industries, and email tones

### Current Limitations Observed
1. **Email Format Issue**: leads_raw.csv shows emails with "request" appended (e.g., reachus@ckbhospital.comrequest) - likely a scraping artifact
2. **Hunter.io Disabled**: ENRICH_WITH_HUNTER = True but appears not functioning as all emails show source as "apollo"
3. **LinkedIn URLs**: Always empty in CSV files
4. **Fallback Emails**: All sampled emails use the generic "Exploring synergies with IRUS" subject, suggesting xAI API may not be configured or falling back to template
5. **Dry Run Default**: DRY_RUN = True in config, meaning emails are queued but not actually sent unless overridden

This exploration reveals a well-structured pipeline designed for automated outreach with manual review checkpoints, using CSV files for persistence and modular Python components for each stage of the process.