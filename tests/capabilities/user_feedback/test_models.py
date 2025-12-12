"""Tests for feedback models."""

import pytest
from vanna.capabilities.user_feedback.models import (
    FeedbackContext,
    FeedbackRating,
    FeedbackRecord,
    FeedbackSearchResult,
    FeedbackStats,
)


def test_feedback_rating_enum():
    """Test FeedbackRating enum values."""
    assert FeedbackRating.HELPFUL == "helpful"
    assert FeedbackRating.NOT_HELPFUL == "not_helpful"
    assert FeedbackRating.NEUTRAL == "neutral"


def test_feedback_context_creation():
    """Test creating FeedbackContext."""
    context = FeedbackContext(
        question="Show sales",
        response="Sales: $1M",
        tools_used=["run_sql"],
        execution_time_ms=100.5,
    )

    assert context.question == "Show sales"
    assert context.response == "Sales: $1M"
    assert context.tools_used == ["run_sql"]
    assert context.execution_time_ms == 100.5


def test_feedback_context_optional_fields():
    """Test FeedbackContext with optional fields."""
    context = FeedbackContext(
        question="Test",
        response="Response",
    )

    assert context.tools_used == []
    assert context.execution_time_ms is None
    assert context.sql_query is None


def test_feedback_record_creation():
    """Test creating FeedbackRecord."""
    context = FeedbackContext(
        question="Test question",
        response="Test response",
        tools_used=["tool1"],
    )

    record = FeedbackRecord(
        feedback_id="fb_123",
        user_id="user_456",
        conversation_id="conv_789",
        rating=FeedbackRating.HELPFUL,
        context=context,
        comment="Great!",
        timestamp="2024-01-15T10:00:00Z",
    )

    assert record.feedback_id == "fb_123"
    assert record.user_id == "user_456"
    assert record.conversation_id == "conv_789"
    assert record.rating == FeedbackRating.HELPFUL
    assert record.comment == "Great!"
    assert record.context.question == "Test question"


def test_feedback_search_result():
    """Test FeedbackSearchResult creation."""
    context = FeedbackContext(question="Test", response="Response")
    record = FeedbackRecord(
        user_id="user1",
        conversation_id="conv1",
        rating=FeedbackRating.HELPFUL,
        context=context,
    )

    result = FeedbackSearchResult(
        feedback=record,
        similarity_score=0.85,
        rank=1,
    )

    assert result.feedback.user_id == "user1"
    assert result.similarity_score == 0.85
    assert result.rank == 1


def test_feedback_stats_from_empty_list():
    """Test creating FeedbackStats from empty list."""
    stats = FeedbackStats.from_feedback_list([])

    assert stats.total_count == 0
    assert stats.helpful_count == 0
    assert stats.not_helpful_count == 0
    assert stats.helpful_percentage == 0.0


def test_feedback_stats_from_feedback_list():
    """Test calculating statistics from feedback list."""
    context = FeedbackContext(question="Q", response="R")

    feedback_list = [
        FeedbackRecord(
            user_id="u1",
            conversation_id="c1",
            rating=FeedbackRating.HELPFUL,
            context=context,
            timestamp="2024-01-15T10:00:00Z",
        ),
        FeedbackRecord(
            user_id="u2",
            conversation_id="c2",
            rating=FeedbackRating.HELPFUL,
            context=context,
            timestamp="2024-01-15T11:00:00Z",
        ),
        FeedbackRecord(
            user_id="u3",
            conversation_id="c3",
            rating=FeedbackRating.NOT_HELPFUL,
            context=context,
            timestamp="2024-01-16T10:00:00Z",
        ),
        FeedbackRecord(
            user_id="u4",
            conversation_id="c4",
            rating=FeedbackRating.NEUTRAL,
            context=context,
            timestamp="2024-01-16T11:00:00Z",
        ),
    ]

    stats = FeedbackStats.from_feedback_list(feedback_list)

    assert stats.total_count == 4
    assert stats.helpful_count == 2
    assert stats.not_helpful_count == 1
    assert stats.neutral_count == 1
    assert stats.helpful_percentage == 50.0
    assert stats.not_helpful_percentage == 25.0

    # Check feedback over time
    assert stats.feedback_over_time is not None
    assert "2024-01-15" in stats.feedback_over_time
    assert "2024-01-16" in stats.feedback_over_time
    assert stats.feedback_over_time["2024-01-15"] == 2
    assert stats.feedback_over_time["2024-01-16"] == 2


def test_feedback_stats_validation():
    """Test FeedbackStats field validation."""
    stats = FeedbackStats(
        total_count=100,
        helpful_count=75,
        not_helpful_count=20,
        neutral_count=5,
        helpful_percentage=75.0,
        not_helpful_percentage=20.0,
    )

    assert stats.total_count == 100
    assert stats.helpful_percentage == 75.0

    # Test percentage bounds
    with pytest.raises(Exception):  # Pydantic validation error
        FeedbackStats(
            total_count=10,
            helpful_count=5,
            not_helpful_count=5,
            helpful_percentage=150.0,  # Invalid: > 100
            not_helpful_percentage=50.0,
        )
