"""Tests for LocalFeedbackCapability."""

import pytest
from datetime import datetime
from vanna.capabilities.user_feedback import (
    LocalFeedbackCapability,
    FeedbackContext,
    FeedbackRating,
)


@pytest.fixture
def feedback_capability():
    """Create a LocalFeedbackCapability instance for testing."""
    return LocalFeedbackCapability()


@pytest.fixture
def sample_context():
    """Create a sample FeedbackContext for testing."""
    return FeedbackContext(
        question="Show me sales data for Q4",
        response="Q4 sales totaled $1.2M",
        tools_used=["run_sql", "visualize_data"],
        execution_time_ms=245.5,
    )


@pytest.mark.asyncio
async def test_save_feedback(feedback_capability, sample_context):
    """Test saving feedback."""
    record = await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
        comment="Great visualization!",
    )

    assert record.feedback_id is not None
    assert record.feedback_id.startswith("fb_")
    assert record.user_id == "alice"
    assert record.conversation_id == "conv_001"
    assert record.rating == FeedbackRating.HELPFUL
    assert record.comment == "Great visualization!"
    assert record.timestamp is not None
    assert record.context.question == sample_context.question


@pytest.mark.asyncio
async def test_save_feedback_without_comment(feedback_capability, sample_context):
    """Test saving feedback without comment."""
    record = await feedback_capability.save_feedback(
        user_id="bob",
        conversation_id="conv_002",
        rating=FeedbackRating.NOT_HELPFUL,
        context=sample_context,
    )

    assert record.comment is None
    assert record.rating == FeedbackRating.NOT_HELPFUL


@pytest.mark.asyncio
async def test_get_feedback_stats_empty(feedback_capability):
    """Test getting stats when no feedback exists."""
    stats = await feedback_capability.get_feedback_stats()

    assert stats.total_count == 0
    assert stats.helpful_count == 0
    assert stats.not_helpful_count == 0


@pytest.mark.asyncio
async def test_get_feedback_stats(feedback_capability, sample_context):
    """Test getting feedback statistics."""
    # Add feedback
    await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
    )

    await feedback_capability.save_feedback(
        user_id="bob",
        conversation_id="conv_002",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
    )

    await feedback_capability.save_feedback(
        user_id="charlie",
        conversation_id="conv_003",
        rating=FeedbackRating.NOT_HELPFUL,
        context=sample_context,
    )

    # Get stats
    stats = await feedback_capability.get_feedback_stats()

    assert stats.total_count == 3
    assert stats.helpful_count == 2
    assert stats.not_helpful_count == 1
    assert stats.helpful_percentage == pytest.approx(66.67, rel=0.1)
    assert stats.not_helpful_percentage == pytest.approx(33.33, rel=0.1)


@pytest.mark.asyncio
async def test_get_recent_feedback(feedback_capability, sample_context):
    """Test getting recent feedback."""
    # Add feedback
    record1 = await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
    )

    record2 = await feedback_capability.save_feedback(
        user_id="bob",
        conversation_id="conv_002",
        rating=FeedbackRating.NOT_HELPFUL,
        context=sample_context,
    )

    # Get recent feedback
    recent = await feedback_capability.get_recent_feedback(limit=10)

    assert len(recent) == 2
    # Should be ordered by timestamp (most recent first)
    assert recent[0].feedback_id == record2.feedback_id
    assert recent[1].feedback_id == record1.feedback_id


@pytest.mark.asyncio
async def test_get_recent_feedback_with_rating_filter(feedback_capability, sample_context):
    """Test getting recent feedback with rating filter."""
    # Add mixed feedback
    await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
    )

    await feedback_capability.save_feedback(
        user_id="bob",
        conversation_id="conv_002",
        rating=FeedbackRating.NOT_HELPFUL,
        context=sample_context,
    )

    await feedback_capability.save_feedback(
        user_id="charlie",
        conversation_id="conv_003",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
    )

    # Get only helpful feedback
    helpful = await feedback_capability.get_recent_feedback(
        rating_filter=FeedbackRating.HELPFUL
    )

    assert len(helpful) == 2
    assert all(f.rating == FeedbackRating.HELPFUL for f in helpful)


