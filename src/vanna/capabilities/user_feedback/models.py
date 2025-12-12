"""
Feedback storage models and types.

This module contains Pydantic models for feedback data structures.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..._compat import StrEnum


class FeedbackRating(StrEnum):
    """Enumeration of feedback rating values."""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    NEUTRAL = "neutral"


class FeedbackContext(BaseModel):
    """Context information about the interaction that received feedback.

    This captures the full context of the agent response so we can learn
    from successful patterns and avoid unsuccessful ones.
    """

    question: str = Field(description="Original user question")
    response: str = Field(description="Agent's response text")
    tools_used: List[str] = Field(
        default_factory=list, description="List of tools executed"
    )
    execution_time_ms: Optional[float] = Field(
        default=None, description="Total execution time in milliseconds"
    )
    sql_query: Optional[str] = Field(
        default=None, description="SQL query if run_sql tool was used"
    )


class FeedbackRecord(BaseModel):
    """A stored feedback record.

    Represents a single piece of user feedback with full context.
    """

    feedback_id: Optional[str] = Field(default=None, description="Unique feedback ID")
    user_id: str = Field(description="User who provided feedback")
    conversation_id: str = Field(description="Conversation ID")
    message_id: Optional[str] = Field(
        default=None, description="Specific message ID if available"
    )
    rating: FeedbackRating = Field(description="Feedback rating")
    comment: Optional[str] = Field(
        default=None, description="Optional detailed comment"
    )
    context: FeedbackContext = Field(description="Context of the interaction")
    timestamp: Optional[str] = Field(
        default=None, description="ISO 8601 timestamp of feedback"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "feedback_id": "fb_123abc",
                "user_id": "user_456",
                "conversation_id": "conv_789",
                "rating": "helpful",
                "comment": "Great explanation!",
                "context": {
                    "question": "Show me sales for Q4",
                    "response": "Here are the Q4 sales...",
                    "tools_used": ["run_sql", "visualize_data"],
                    "execution_time_ms": 245.5,
                },
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }


class FeedbackSearchResult(BaseModel):
    """A search result from feedback storage.

    Represents a feedback record with similarity score for ranking.
    """

    feedback: FeedbackRecord = Field(description="The feedback record")
    similarity_score: float = Field(
        description="Similarity score (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    rank: int = Field(description="Rank in search results (1-based)", ge=1)


class FeedbackStats(BaseModel):
    """Aggregated feedback statistics.

    Provides analytics on feedback collection for monitoring and improvement.
    """

    total_count: int = Field(default=0, description="Total feedback records")
    helpful_count: int = Field(default=0, description="Number of helpful ratings")
    not_helpful_count: int = Field(
        default=0, description="Number of not helpful ratings"
    )
    neutral_count: int = Field(default=0, description="Number of neutral ratings")
    helpful_percentage: float = Field(
        default=0.0, description="Percentage of helpful feedback", ge=0.0, le=100.0
    )
    not_helpful_percentage: float = Field(
        default=0.0, description="Percentage of not helpful feedback", ge=0.0, le=100.0
    )
    avg_rating: Optional[float] = Field(
        default=None,
        description="Average numeric rating if applicable",
        ge=1.0,
        le=5.0,
    )
    feedback_over_time: Optional[Dict[str, int]] = Field(
        default=None, description="Feedback counts by date (ISO date string keys)"
    )
    most_common_issues: Optional[List[str]] = Field(
        default=None, description="Most frequently mentioned issues from comments"
    )

    @classmethod
    def from_feedback_list(cls, feedback_list: List[FeedbackRecord]) -> "FeedbackStats":
        """Calculate statistics from a list of feedback records.

        Args:
            feedback_list: List of feedback records to analyze

        Returns:
            FeedbackStats with calculated statistics
        """
        total = len(feedback_list)
        if total == 0:
            return cls()

        helpful = sum(1 for f in feedback_list if f.rating == FeedbackRating.HELPFUL)
        not_helpful = sum(
            1 for f in feedback_list if f.rating == FeedbackRating.NOT_HELPFUL
        )
        neutral = sum(1 for f in feedback_list if f.rating == FeedbackRating.NEUTRAL)

        helpful_pct = (helpful / total * 100) if total > 0 else 0.0
        not_helpful_pct = (not_helpful / total * 100) if total > 0 else 0.0

        # Calculate feedback over time
        feedback_by_date: Dict[str, int] = {}
        for feedback in feedback_list:
            if feedback.timestamp:
                try:
                    date = datetime.fromisoformat(
                        feedback.timestamp.replace("Z", "+00:00")
                    )
                    date_key = date.date().isoformat()
                    feedback_by_date[date_key] = feedback_by_date.get(date_key, 0) + 1
                except (ValueError, AttributeError):
                    pass

        return cls(
            total_count=total,
            helpful_count=helpful,
            not_helpful_count=not_helpful,
            neutral_count=neutral,
            helpful_percentage=helpful_pct,
            not_helpful_percentage=not_helpful_pct,
            feedback_over_time=feedback_by_date if feedback_by_date else None,
        )
