# Restaurant Reservation Agent

A working reservation assistant that books, modifies, and cancels restaurant reservations through a Streamlit chat interface. Reservation operations are deterministic and persist to SQLite; Groq is an optional natural-language extraction layer, not a dependency for the core workflow.

## What it demonstrates

- Multi-turn collection of missing reservation details
- Optional structured extraction through Groq's OpenAI-compatible API
- Offline command parsing for reproducible demos and tests
- SQLite persistence with transactional capacity checks
- Booking confirmation before data is written
- Email-and-ID checks for modification and cancellation
- Nearby time suggestions when a slot is full
- Input validation with Pydantic
- Automated tests and linting in GitHub Actions

## Architecture

```text
Streamlit or CLI
       |
ReservationAgent
       |
HybridExtractor ---- optional Groq API
       |
ReservationStore ---- SQLite
```

The language model, when enabled, only converts natural language into validated fields. The application code decides which action to perform, checks capacity, asks for confirmation, and writes to the database.

## Run locally

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS or Linux
source .venv/bin/activate
```

Install and start the web app:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The application creates `data/restaurant.db` automatically. No external database or API key is required.

## Offline demo format

Without a Groq key, enter explicit commands in the chat:

```text
book | name=Ahmed | email=ahmed@example.com | party=2 | date=2026-10-10 | time=19:00 | type=dinner
yes
modify | id=1 | email=ahmed@example.com | time=20:00
cancel | id=1 | email=ahmed@example.com
```

There is also a terminal interface:

```bash
python demo.py
```

## Optional natural-language mode

Copy `.env.example` to `.env`, then set:

```dotenv
GROQ_API_KEY=your-key
GROQ_MODEL=a-current-groq-model-id
```

With both values present, natural-language requests are sent to Groq for structured extraction. If extraction fails, the agent falls back to the local parser.

## Tests

```bash
pip install -r requirements-dev.txt
ruff check .
python -m pytest -q
```

Tests use temporary SQLite databases and do not require network access or credentials.

## Data and security notes

- The generated database and `.env` file are excluded from version control.
- SQLite is appropriate for a local demonstration, not a multi-instance deployment.
- Email plus reservation ID is a lightweight ownership check for this portfolio project. A production system should use authenticated accounts, authorization rules, encrypted secrets, audit logging, and a managed database.
- The optional provider receives the conversation state needed for field extraction. Do not enter sensitive personal information when using a third-party model.

## Project structure

```text
restaurant_agent/
  agent.py         conversation and action flow
  database.py      SQLite repository and capacity rules
  extraction.py    offline and optional Groq extraction
  models.py        validated application models
app.py             Streamlit interface
demo.py            terminal interface
tests/              behavior and database tests
docs/               original course presentation
```

## Background

This project began as a generative-AI course exercise. The original presentation is retained in [`docs/original-course-presentation.pdf`](docs/original-course-presentation.pdf). The implementation was subsequently hardened into a reproducible portfolio project with offline operation, consistent storage, tests, CI, and documented limitations.

## License

MIT
