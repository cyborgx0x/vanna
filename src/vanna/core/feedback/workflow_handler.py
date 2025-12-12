"""
Feedback workflow handler for handling feedback commands and interactions.

This module provides a workflow handler that intercepts feedback-related
messages and commands before they reach the LLM.
"""

from typing import TYPE_CHECKING, List, Optional
import uuid

from ..workflow import WorkflowHandler, WorkflowResult

if TYPE_CHECKING:
    from ..agent.agent import Agent
    from ..user.models import User
    from ..storage import Conversation, Message
    from ...capabilities.user_feedback import (
        FeedbackCapability,
        FeedbackContext,
        FeedbackRating,
    )

# Import components
from ...components import (
    UiComponent,
    RichTextComponent,
    StatusCardComponent,
    CardComponent,
    SimpleTextComponent,
)


class FeedbackWorkflowHandler(WorkflowHandler):
    """Handle feedback-related commands and button interactions.

    This workflow handler intercepts feedback commands and button clicks,
    saves feedback to storage, and provides confirmation UIs to users.

    Supported interactions:
    - "__feedback_helpful__" - Helpful button click
    - "__feedback_not_helpful__" - Not helpful button click
    - "/feedback [comment]" - Submit feedback with comment
    - "/view-feedback" - View recent feedback (admin only)
    - "/feedback-stats" - View feedback statistics (admin only)

    Example:
        from vanna.capabilities.user_feedback import LocalFeedbackCapability
        from vanna.core.feedback import FeedbackWorkflowHandler

        feedback_capability = LocalFeedbackCapability()
        workflow_handler = FeedbackWorkflowHandler(feedback_capability)

        agent = Agent(
            llm_service=llm,
            tool_registry=tools,
            user_resolver=resolver,
            agent_memory=memory,
            workflow_handler=workflow_handler  # Add feedback handler
        )
    """

    def __init__(
        self,
        feedback_capability: "FeedbackCapability",
        show_feedback_prompts: bool = True,
    ):
        """Initialize the feedback workflow handler.

        Args:
            feedback_capability: FeedbackCapability instance for storage
            show_feedback_prompts: Whether to show feedback prompts in UI
        """
        self.feedback_capability = feedback_capability
        self.show_feedback_prompts = show_feedback_prompts

    async def try_handle(
        self,
        agent: "Agent",
        user: "User",
        conversation: "Conversation",
        message: str,
    ) -> WorkflowResult:
        """Attempt to handle feedback-related messages.

        Args:
            agent: Agent instance
            user: User sending the message
            conversation: Current conversation
            message: User's message

        Returns:
            WorkflowResult with should_skip_llm=True if handled,
            or should_skip_llm=False to continue to LLM
        """
        # Handle helpful button click
        if message.strip() == "__feedback_helpful__":
            return await self._handle_helpful_feedback(user, conversation)

        # Handle not helpful button click
        if message.strip() == "__feedback_not_helpful__":
            return await self._handle_not_helpful_feedback(user, conversation)

        # Handle feedback command with comment
        if message.strip().lower().startswith("/feedback"):
            comment = message.strip()[9:].strip()  # Extract after "/feedback"
            return await self._handle_feedback_command(user, conversation, comment)

        # Handle view feedback command (admin only)
        if message.strip().lower() in ["/view-feedback", "view-feedback"]:
            if "admin" not in user.group_memberships:
                return self._access_denied_result()
            return await self._handle_view_feedback(user)

        # Handle feedback stats command (admin only)
        if message.strip().lower() in ["/feedback-stats", "feedback-stats"]:
            if "admin" not in user.group_memberships:
                return self._access_denied_result()
            return await self._handle_feedback_stats(user)

        # Not a feedback command, continue to LLM
        return WorkflowResult(should_skip_llm=False)

    async def get_starter_ui(
        self,
        agent: "Agent",
        user: "User",
        conversation: "Conversation",
    ) -> Optional[List[UiComponent]]:
        """Provide starter UI with feedback information for admins.

        Args:
            agent: Agent instance
            user: User starting conversation
            conversation: New conversation

        Returns:
            List of UI components or None
        """
        # Only show for admins
        if "admin" not in user.group_memberships:
            return None

        # Get feedback stats
        stats = await self.feedback_capability.get_feedback_stats()

        if stats.total_count == 0:
            return None

        # Create info card
        content = (
            f"**Feedback System Active**\n\n"
            f"Total feedback collected: {stats.total_count}\n"
            f"Helpful: {stats.helpful_percentage:.1f}%\n"
            f"Not helpful: {stats.not_helpful_percentage:.1f}%"
        )

        card = UiComponent(
            rich_component=CardComponent(
                title="💬 Feedback Overview",
                content=content,
                icon="📊",
                status="info",
                markdown=True,
                actions=[
                    {
                        "label": "View Feedback",
                        "action": "/view-feedback",
                        "variant": "secondary",
                    },
                    {
                        "label": "View Stats",
                        "action": "/feedback-stats",
                        "variant": "secondary",
                    },
                ],
            ),
            simple_component=None,
        )

        return [card]

    async def _handle_helpful_feedback(
        self,
        user: "User",
        conversation: "Conversation",
    ) -> WorkflowResult:
        """Handle helpful feedback button click.

        Args:
            user: User providing feedback
            conversation: Current conversation

        Returns:
            WorkflowResult with confirmation UI
        """
        # Extract context from last assistant message
        context = self._extract_feedback_context(conversation)

        if not context:
            return WorkflowResult(
                should_skip_llm=True,
                components=[
                    self._create_error_component(
                        "Could not find a message to provide feedback for."
                    )
                ],
            )

        # Save feedback
        await self.feedback_capability.save_feedback(
            user_id=user.id,
            conversation_id=conversation.id,
            rating=FeedbackRating.HELPFUL,
            context=context,
            metadata={"source": "button", "user_groups": user.group_memberships},
        )

        # Create confirmation UI
        confirmation = UiComponent(
            rich_component=StatusCardComponent(
                title="Thanks for your feedback!",
                status="success",
                description="Your positive feedback helps us improve.",
                icon="👍",
            ),
            simple_component=SimpleTextComponent(
                text="Thanks for your feedback! (Helpful)"
            ),
        )

        return WorkflowResult(should_skip_llm=True, components=[confirmation])

    async def _handle_not_helpful_feedback(
        self,
        user: "User",
        conversation: "Conversation",
    ) -> WorkflowResult:
        """Handle not helpful feedback button click.

        Args:
            user: User providing feedback
            conversation: Current conversation

        Returns:
            WorkflowResult with prompt for more details
        """
        # Extract context from last assistant message
        context = self._extract_feedback_context(conversation)

        if not context:
            return WorkflowResult(
                should_skip_llm=True,
                components=[
                    self._create_error_component(
                        "Could not find a message to provide feedback for."
                    )
                ],
            )

        # Save feedback
        await self.feedback_capability.save_feedback(
            user_id=user.id,
            conversation_id=conversation.id,
            rating=FeedbackRating.NOT_HELPFUL,
            context=context,
            metadata={"source": "button", "user_groups": user.group_memberships},
        )

        # Create UI asking for more details
        response_text = (
            "# Thanks for your feedback\n\n"
            "We're sorry this response wasn't helpful. "
            "To help us improve, you can:\n\n"
            "- Type `/feedback [your comment]` to tell us what went wrong\n"
            "- Try rephrasing your question\n"
            "- Ask me to try a different approach"
        )

        response = UiComponent(
            rich_component=RichTextComponent(content=response_text, markdown=True),
            simple_component=SimpleTextComponent(
                text="Thanks for your feedback. Type '/feedback [comment]' to provide details."
            ),
        )

        return WorkflowResult(should_skip_llm=True, components=[response])

    async def _handle_feedback_command(
        self,
        user: "User",
        conversation: "Conversation",
        comment: str,
    ) -> WorkflowResult:
        """Handle /feedback command with optional comment.

        Args:
            user: User providing feedback
            conversation: Current conversation
            comment: User's comment (may be empty)

        Returns:
            WorkflowResult with confirmation UI
        """
        # Extract context
        context = self._extract_feedback_context(conversation)

        if not context:
            return WorkflowResult(
                should_skip_llm=True,
                components=[
                    self._create_error_component(
                        "Could not find a message to provide feedback for."
                    )
                ],
            )

        # Determine rating based on comment sentiment
        # For now, default to neutral when using command
        rating = FeedbackRating.NEUTRAL

        # Save feedback with comment
        await self.feedback_capability.save_feedback(
            user_id=user.id,
            conversation_id=conversation.id,
            rating=rating,
            context=context,
            comment=comment if comment else None,
            metadata={"source": "command", "user_groups": user.group_memberships},
        )

        # Create confirmation
        confirmation = UiComponent(
            rich_component=StatusCardComponent(
                title="Feedback Received",
                status="success",
                description=(
                    f"Thank you for your detailed feedback: \"{comment}\""
                    if comment
                    else "Thank you for your feedback!"
                ),
                icon="💬",
            ),
            simple_component=SimpleTextComponent(text="Feedback received. Thank you!"),
        )

        return WorkflowResult(should_skip_llm=True, components=[confirmation])

    async def _handle_view_feedback(self, user: "User") -> WorkflowResult:
        """Handle view feedback command (admin only).

        Args:
            user: Admin user requesting feedback view

        Returns:
            WorkflowResult with feedback list UI
        """
        # Get recent feedback
        recent_feedback = await self.feedback_capability.get_recent_feedback(limit=20)

        if not recent_feedback:
            return WorkflowResult(
                should_skip_llm=True,
                components=[
                    UiComponent(
                        rich_component=RichTextComponent(
                            content="# 💬 Recent Feedback\n\nNo feedback collected yet.",
                            markdown=True,
                        ),
                        simple_component=None,
                    )
                ],
            )

        components = []

        # Header
        header = UiComponent(
            rich_component=RichTextComponent(
                content=f"# 💬 Recent Feedback\n\nShowing {len(recent_feedback)} most recent feedback items:",
                markdown=True,
            ),
            simple_component=None,
        )
        components.append(header)

        # Create card for each feedback
        for feedback in recent_feedback:
            rating_icon = {
                FeedbackRating.HELPFUL: "👍",
                FeedbackRating.NOT_HELPFUL: "👎",
                FeedbackRating.NEUTRAL: "💬",
            }.get(feedback.rating, "💬")

            card_content = f"**User:** {feedback.user_id}\n\n"
            card_content += f"**Question:** {feedback.context.question}\n\n"
            card_content += f"**Rating:** {rating_icon} {feedback.rating.value}\n\n"

            if feedback.comment:
                card_content += f"**Comment:** {feedback.comment}\n\n"

            if feedback.context.tools_used:
                card_content += (
                    f"**Tools Used:** {', '.join(feedback.context.tools_used)}\n\n"
                )

            card_content += f"**Timestamp:** {feedback.timestamp}\n\n"
            card_content += f"**ID:** `{feedback.feedback_id}`"

            card = UiComponent(
                rich_component=CardComponent(
                    title=f"{rating_icon} Feedback",
                    content=card_content,
                    markdown=True,
                    status=(
                        "success"
                        if feedback.rating == FeedbackRating.HELPFUL
                        else "error"
                        if feedback.rating == FeedbackRating.NOT_HELPFUL
                        else "info"
                    ),
                ),
                simple_component=None,
            )
            components.append(card)

        return WorkflowResult(should_skip_llm=True, components=components)

    async def _handle_feedback_stats(self, user: "User") -> WorkflowResult:
        """Handle feedback stats command (admin only).

        Args:
            user: Admin user requesting stats

        Returns:
            WorkflowResult with stats UI
        """
        # Get stats
        stats = await self.feedback_capability.get_feedback_stats()

        # Create stats display
        stats_content = "# 📊 Feedback Statistics\n\n"
        stats_content += f"**Total Feedback:** {stats.total_count}\n\n"

        if stats.total_count > 0:
            stats_content += "## Rating Breakdown\n\n"
            stats_content += (
                f"- 👍 **Helpful:** {stats.helpful_count} "
                f"({stats.helpful_percentage:.1f}%)\n"
            )
            stats_content += (
                f"- 👎 **Not Helpful:** {stats.not_helpful_count} "
                f"({stats.not_helpful_percentage:.1f}%)\n"
            )
            stats_content += f"- 💬 **Neutral:** {stats.neutral_count}\n\n"

            if stats.feedback_over_time:
                stats_content += "## Feedback Over Time\n\n"
                for date, count in sorted(stats.feedback_over_time.items())[:10]:
                    stats_content += f"- {date}: {count} feedback items\n"
        else:
            stats_content += "*No feedback collected yet.*"

        stats_ui = UiComponent(
            rich_component=RichTextComponent(content=stats_content, markdown=True),
            simple_component=SimpleTextComponent(
                text=f"Feedback Stats: {stats.total_count} total, "
                f"{stats.helpful_percentage:.1f}% helpful"
            ),
        )

        return WorkflowResult(should_skip_llm=True, components=[stats_ui])

    def _extract_feedback_context(
        self, conversation: "Conversation"
    ) -> Optional["FeedbackContext"]:
        """Extract feedback context from conversation.

        Args:
            conversation: Conversation to extract context from

        Returns:
            FeedbackContext if found, None otherwise
        """
        from ...capabilities.user_feedback import FeedbackContext

        # Find last user message and last assistant message
        last_user_message = None
        last_assistant_message = None

        for message in reversed(conversation.messages):
            if message.role == "user" and last_user_message is None:
                last_user_message = message
            elif message.role == "assistant" and last_assistant_message is None:
                last_assistant_message = message

            if last_user_message and last_assistant_message:
                break

        if not last_user_message or not last_assistant_message:
            return None

        # Extract tools used from tool calls in conversation
        tools_used = []
        for message in conversation.messages:
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.name not in tools_used:
                        tools_used.append(tool_call.name)

        # Create context
        return FeedbackContext(
            question=last_user_message.content or "",
            response=last_assistant_message.content or "",
            tools_used=tools_used,
        )

    def _create_error_component(self, message: str) -> UiComponent:
        """Create error UI component.

        Args:
            message: Error message

        Returns:
            UiComponent with error display
        """
        return UiComponent(
            rich_component=StatusCardComponent(
                title="Error",
                status="error",
                description=message,
                icon="⚠️",
            ),
            simple_component=SimpleTextComponent(text=f"Error: {message}"),
        )

    def _access_denied_result(self) -> WorkflowResult:
        """Create access denied result.

        Returns:
            WorkflowResult with access denied UI
        """
        return WorkflowResult(
            should_skip_llm=True,
            components=[
                UiComponent(
                    rich_component=RichTextComponent(
                        content=(
                            "# 🔒 Access Denied\n\n"
                            "This command is only available to administrators.\n\n"
                            "If you need access to feedback management features, "
                            "please contact your system administrator."
                        ),
                        markdown=True,
                    ),
                    simple_component=SimpleTextComponent(
                        text="Access denied. Admin only."
                    ),
                )
            ],
        )
