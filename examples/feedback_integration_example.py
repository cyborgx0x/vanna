"""
Complete example of integrating the feedback system with Vanna 2.0.

This example demonstrates:
1. Setting up FeedbackCapability for storage
2. Creating FeedbackWorkflowHandler
3. Integrating with Agent
4. Using feedback to improve responses
"""

import asyncio
from vanna import Agent, AgentConfig
from vanna.capabilities.user_feedback import (
    LocalFeedbackCapability,
    FeedbackRating,
    FeedbackContext,
)
from vanna.core.feedback import FeedbackWorkflowHandler, FeedbackCollectionHook
from vanna.core.registry import ToolRegistry
from vanna.core.user import User, UserResolver, RequestContext
from vanna.capabilities.agent_memory import AgentMemory
from vanna.integrations.local import MemoryConversationStore


# Mock implementations for example
class MockLlmService:
    """Mock LLM service for example."""

    async def send_request(self, request):
        """Mock send request."""
        from vanna.core.llm import LlmResponse

        return LlmResponse(content="Here is your data analysis result.")

    async def stream_request(self, request):
        """Mock stream request."""
        from vanna.core.llm import LlmStreamChunk

        yield LlmStreamChunk(content="Here is your data analysis result.")


class MockUserResolver(UserResolver):
    """Mock user resolver for example."""

    async def resolve_user(self, request_context: RequestContext) -> User:
        """Return a test user."""
        return User(
            id="test_user_123",
            email="test@example.com",
            group_memberships=["admin", "user"],
        )


class MockAgentMemory(AgentMemory):
    """Mock agent memory for example."""

    async def save_tool_usage(self, question, tool_name, args, context, success=True, metadata=None):
        pass

    async def save_text_memory(self, content, context):
        from vanna.capabilities.agent_memory.models import TextMemory
        return TextMemory(content=content)

    async def search_similar_usage(self, question, context, limit=10, similarity_threshold=0.7, tool_name_filter=None):
        return []

    async def search_text_memories(self, query, context, limit=10, similarity_threshold=0.7):
        return []

    async def get_recent_memories(self, context, limit=10):
        return []

    async def get_recent_text_memories(self, context, limit=10):
        return []

    async def delete_by_id(self, context, memory_id):
        return False

    async def delete_text_memory(self, context, memory_id):
        return False

    async def clear_memories(self, context, tool_name=None, before_date=None):
        return 0


async def example_basic_feedback():
    """Example 1: Basic feedback collection."""
    print("=" * 70)
    print("Example 1: Basic Feedback Collection")
    print("=" * 70)

    # 1. Create feedback capability
    feedback_capability = LocalFeedbackCapability()

    # 2. Save some example feedback
    record1 = await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=FeedbackContext(
            question="Show me Q4 sales data",
            response="Q4 sales totaled $1.2M across all regions...",
            tools_used=["run_sql", "visualize_data"],
            execution_time_ms=245.5,
        ),
        comment="Great visualization!",
    )
    print(f"✓ Saved helpful feedback: {record1.feedback_id}")

    record2 = await feedback_capability.save_feedback(
        user_id="bob",
        conversation_id="conv_002",
        rating=FeedbackRating.NOT_HELPFUL,
        context=FeedbackContext(
            question="Display revenue by region",
            response="Here is the revenue data...",
            tools_used=["run_sql"],
        ),
        comment="Missing chart visualization",
    )
    print(f"✓ Saved not helpful feedback: {record2.feedback_id}")

    # 3. Get statistics
    stats = await feedback_capability.get_feedback_stats()
    print(f"\n📊 Feedback Stats:")
    print(f"   Total: {stats.total_count}")
    print(f"   Helpful: {stats.helpful_count} ({stats.helpful_percentage:.1f}%)")
    print(f"   Not Helpful: {stats.not_helpful_count} ({stats.not_helpful_percentage:.1f}%)")

    # 4. Search similar feedback
    results = await feedback_capability.search_similar_feedback(
        query="show sales data",
        rating_filter=FeedbackRating.HELPFUL,
    )
    print(f"\n🔍 Similar helpful feedback for 'show sales data':")
    for result in results:
        print(f"   - {result.feedback.context.question} (similarity: {result.similarity_score:.2f})")

    print()


