"""Quality check models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class QualityRule(str, Enum):
    """Quality check rules."""

    FIELD_COMPLETENESS = "field_completeness"
    VALUE_RANGE = "value_range"
    TITLE_FORMAT = "title_format"


class RuleViolation(BaseModel):
    """A single quality rule violation."""

    rule: QualityRule
    field: str | None = None
    message: str
    severity: str = Field(default="error")  # error, warning, info


class QualityResult(BaseModel):
    """Result of quality checking."""

    passed: bool = Field(..., description="Whether all checks passed")
    overall_reason: str | None = Field(None, description="Overall failure reason")
    violations: list[RuleViolation] = Field(default_factory=list, description="Rule violations")

    @classmethod
    def pass_result(cls) -> "QualityResult":
        """Create a passing result."""
        return cls(passed=True, violations=[])

    @classmethod
    def fail_result(cls, message: str, violations: list[RuleViolation]) -> "QualityResult":
        """Create a failing result."""
        return cls(passed=False, overall_reason=message, violations=violations)

    def add_violation(self, rule: QualityRule, field: str | None, message: str) -> None:
        """Add a violation."""
        self.violations.append(
            RuleViolation(rule=rule, field=field, message=message, severity="error")
        )
        self.passed = False


class QualityCheckDB(BaseModel):
    """Quality check as stored in database."""

    id: int
    anime_id: int
    passed: bool
    overall_reason: str | None = None
    violation_details: str | None = None  # JSON string
    created_at: datetime | None = None
