# Architecture - Luma Anime Metadata Pipeline

## Overview

Luma is an incremental, checkpoint-resumable data pipeline for processing anime metadata from MyAnimeList (MAL).

## Design Principles

1. **Incremental Processing**: Process data in batches to enable checkpoint/resume
2. **Idempotency**: Re-processing the same data should produce consistent results
3. **Fault Tolerance**: Graceful handling of API errors, timeouts, and interruptions
4. **Resumability**: Resume from any interruption point without data loss

## Module Structure

```
src/luma/
├── core/              # Core business logic
│   ├── fetch.py       # Data fetching from Jikan API
│   ├── quality.py     # Quality validation
│   ├── match.py       # Wikidata matching
│   └── storage.py     # Database operations
├── pipeline/          # Pipeline orchestration
│   ├── orchestrator.py # Main pipeline flow
│   ├── checkpoint.py   # Checkpoint management
│   └── reporter.py     # Report generation
├── infrastructure/    # Infrastructure
│   ├── rate_limiter.py # Rate limiting
│   ├── database.py     # Database connection
│   └── http_client.py  # HTTP client
├── models/            # Data models
│   ├── anime.py       # Anime data
│   ├── quality.py     # Quality results
│   ├── match.py       # Match results
│   └── checkpoint.py  # Checkpoint state
├── config/            # Configuration
│   ├── settings.py    # Settings
│   └── constants.py   # Constants
└── utils/             # Utilities
    ├── logging.py     # Logging setup
    └── helpers.py     # Helper functions
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     Pipeline Orchestrator                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Fetch          ──►  Anime Data from Jikan API               │
│  2. Quality Check  ──►  Validate completeness and values        │
│  3. Wikidata Match ──►  Find matching Wikidata entries          │
│  4. Storage        ──►  Persist to SQLite database              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ Checkpoint Save │  ◄── After each batch
                    └─────────────────┘
```

## Checkpoint Strategy

Checkpoints are saved:
- After each batch completes
- Before stage transitions
- On error/exception

Checkpoint state includes:
- Processed, in-progress, and pending anime IDs
- Current stage and batch index
- Statistics and error information

## Quality Rules

1. **Field Completeness**: Required fields must exist
2. **Value Validation**:
   - Score: 1-10
   - Episodes: 1-2000
   - Year: 1900 to current year + 5
3. **Title Format**: Non-empty, no TBA/N/A placeholders

## Wikidata Matching

Matching strategies (by priority):
1. **Exact ID Match**: Using MAL ID property (confidence ≥ 0.9)
2. **Exact Title + Year**: Precise match (confidence ≥ 0.9)
3. **Fuzzy Title**: RapidFuzz similarity (confidence 0.5-0.9)
4. **Multi-field**: Title + episodes + year (confidence 0.5-0.9)

## Database Schema

```sql
-- Main anime table
CREATE TABLE anime (
    id INTEGER PRIMARY KEY,
    mal_id INTEGER UNIQUE NOT NULL,
    title TEXT NOT NULL,
    -- ... other fields
    processing_status TEXT NOT NULL DEFAULT 'pending'
);

-- Quality check results
CREATE TABLE quality_checks (
    id INTEGER PRIMARY KEY,
    anime_id INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    -- ... other fields
    FOREIGN KEY (anime_id) REFERENCES anime(id)
);

-- Wikidata matches
CREATE TABLE matches (
    id INTEGER PRIMARY KEY,
    anime_id INTEGER NOT NULL UNIQUE,
    wikidata_id TEXT,
    confidence REAL NOT NULL,
    -- ... other fields
    FOREIGN KEY (anime_id) REFERENCES anime(id)
);

-- Processing errors
CREATE TABLE processing_errors (
    id INTEGER PRIMARY KEY,
    anime_id INTEGER,
    stage TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Concurrency Control

Three-tier control:
1. **Semaphore**: Max concurrent operations (default: 10)
2. **Rate Limiter**: Token bucket, 3 req/s for Jikan API
3. **Batch Size**: Process in batches of 10

## CLI Commands

```bash
luma run [OPTIONS]        # Run pipeline
luma resume               # Resume from checkpoint
luma export [OPTIONS]     # Export data
luma status               # View status
luma checkpoint clear     # Clear checkpoint
```