async def example_agent_integration():
    """Example 2: Full agent integration with feedback."""
    print("=" * 70)
    print("Example 2: Agent Integration with Feedback")
    print("=" * 70)

    # 1. Create feedback capability
    feedback_capability = LocalFeedbackCapability()

    # 2. Create feedback workflow handler
    workflow_handler = FeedbackWorkflowHandler(
        feedback_capability=feedback_capability,
        show_feedback_prompts=True,
    )

    # 3. Create feedback collection hook (optional)
    feedback_hook = FeedbackCollectionHook(log_feedback_events=True)

    # 4. Create agent with feedback integration
    agent = Agent(
        llm_service=MockLlmService(),
        tool_registry=ToolRegistry(),
        user_resolver=MockUserResolver(),
        agent_memory=MockAgentMemory(),
        conversation_store=MemoryConversationStore(),
        config=AgentConfig(),
        workflow_handler=workflow_handler,
        lifecycle_hooks=[feedback_hook],
    )

    print("✓ Created agent with feedback integration")

    # 5. Simulate user interaction
    request_context = RequestContext(metadata={})

    print("\n📤 Sending user message...")
    component_count = 0
    async for component in agent.send_message(
        request_context,
        "Show me sales data for Q4",
    ):
        component_count += 1

    print(f"✓ Received {component_count} UI components")

    # 6. Simulate feedback submission
    print("\n👍 User clicks 'Helpful' button...")
    async for component in agent.send_message(
        request_context,
        "__feedback_helpful__",
        conversation_id=None,  # Would use actual conversation_id
    ):
        if hasattr(component, "rich_component"):
            if hasattr(component.rich_component, "title"):
                print(f"   {component.rich_component.title}")

    # 7. Check feedback was saved
    stats = await feedback_capability.get_feedback_stats()
    print(f"\n📊 Updated stats: {stats.total_count} feedback items")

    print()


async def example_admin_features():
    """Example 3: Admin feedback management."""
    print("=" * 70)
    print("Example 3: Admin Feedback Management")
    print("=" * 70)

    # Setup
    feedback_capability = LocalFeedbackCapability()
    workflow_handler = FeedbackWorkflowHandler(feedback_capability)

    agent = Agent(
        llm_service=MockLlmService(),
        tool_registry=ToolRegistry(),
        user_resolver=MockUserResolver(),
        agent_memory=MockAgentMemory(),
        conversation_store=MemoryConversationStore(),
        workflow_handler=workflow_handler,
    )

    # Add some feedback
    await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_001",
        rating=FeedbackRating.HELPFUL,
        context=FeedbackContext(
            question="Show sales",
            response="Sales data...",
            tools_used=["run_sql"],
        ),
    )

    # Admin views feedback
    print("🔒 Admin user viewing feedback...")
    request_context = RequestContext(metadata={})

    component_count = 0
    async for component in agent.send_message(
        request_context,
        "/view-feedback",
    ):
        component_count += 1

    print(f"✓ Displayed {component_count} feedback components")

    # Admin views stats
    print("\n📊 Admin viewing feedback stats...")
    async for component in agent.send_message(
        request_context,
        "/feedback-stats",
    ):
        if hasattr(component, "rich_component"):
            if hasattr(component.rich_component, "content"):
                # Print first line of content
                content = component.rich_component.content
                first_line = content.split("\n")[0]
                print(f"   {first_line}")

    print()