@pytest.mark.asyncio
async def test_search_similar_feedback(feedback_capability):
    """Test searching for similar feedback."""
    # Add feedback with different questions
    await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=FeedbackContext(
            question="Show me sales data for Q4",
            response="Q4 sales: $1.2M",
            tools_used=["run_sql"],
        ),
    )

    await feedback_capability.save_feedback(
        user_id="bob",
        conversation_id="conv_002",
        rating=FeedbackRating.HELPFUL,
        context=FeedbackContext(
            question="Display sales numbers",
            response="Sales: $1.5M",
            tools_used=["run_sql"],
        ),
    )

    await feedback_capability.save_feedback(
        user_id="charlie",
        conversation_id="conv_003",
        rating=FeedbackRating.NOT_HELPFUL,
        context=FeedbackContext(
            question="Show revenue breakdown",
            response="Revenue data...",
            tools_used=["run_sql"],
        ),
    )

    # Search for "sales data"
    results = await feedback_capability.search_similar_feedback(
        query="sales data",
        limit=10,
        min_similarity=0.0,  # Lower threshold for simple matching
    )

    assert len(results) > 0
    # Results should be ordered by similarity
    for i in range(len(results) - 1):
        assert results[i].similarity_score >= results[i + 1].similarity_score


@pytest.mark.asyncio
async def test_search_similar_feedback_with_rating_filter(feedback_capability):
    """Test searching with rating filter."""
    # Add mixed feedback
    await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=FeedbackContext(
            question="Show sales data",
            response="Sales: $1M",
            tools_used=["run_sql"],
        ),
    )

    await feedback_capability.save_feedback(
        user_id="bob",
        conversation_id="conv_002",
        rating=FeedbackRating.NOT_HELPFUL,
        context=FeedbackContext(
            question="Display sales information",
            response="Sales info...",
            tools_used=["run_sql"],
        ),
    )

    # Search for only helpful
    results = await feedback_capability.search_similar_feedback(
        query="sales",
        rating_filter=FeedbackRating.HELPFUL,
        min_similarity=0.0,
    )

    assert len(results) >= 1
    assert all(r.feedback.rating == FeedbackRating.HELPFUL for r in results)


@pytest.mark.asyncio
async def test_delete_feedback(feedback_capability, sample_context):
    """Test deleting feedback."""
    # Add feedback
    record = await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
    )

    # Verify it exists
    assert feedback_capability.count() == 1

    # Delete it
    deleted = await feedback_capability.delete_feedback(record.feedback_id)
    assert deleted is True

    # Verify it's gone
    assert feedback_capability.count() == 0

    # Try deleting again (should return False)
    deleted_again = await feedback_capability.delete_feedback(record.feedback_id)
    assert deleted_again is False


@pytest.mark.asyncio
async def test_clear_all_feedback(feedback_capability, sample_context):
    """Test clearing all feedback."""
    # Add multiple feedback items
    for i in range(5):
        await feedback_capability.save_feedback(
            user_id=f"user_{i}",
            conversation_id=f"conv_{i}",
            rating=FeedbackRating.HELPFUL,
            context=sample_context,
        )

    assert feedback_capability.count() == 5

    # Clear all
    count = await feedback_capability.clear_all_feedback()

    assert count == 5
    assert feedback_capability.count() == 0


@pytest.mark.asyncio
async def test_clear_feedback_with_user_filter(feedback_capability, sample_context):
    """Test clearing feedback for specific user."""
    # Add feedback from different users
    await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
    )

    await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_002",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
    )

    await feedback_capability.save_feedback(
        user_id="bob",
        conversation_id="conv_003",
        rating=FeedbackRating.HELPFUL,
        context=sample_context,
    )

    assert feedback_capability.count() == 3

    # Clear only alice's feedback
    count = await feedback_capability.clear_all_feedback(user_id="alice")

    assert count == 2
    assert feedback_capability.count() == 1

    # Remaining feedback should be bob's
    remaining = feedback_capability.get_all_feedback()
    assert remaining[0].user_id == "bob"
