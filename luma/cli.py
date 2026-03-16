"""CLI entry point for Luma."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click

from luma.config.settings import Settings
from luma.utils.logging import setup_logging

from luma.infrastructure.database import Database
from luma.infrastructure.http_client import JikanClient
from luma.infrastructure.rate_limiter import RateLimiter

from luma.core.fetch import AnimeFetcher
from luma.core.quality import QualityChecker
from luma.core.match import WikidataMatcher
from luma.core.storage import Storage

from luma.pipeline.checkpoint import CheckpointManager
from luma.pipeline.orchestrator import PipelineOrchestrator
from luma.pipeline.reporter import PipelineReporter


def get_settings() -> Settings:
    """Get application settings."""
    return Settings.from_env()


def create_pipeline_components(settings: Settings):
    """Create pipeline components.

    Returns:
        Tuple of (orchestrator, reporter, checkpoint_manager)
    """
    # Infrastructure
    db = Database(settings.db_path)
    rate_limiter = RateLimiter(rate=settings.jikan_api_rate)
    http_client = JikanClient(timeout=settings.jikan_timeout, max_retries=settings.jikan_max_retries)

    # Core
    fetcher = AnimeFetcher(rate_limiter=rate_limiter, client=http_client)
    quality_checker = QualityChecker()
    matcher = WikidataMatcher(http_client=http_client)
    storage = Storage(db)

    # Pipeline
    checkpoint_manager = CheckpointManager(settings.checkpoint_path)
    reporter = PipelineReporter()
    orchestrator = PipelineOrchestrator(
        fetcher=fetcher,
        quality_checker=quality_checker,
        matcher=matcher,
        storage=storage,
        checkpoint_manager=checkpoint_manager,
        reporter=reporter,
        batch_size=settings.batch_size,
        max_concurrent=settings.max_concurrent,
    )

    return orchestrator, reporter, checkpoint_manager


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Luma - Anime metadata incremental processing pipeline."""
    pass


@cli.command()
@click.option("--start-id", type=int, required=True, help="Starting MAL ID")
@click.option("--end-id", type=int, required=True, help="Ending MAL ID")
@click.option("--batch-size", type=int, default=10, help="Batch size (default: 10)")
@click.option("--concurrent", type=int, default=5, help="Concurrent operations (default: 5)")
@click.option("--rate-limit", type=float, default=3.0, help="API rate limit req/s (default: 3.0)")
@click.option("--resume", is_flag=True, help="Resume from checkpoint")
def run(start_id: int, end_id: int, batch_size: int, concurrent: int, rate_limit: float, resume: bool):
    """Run the anime metadata pipeline."""
    settings = get_settings()
    settings.batch_size = batch_size
    settings.max_concurrent = concurrent
    settings.jikan_api_rate = rate_limit
    settings.ensure_directories()

    setup_logging(settings.log_level)

    async def execute():
        orchestrator, reporter, checkpoint_manager = create_pipeline_components(settings)

        try:
            report = await orchestrator.run(start_id, end_id, resume=resume)
            reporter.print_report(report)
            return 0
        except KeyboardInterrupt:
            click.echo("\nPipeline interrupted by user")
            return 130
        except Exception as e:
            click.echo(f"Pipeline error: {e}", err=True)
            return 1
        finally:
            await orchestrator.fetcher.close()
            await orchestrator.matcher.close()
            await orchestrator.storage.db.close()

    sys.exit(asyncio.run(execute()))


@cli.command()
@click.option("--batch-size", type=int, default=10, help="Batch size (default: 10)")
@click.option("--concurrent", type=int, default=5, help="Concurrent operations (default: 5)")
@click.option("--rate-limit", type=float, default=3.0, help="API rate limit req/s (default: 3.0)")
def resume(batch_size: int, concurrent: int, rate_limit: float):
    """Resume pipeline from checkpoint."""
    settings = get_settings()
    settings.batch_size = batch_size
    settings.max_concurrent = concurrent
    settings.jikan_api_rate = rate_limit
    settings.ensure_directories()

    setup_logging(settings.log_level)

    checkpoint_manager = CheckpointManager(settings.checkpoint_path)

    if not checkpoint_manager.exists():
        click.echo("No checkpoint found. Use 'luma run' to start a new pipeline.", err=True)
        sys.exit(1)

    state = checkpoint_manager.load()
    if state is None:
        click.echo("Failed to load checkpoint.", err=True)
        sys.exit(1)

    click.echo(f"Resuming from checkpoint {state.checkpoint_id}")
    click.echo(f"Range: {state.start_id} - {state.end_id}")
    click.echo(f"Progress: {len(state.processed_ids)}/{state.total_count} processed")
    click.echo(f"Stage: {state.current_stage}")

    async def execute():
        orchestrator, reporter, _ = create_pipeline_components(settings)

        try:
            report = await orchestrator.run(state.start_id, state.end_id, resume=True)
            reporter.print_report(report)
            return 0
        except KeyboardInterrupt:
            click.echo("\nPipeline interrupted by user")
            return 130
        except Exception as e:
            click.echo(f"Pipeline error: {e}", err=True)
            return 1
        finally:
            await orchestrator.fetcher.close()
            await orchestrator.matcher.close()
            await orchestrator.storage.db.close()

    sys.exit(asyncio.run(execute()))


