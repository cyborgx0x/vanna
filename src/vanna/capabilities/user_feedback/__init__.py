"""
User feedback capability for collecting and analyzing user feedback.

This module provides the FeedbackCapability interface for storing and retrieving
user feedback about agent responses.
"""

from .base import FeedbackCapability
from .models import (
    FeedbackContext,
    FeedbackRating,
    FeedbackRecord,
    FeedbackSearchResult,
    FeedbackStats,
)
from .local import LocalFeedbackCapability

__all__ = [
    "FeedbackCapability",
    "FeedbackContext",
    "FeedbackRating",
    "FeedbackRecord",
    "FeedbackSearchResult",
    "FeedbackStats",
    "LocalFeedbackCapability",
]
