"""
Local in-memory implementation of FeedbackCapability.

This module provides a simple in-memory implementation for development and testing.
For production use, consider implementing a database-backed version.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from .base import FeedbackCapability
from .models import (
    FeedbackContext,
    FeedbackRating,
    FeedbackRecord,
    FeedbackSearchResult,
    FeedbackStats,
)


class LocalFeedbackCapability(FeedbackCapability):
    """In-memory implementation of FeedbackCapability.

    This implementation stores feedback in memory using a simple dictionary.
    Data is not persisted between restarts.

    For production use, consider:
    - SQLite for simple persistence
    - PostgreSQL for production scale
    - ChromaDB for better similarity search

    Example:
        feedback = LocalFeedbackCapability()

        # Save feedback
        record = await feedback.save_feedback(
            user_id="alice",
            conversation_id="conv123",
            rating=FeedbackRating.HELPFUL,
            context=FeedbackContext(
                question="Show sales",
                response="Q4 sales: $1.2M",
                tools_used=["run_sql"]
            )
        )

        # Search similar
        results = await feedback.search_similar_feedback(
            query="display revenue",
            rating_filter=FeedbackRating.HELPFUL
        )
    """

    def __init__(self):
        """Initialize the local feedback storage."""
        self._feedback_store: Dict[str, FeedbackRecord] = {}

    async def save_feedback(
        self,
        user_id: str,
        conversation_id: str,
        rating: FeedbackRating,
        context: FeedbackContext,
        comment: Optional[str] = None,
        message_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> FeedbackRecord:
        """Save user feedback to in-memory storage.

        Args:
            user_id: ID of the user providing feedback
            conversation_id: ID of the conversation
            rating: Feedback rating
            context: Context of the interaction
            comment: Optional detailed comment
            message_id: Optional specific message ID
            metadata: Optional additional metadata

        Returns:
            FeedbackRecord with generated ID and timestamp
        """
        # Generate unique ID
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"

        # Create timestamp
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Create record
        record = FeedbackRecord(
            feedback_id=feedback_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            rating=rating,
            comment=comment,
            context=context,
            timestamp=timestamp,
            metadata=metadata or {},
        )

        # Store in memory
        self._feedback_store[feedback_id] = record

        return record

    async def search_similar_feedback(
        self,
        query: str,
        limit: int = 10,
        rating_filter: Optional[FeedbackRating] = None,
        min_similarity: float = 0.7,
        user_id: Optional[str] = None,
    ) -> List[FeedbackSearchResult]:
        """Search for similar feedback based on query text.

        Note: This simple implementation uses basic string matching.
        For production, implement proper embedding-based similarity search
        using ChromaDB or similar vector database.

        Args:
            query: Query text to search for
            limit: Maximum results to return
            rating_filter: Optional filter by rating
            min_similarity: Minimum similarity threshold
            user_id: Optional filter by user

        Returns:
            List of FeedbackSearchResult ordered by similarity
        """
        results = []
        query_lower = query.lower()

        for record in self._feedback_store.values():
            # Apply filters
            if rating_filter and record.rating != rating_filter:
                continue
            if user_id and record.user_id != user_id:
                continue

            # Calculate simple similarity score
            # Production implementation should use embeddings
            similarity = self._calculate_similarity(query_lower, record)

            if similarity >= min_similarity:
                results.append((similarity, record))

        # Sort by similarity (descending)
        results.sort(key=lambda x: x[0], reverse=True)

        # Limit results
        results = results[:limit]

        # Create search results with ranks
        search_results = [
            FeedbackSearchResult(
                feedback=record, similarity_score=score, rank=idx + 1
            )
            for idx, (score, record) in enumerate(results)
        ]

        return search_results

    def _calculate_similarity(self, query: str, record: FeedbackRecord) -> float:
        """Calculate similarity between query and feedback record.

        This is a simple implementation using word overlap.
        Production should use embedding-based similarity.

        Args:
            query: Query string (lowercase)
            record: Feedback record to compare

        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Get text to compare
        question = record.context.question.lower()
        response = record.context.response.lower()

        # Simple word-based similarity
        query_words = set(query.split())
        question_words = set(question.split())
        response_words = set(response.split())

        # Calculate overlap
        question_overlap = len(query_words & question_words)
        response_overlap = len(query_words & response_words)

        if len(query_words) == 0:
            return 0.0

        # Weight question overlap more than response
        similarity = (question_overlap * 2 + response_overlap) / (len(query_words) * 3)

        return min(similarity, 1.0)

    async def get_feedback_stats(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> FeedbackStats:
        """Get aggregated feedback statistics.

        Args:
            user_id: Optional filter by user
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            FeedbackStats with aggregated statistics
        """
        # Filter feedback records
        filtered_feedback = []

        for record in self._feedback_store.values():
            # Apply user filter
            if user_id and record.user_id != user_id:
                continue

            # Apply date filters
            if start_date or end_date:
                if record.timestamp:
                    try:
                        record_date = datetime.fromisoformat(
                            record.timestamp.replace("Z", "+00:00")
                        )
                        if start_date and record_date < start_date:
                            continue
                        if end_date and record_date > end_date:
                            continue
                    except (ValueError, AttributeError):
                        continue

            filtered_feedback.append(record)

        # Calculate statistics
        return FeedbackStats.from_feedback_list(filtered_feedback)

    async def get_recent_feedback(
        self,
        limit: int = 20,
        rating_filter: Optional[FeedbackRating] = None,
        user_id: Optional[str] = None,
    ) -> List[FeedbackRecord]:
        """Get recent feedback records.

        Args:
            limit: Maximum records to return
            rating_filter: Optional filter by rating
            user_id: Optional filter by user

        Returns:
            List of FeedbackRecord ordered by timestamp (descending)
        """
        # Filter records
        filtered_records = []

        for record in self._feedback_store.values():
            # Apply filters
            if rating_filter and record.rating != rating_filter:
                continue
            if user_id and record.user_id != user_id:
                continue

            filtered_records.append(record)

        # Sort by timestamp (most recent first)
        filtered_records.sort(
            key=lambda r: r.timestamp if r.timestamp else "",
            reverse=True,
        )

        # Limit results
        return filtered_records[:limit]

    async def delete_feedback(self, feedback_id: str) -> bool:
        """Delete a feedback record by ID.

        Args:
            feedback_id: ID of the feedback to delete

        Returns:
            True if deleted, False if not found
        """
        if feedback_id in self._feedback_store:
            del self._feedback_store[feedback_id]
            return True
        return False

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
        """
        to_delete = []

        for feedback_id, record in self._feedback_store.items():
            # Apply user filter
            if user_id and record.user_id != user_id:
                continue

            # Apply date filter
            if before_date and record.timestamp:
                try:
                    record_date = datetime.fromisoformat(
                        record.timestamp.replace("Z", "+00:00")
                    )
                    if record_date >= before_date:
                        continue
                except (ValueError, AttributeError):
                    continue

            to_delete.append(feedback_id)

        # Delete records
        for feedback_id in to_delete:
            del self._feedback_store[feedback_id]

        return len(to_delete)

    def get_all_feedback(self) -> List[FeedbackRecord]:
        """Get all feedback records (for testing/debugging).

        Returns:
            List of all FeedbackRecord objects
        """
        return list(self._feedback_store.values())

    def count(self) -> int:
        """Get total count of feedback records (for testing/debugging).

        Returns:
            Total number of feedback records
        """
        return len(self._feedback_store)
