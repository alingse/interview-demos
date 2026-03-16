"""Quality checking for anime data."""

import logging
from typing import Optional

from luma.models.anime import Anime
from luma.models.quality import QualityResult, QualityRule, RuleViolation

logger = logging.getLogger(__name__)


class QualityChecker:
    """Quality checker for anime metadata."""

    # Required fields
    REQUIRED_FIELDS = ["title", "mal_id"]

    # Valid ranges
    MIN_SCORE = 1.0
    MAX_SCORE = 10.0
    MIN_EPISODES = 1
    MAX_EPISODES = 2000
    MIN_YEAR = 1900

    # Invalid title patterns
    INVALID_TITLE_PATTERNS = ["tba", "n/a", "tbd", "unknown"]

    def __init__(self, current_year: Optional[int] = None):
        """Initialize quality checker.

        Args:
            current_year: Current year for year validation (auto-detected if None)
        """
        from datetime import datetime

        self.current_year = current_year or datetime.now().year
        self.max_year = self.current_year + 5

    def check(self, anime: Anime) -> QualityResult:
        """Perform all quality checks.

        Args:
            anime: Anime to check

        Returns:
            QualityResult with pass/fail status
        """
        violations: list[RuleViolation] = []

        # 1. Field completeness check
        completeness = self._check_field_completeness(anime)
        violations.extend(completeness)

        # 2. Value range check
        range_check = self._check_value_ranges(anime)
        violations.extend(range_check)

        # 3. Title format check
        title_check = self._check_title_format(anime)
        violations.extend(title_check)

        # Build result
        if not violations:
            return QualityResult.pass_result()

        messages = [v.message for v in violations]
        return QualityResult.fail_result(
            message="; ".join(messages),
            violations=violations,
        )

    def _check_field_completeness(self, anime: Anime) -> list[RuleViolation]:
        """Check required fields are present."""
        violations: list[RuleViolation] = []

        for field in self.REQUIRED_FIELDS:
            value = getattr(anime, field, None)
            if value is None:
                violations.append(
                    RuleViolation(
                        rule=QualityRule.FIELD_COMPLETENESS,
                        field=field,
                        message=f"Required field '{field}' is missing",
                    )
                )

        return violations

    def _check_value_ranges(self, anime: Anime) -> list[RuleViolation]:
        """Check values are within valid ranges."""
        violations: list[RuleViolation] = []

        # Score validation
        if anime.score is not None:
            if not (self.MIN_SCORE <= anime.score <= self.MAX_SCORE):
                violations.append(
                    RuleViolation(
                        rule=QualityRule.VALUE_RANGE,
                        field="score",
                        message=f"Score {anime.score} not in valid range [{self.MIN_SCORE}, {self.MAX_SCORE}]",
                    )
                )

        # Episodes validation
        if anime.episodes is not None:
            if not (self.MIN_EPISODES <= anime.episodes <= self.MAX_EPISODES):
                violations.append(
                    RuleViolation(
                        rule=QualityRule.VALUE_RANGE,
                        field="episodes",
                        message=f"Episodes {anime.episodes} not in valid range [{self.MIN_EPISODES}, {self.MAX_EPISODES}]",
                    )
                )

        # Year validation
        if anime.year is not None:
            if not (self.MIN_YEAR <= anime.year <= self.max_year):
                violations.append(
                    RuleViolation(
                        rule=QualityRule.VALUE_RANGE,
                        field="year",
                        message=f"Year {anime.year} not in valid range [{self.MIN_YEAR}, {self.max_year}]",
                    )
                )

        return violations

    def _check_title_format(self, anime: Anime) -> list[RuleViolation]:
        """Check title format is valid."""
        violations: list[RuleViolation] = []

        title_lower = anime.title.lower().strip()

        # Check for empty or placeholder titles
        if not title_lower or title_lower in self.INVALID_TITLE_PATTERNS:
            violations.append(
                RuleViolation(
                    rule=QualityRule.TITLE_FORMAT,
                    field="title",
                    message=f"Invalid title: '{anime.title}'",
                )
            )

        # Check Japanese title if present
        if anime.title_japanese:
            jp_lower = anime.title_japanese.lower().strip()
            if not jp_lower or jp_lower in self.INVALID_TITLE_PATTERNS:
                violations.append(
                    RuleViolation(
                        rule=QualityRule.TITLE_FORMAT,
                        field="title_japanese",
                        message=f"Invalid Japanese title: '{anime.title_japanese}'",
                    )
                )

        return violations