async def example_feedback_search():
    """Example 4: Searching and analyzing feedback."""
    print("=" * 70)
    print("Example 4: Feedback Search and Analysis")
    print("=" * 70)

    feedback_capability = LocalFeedbackCapability()

    # Add diverse feedback
    queries = [
        ("Show me sales data", "helpful", "Great charts!"),
        ("Display revenue by region", "not_helpful", "Missing breakdown"),
        ("Show Q4 performance", "helpful", "Very clear"),
        ("Get sales numbers", "helpful", None),
        ("Revenue report", "not_helpful", "Too slow"),
    ]

    for question, rating, comment in queries:
        await feedback_capability.save_feedback(
            user_id="test_user",
            conversation_id=f"conv_{question[:10]}",
            rating=FeedbackRating.HELPFUL if rating == "helpful" else FeedbackRating.NOT_HELPFUL,
            context=FeedbackContext(
                question=question,
                response="Sample response...",
                tools_used=["run_sql"],
            ),
            comment=comment,
        )

    print(f"✓ Added {len(queries)} feedback items")

    # Search for similar queries
    print("\n🔍 Searching for feedback similar to 'show sales'...")
    results = await feedback_capability.search_similar_feedback(
        query="show sales",
        limit=3,
    )

    for result in results:
        print(f"\n   Rank {result.rank} (similarity: {result.similarity_score:.2f})")
        print(f"   Question: {result.feedback.context.question}")
        print(f"   Rating: {result.feedback.rating.value}")
        if result.feedback.comment:
            print(f"   Comment: {result.feedback.comment}")

    # Get helpful feedback only
    print("\n👍 Searching for only helpful feedback...")
    helpful_results = await feedback_capability.search_similar_feedback(
        query="sales data",
        rating_filter=FeedbackRating.HELPFUL,
        limit=5,
    )
    print(f"   Found {len(helpful_results)} helpful feedback items")

    # Get recent feedback
    print("\n📅 Recent feedback:")
    recent = await feedback_capability.get_recent_feedback(limit=3)
    for feedback in recent:
        print(f"   - {feedback.context.question}: {feedback.rating.value}")

    print()


async def example_feedback_lifecycle():
    """Example 5: Complete feedback lifecycle."""
    print("=" * 70)
    print("Example 5: Complete Feedback Lifecycle")
    print("=" * 70)

    feedback_capability = LocalFeedbackCapability()

    # 1. Collect feedback
    print("1️⃣ Collecting feedback...")
    record = await feedback_capability.save_feedback(
        user_id="alice",
        conversation_id="conv_lifecycle",
        rating=FeedbackRating.HELPFUL,
        context=FeedbackContext(
            question="Show Q4 sales",
            response="Q4 sales: $1.2M",
            tools_used=["run_sql", "visualize_data"],
            execution_time_ms=150.0,
        ),
        comment="Perfect!",
    )
    print(f"   ✓ Saved: {record.feedback_id}")

    # 2. Retrieve feedback
    print("\n2️⃣ Retrieving feedback...")
    recent = await feedback_capability.get_recent_feedback(limit=1)
    print(f"   ✓ Found: {recent[0].feedback_id}")
    print(f"   Rating: {recent[0].rating.value}")
    print(f"   Comment: {recent[0].comment}")

    # 3. Analyze feedback
    print("\n3️⃣ Analyzing feedback...")
    stats = await feedback_capability.get_feedback_stats()
    print(f"   Total: {stats.total_count}")
    print(f"   Helpful: {stats.helpful_percentage:.1f}%")

    # 4. Use feedback for improvements
    print("\n4️⃣ Using feedback to improve...")
    similar = await feedback_capability.search_similar_feedback(
        query="display sales",
        rating_filter=FeedbackRating.HELPFUL,
    )
    if similar:
        print(f"   ✓ Found {len(similar)} similar successful queries")
        print(f"   Tools that worked: {similar[0].feedback.context.tools_used}")

    # 5. Cleanup old feedback
    print("\n5️⃣ Cleanup (delete feedback)...")
    deleted = await feedback_capability.delete_feedback(record.feedback_id)
    print(f"   ✓ Deleted: {deleted}")

    final_count = feedback_capability.count()
    print(f"   Remaining feedback: {final_count}")

    print()


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("VANNA 2.0 FEEDBACK SYSTEM EXAMPLES")
    print("=" * 70 + "\n")

    await example_basic_feedback()
    await example_agent_integration()
    await example_admin_features()
    await example_feedback_search()
    await example_feedback_lifecycle()

    print("=" * 70)
    print("All examples completed successfully! ✨")
    print("=" * 70 + "\n")

    print("Next steps:")
    print("1. Integrate FeedbackCapability into your agent")
    print("2. Add FeedbackWorkflowHandler to handle feedback commands")
    print("3. Use feedback data to improve prompts and tool selection")
    print("4. Monitor feedback stats for quality improvements")
    print()


if __name__ == "__main__":
    asyncio.run(main())
