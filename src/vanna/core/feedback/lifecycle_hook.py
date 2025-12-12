"""
Feedback collection lifecycle hook.

This module provides a lifecycle hook that can automatically collect
feedback context and prompt users for feedback after responses.
"""

from typing import TYPE_CHECKING, Optional

from ..lifecycle import LifecycleHook

if TYPE_CHECKING:
    from ..storage import Conversation
    from ..tool import Tool, ToolContext, ToolResult
    from ..user import User


class FeedbackCollectionHook(LifecycleHook):
    """Lifecycle hook for automatic feedback collection.

    This hook can be used to:
    - Track message context for feedback linking
    - Log feedback-related events
    - Trigger feedback prompts based on conditions

    Note: For most use cases, the FeedbackWorkflowHandler is sufficient.
    This hook is for advanced scenarios requiring lifecycle integration.

    Example:
        from vanna.core.feedback import FeedbackCollectionHook

        hook = FeedbackCollectionHook()

        agent = Agent(
            llm_service=llm,
            tool_registry=tools,
            user_resolver=resolver,
            agent_memory=memory,
            lifecycle_hooks=[hook]  # Add feedback hook
        )
    """

    def __init__(self, log_feedback_events: bool = True):
        """Initialize the feedback collection hook.

        Args:
            log_feedback_events: Whether to log feedback-related events
        """
        self.log_feedback_events = log_feedback_events
        self._message_context_cache = {}

    async def before_message(self, user: "User", message: str) -> Optional[str]:
        """Called before processing a user message.

        Args:
            user: User sending the message
            message: Original message content

        Returns:
            Modified message string, or None to keep original
        """
        # Log if this is a feedback-related message
        if self.log_feedback_events:
            if any(
                keyword in message.lower()
                for keyword in ["feedback", "__feedback_"]
            ):
                import logging

                logger = logging.getLogger(__name__)
                logger.info(f"Feedback interaction from user {user.id}")

        return None

    async def after_message(self, conversation: "Conversation") -> None:
        """Called after message has been fully processed.

        This can be used to cache message context for feedback linking.

        Args:
            conversation: Final conversation state
        """
        # Cache the last message context for potential feedback
        if conversation.messages:
            last_message = conversation.messages[-1]
            if last_message.role == "assistant":
                # Store context for feedback linking
                self._message_context_cache[conversation.id] = {
                    "content": last_message.content,
                    "timestamp": "now",  # Could add actual timestamp
                }

    async def before_tool(self, tool: "Tool", context: "ToolContext") -> None:
        """Called before tool execution.

        Args:
            tool: Tool about to be executed
            context: Tool execution context
        """
        # Could track tool usage for feedback context
        pass

    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        """Called after tool execution.

        This could be used to add feedback UI to tool results,
        but it's generally better to handle this in the agent or workflow handler.

        Args:
            result: Result from tool execution

        Returns:
            Modified ToolResult, or None to keep original
        """
        # Don't modify tool results here
        # Feedback UI is better handled in FeedbackWorkflowHandler
        return None

    def get_cached_context(self, conversation_id: str) -> Optional[dict]:
        """Get cached message context for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Cached context dict or None
        """
        return self._message_context_cache.get(conversation_id)

    def clear_cache(self, conversation_id: Optional[str] = None) -> None:
        """Clear cached message context.

        Args:
            conversation_id: Optional specific conversation to clear,
                           or None to clear all
        """
        if conversation_id:
            self._message_context_cache.pop(conversation_id, None)
        else:
            self._message_context_cache.clear()
