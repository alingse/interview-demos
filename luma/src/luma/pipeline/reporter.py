"""Pipeline reporting."""

import logging
from datetime import datetime
from typing import Optional

from luma.models.checkpoint import CheckpointState, PipelineReport

logger = logging.getLogger(__name__)


class PipelineReporter:
    """Generate pipeline execution reports."""

    async def generate(
        self,
        state: CheckpointState,
        resumed: bool = False,
    ) -> PipelineReport:
        """Generate pipeline report from checkpoint state.

        Args:
            state: Final checkpoint state
            resumed: Whether this was a resumed run

        Returns:
            PipelineReport
        """
        now = datetime.utcnow()

        return PipelineReport(
            checkpoint_id=state.checkpoint_id,
            start_time=state.stats.start_time or now,
            end_time=state.stats.end_time or now,
            start_id=state.start_id,
            end_id=state.end_id,
            total_processed=state.stats.processed,
            successful=state.stats.processed - state.stats.failed,
            failed=state.stats.failed,
            skipped=state.stats.skipped,
            quality_passed=state.stats.quality_passed,
            quality_failed=state.stats.quality_failed,
            matched=state.stats.matched,
            unmatched=state.stats.unmatched,
            errors=state.errors,
            resumed=resumed,
        )

    def format_report(self, report: PipelineReport) -> str:
        """Format report as human-readable text.

        Args:
            report: PipelineReport

        Returns:
            Formatted report string
        """
        lines = [
            "=" * 60,
            "PIPELINE EXECUTION REPORT",
            "=" * 60,
            "",
            f"Checkpoint ID: {report.checkpoint_id}",
            f"Range: MAL ID {report.start_id} - {report.end_id}",
            f"Resumed: {report.resumed}",
            "",
            f"Start Time: {report.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"End Time: {report.end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "-" * 60,
            "SUMMARY",
            "-" * 60,
            f"Total Processed: {report.total_processed}",
            f"Successful: {report.successful}",
            f"Failed: {report.failed}",
            f"Skipped: {report.skipped}",
            "",
            "-" * 60,
            "QUALITY CHECKS",
            "-" * 60,
            f"Passed: {report.quality_passed}",
            f"Failed: {report.quality_failed}",
            "",
            "-" * 60,
            "WIKIDATA MATCHING",
            "-" * 60,
            f"Matched: {report.matched}",
            f"Unmatched: {report.unmatched}",
        ]

        if report.errors:
            lines.extend([
                "",
                "-" * 60,
                "ERRORS",
                "-" * 60,
            ])
            for error in report.errors[-10:]:  # Show last 10 errors
                anime_str = f"Anime {error.anime_id}" if error.anime_id else "General"
                lines.append(f"{anime_str} [{error.stage}]: {error.error_message}")

        lines.append("=" * 60)

        return "\n".join(lines)

    def print_report(self, report: PipelineReport) -> None:
        """Print report to console.

        Args:
            report: PipelineReport
        """
        print(self.format_report(report))

    async def save_report(
        self,
        report: PipelineReport,
        output_path: str = "output/report.txt",
    ) -> None:
        """Save report to file.

        Args:
            report: PipelineReport
            output_path: Output file path
        """
        from pathlib import Path

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(self.format_report(report))

        logger.info(f"Report saved to {output_path}")