@cli.command()
@click.option("--output", type=str, default="output/anime.jsonl", help="Output file path")
@click.option("--filter", type=click.Choice(["all", "matched", "unmatched"], case_sensitive=False),
              default="all", help="Filter type (all, matched, unmatched)")
@click.option("--limit", type=int, default=None, help="Maximum records to export")
def export(output: str, filter: str, limit: Optional[int]):
    """Export anime data to JSONL."""
    settings = get_settings()
    settings.ensure_directories()

    setup_logging(settings.log_level)

    async def execute():
        db = Database(settings.db_path)
        storage = Storage(db)

        try:
            data = await storage.export_data(filter_type=filter, limit=limit)

            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                for record in data:
                    # Convert to JSON-serializable dict
                    export_record = {
                        "mal_id": record["mal_id"],
                        "title": record["title"],
                        "title_japanese": record.get("title_japanese"),
                        "title_english": record.get("title_english"),
                        "episodes": record.get("episodes"),
                        "score": record.get("score"),
                        "year": record.get("year"),
                        "type": record.get("type"),
                        "source": record.get("source"),
                        "studios": json.loads(record["studios"]) if record.get("studios") else [],
                        "genres": json.loads(record["genres"]) if record.get("genres") else [],
                        "synopsis": record.get("synopsis"),
                        "quality_passed": record.get("quality_passed"),
                        "wikidata_id": record.get("wikidata_id"),
                        "wikidata_label": record.get("wikidata_label"),
                        "match_confidence": record.get("match_confidence"),
                    }
                    f.write(json.dumps(export_record) + "\n")

            click.echo(f"Exported {len(data)} records to {output}")
            return 0

        except Exception as e:
            click.echo(f"Export error: {e}", err=True)
            return 1
        finally:
            await db.close()

    sys.exit(asyncio.run(execute()))


@cli.command()
def status():
    """Show pipeline status."""
    settings = get_settings()

    setup_logging(settings.log_level)

    async def execute():
        checkpoint_manager = CheckpointManager(settings.checkpoint_path)
        db = Database(settings.db_path)

        try:
            # Checkpoint status
            if checkpoint_manager.exists():
                state = checkpoint_manager.load()
                if state:
                    click.echo("CHECKPOINT STATUS")
                    click.echo("-" * 40)
                    click.echo(f"ID: {state.checkpoint_id}")
                    click.echo(f"Range: {state.start_id} - {state.end_id}")
                    click.echo(f"Progress: {len(state.processed_ids)}/{state.total_count} "
                               f"({state.get_progress_summary()['percent']}%)")
                    click.echo(f"Stage: {state.current_stage}")
                    click.echo(f"Timestamp: {state.timestamp}")
                    click.echo("")

                    if state.errors:
                        click.echo(f"Recent errors: {len(state.errors)}")
            else:
                click.echo("No checkpoint found.")

            click.echo("")
            click.echo("DATABASE STATUS")
            click.echo("-" * 40)

            stats = await db.get_stats()
            click.echo(f"Total anime: {stats['total_anime']}")
            click.echo(f"Completed: {stats['completed_anime']}")
            click.echo(f"Quality passed: {stats['quality_passed']}")
            click.echo(f"Quality failed: {stats['quality_failed']}")
            click.echo(f"Matched: {stats['matched']}")
            click.echo(f"Unmatched: {stats['unmatched']}")

            return 0

        except Exception as e:
            click.echo(f"Status error: {e}", err=True)
            return 1
        finally:
            await db.close()

    sys.exit(asyncio.run(execute()))


@cli.command()
@click.confirmation_option(prompt="Clear checkpoint file?")
def checkpoint_clear():
    """Clear checkpoint file."""
    settings = get_settings()

    checkpoint_manager = CheckpointManager(settings.checkpoint_path)

    if not checkpoint_manager.exists():
        click.echo("No checkpoint found.")
        return

    checkpoint_manager.clear()
    click.echo("Checkpoint cleared.")


def main() -> int:
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
