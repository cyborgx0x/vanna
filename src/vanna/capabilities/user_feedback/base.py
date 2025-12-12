"""
Feedback capability interface for user feedback storage and retrieval.

This module contains the abstract base class for feedback operations,
following the same pattern as the AgentMemory interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .models import (
        FeedbackContext,
        FeedbackRating,
        FeedbackRecord,
        FeedbackSearchResult,
        FeedbackStats,
    )


class FeedbackCapability(ABC):
    """Abstract base class for user feedback operations.

    This interface provides methods for storing, retrieving, and analyzing
    user feedback about agent responses. Implementations can use different
    storage backends (in-memory, SQLite, PostgreSQL, ChromaDB, etc.).

    Example:
        class MyFeedbackCapability(FeedbackCapability):
            async def save_feedback(self, user_id, conversation_id, rating, context, ...):
                # Store feedback in database
                return feedback_record

        feedback = MyFeedbackCapability()
        record = await feedback.save_feedback(
            user_id="user123",
            conversation_id="conv456",
            rating=FeedbackRating.HELPFUL,
            context=FeedbackContext(
                question="Show sales",
                response="Here are the sales...",
                tools_used=["run_sql"]
            )
        )
    """

    @abstractmethod
    async def save_feedback(
        self,
        user_id: str,
        conversation_id: str,
        rating: "FeedbackRating",
        context: "FeedbackContext",
        comment: Optional[str] = None,
        message_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "FeedbackRecord":
        """Save user feedback to storage.

        Args:
            user_id: ID of the user providing feedback
            conversation_id: ID of the conversation
            rating: Feedback rating (helpful, not_helpful, neutral)
            context: Context of the interaction (question, response, tools used)
            comment: Optional detailed comment from user
            message_id: Optional specific message ID
            metadata: Optional additional metadata

        Returns:
            FeedbackRecord with generated feedback_id and timestamp

        Example:
            record = await feedback.save_feedback(
                user_id="alice",
                conversation_id="conv123",
                rating=FeedbackRating.HELPFUL,
                context=FeedbackContext(
                    question="Show revenue",
                    response="Q4 revenue was $1.2M",
                    tools_used=["run_sql"]
                )
            )
        """
        pass

    @abstractmethod
    async def search_similar_feedback(
        self,
        query: str,
        limit: int = 10,
        rating_filter: Optional["FeedbackRating"] = None,
        min_similarity: float = 0.7,
        user_id: Optional[str] = None,
    ) -> List["FeedbackSearchResult"]:
        """Search for similar feedback based on query text.

        Uses semantic similarity (embeddings) to find feedback about similar
        queries. This is useful for learning from past successful or unsuccessful
        interactions.

        Args:
            query: Query text to search for similar feedback
            limit: Maximum number of results to return
            rating_filter: Optional filter by rating (e.g., only "helpful")
            min_similarity: Minimum similarity threshold (0.0 to 1.0)
            user_id: Optional filter by specific user

        Returns:
            List of FeedbackSearchResult ordered by similarity score (descending)

        Example:
            results = await feedback.search_similar_feedback(
                query="show me sales data",
                rating_filter=FeedbackRating.HELPFUL,
                limit=5
            )
            for result in results:
                print(f"Similar query: {result.feedback.context.question}")
                print(f"Similarity: {result.similarity_score}")
        """
        pass

    @abstractmethod
    async def get_feedback_stats(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> "FeedbackStats":
        """Get aggregated feedback statistics.

        Args:
            user_id: Optional filter by specific user
            start_date: Optional start date for time range
            end_date: Optional end date for time range

        Returns:
            FeedbackStats with aggregated statistics

        Example:
            stats = await feedback.get_feedback_stats()
            print(f"Total feedback: {stats.total_count}")
            print(f"Helpful: {stats.helpful_percentage}%")
        """
        pass

    @abstractmethod
    async def get_recent_feedback(
        self,
        limit: int = 20,
        rating_filter: Optional["FeedbackRating"] = None,
        user_id: Optional[str] = None,
    ) -> List["FeedbackRecord"]:
        """Get recent feedback records.

        Args:
            limit: Maximum number of records to return
            rating_filter: Optional filter by rating
            user_id: Optional filter by specific user

        Returns:
            List of FeedbackRecord ordered by timestamp (most recent first)

        Example:
            recent = await feedback.get_recent_feedback(limit=10)
            for record in recent:
                print(f"{record.timestamp}: {record.rating}")
        """
        pass

    @abstractmethod
    async def delete_feedback(self, feedback_id: str) -> bool:
        """Delete a feedback record by ID.

        Args:
            feedback_id: ID of the feedback to delete

        Returns:
            True if deleted, False if not found

        Example:
            deleted = await feedback.delete_feedback("fb_123")
            if deleted:
                print("Feedback deleted successfully")
        """
        pass

    @abstractmethod
    async def clear_all_feedback(
        self,
        user_id: Optional[str] = None,
        before_date: Optional[datetime] = None,
    ) -> int:
        """Clear feedback records with optional filters.

        Args:
            user_id: Optional - only clear feedback from this user
            before_date: Optional - only clear feedback before this date

        Returns:
            Number of feedback records deleted

        Example:
            # Clear all old feedback
            count = await feedback.clear_all_feedback(
                before_date=datetime(2024, 1, 1)
            )
            print(f"Deleted {count} old feedback records")
        """
        pass
