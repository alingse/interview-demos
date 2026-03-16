# Luma - Anime Metadata Pipeline

A reliable, checkpoint-resumable data pipeline for fetching and processing anime metadata from MyAnimeList (MAL).

## Features

- **Incremental Processing**: Process anime IDs in ranges with batch support
- **Checkpoint/Resume**: Resume from any interruption point
- **Quality Checks**: Validate data completeness and value ranges
- **Wikidata Matching**: Match anime to Wikidata entries with confidence scoring
- **Rate Limiting**: Built-in rate limiter for API respect
- **SQLite Storage**: Persistent storage with export capabilities

## Installation

```bash
uv sync
```

## Usage

```bash
# Run pipeline
luma run --start-id 1 --end-id 1000

# Resume from checkpoint
luma resume

# Export data
luma export --output output/anime.jsonl

# View status
luma status

# Clear checkpoint
luma checkpoint clear
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design documentation.

## License

MIT
