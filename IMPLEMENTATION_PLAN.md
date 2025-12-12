# Vanna 2.0 Custom Feedback System - Implementation Plan

## Executive Summary

Kế hoạch này mô tả cách tích hợp một **feedback system** toàn diện vào Vanna 2.0 framework. Feedback system cho phép:
- Thu thập phản hồi từ users về chất lượng câu trả lời
- Lưu trữ và phân tích feedback data
- Sử dụng feedback để cải thiện responses trong tương lai
- Hiển thị feedback UI components cho users

**Approach:** Extend existing Agent thay vì tạo Agent mới, sử dụng 7 extensibility points của framework.

---

## 1. Architectural Decision: Extend vs Create New

### ✅ **QUYẾT ĐỊNH: EXTEND EXISTING AGENT**

**Lý do:**

1. **Framework đã có 7 extensibility points** được thiết kế cho use cases như này:
   - `lifecycle_hooks` - Hook vào feedback collection
   - `workflow_handler` - Handle feedback commands
   - Custom capabilities - Feedback storage
   - Custom components - Feedback UI
   - Custom tools - Feedback operations
   - `llm_context_enhancer` - Use feedback to improve prompts
   - `observability_provider` - Track feedback metrics

2. **Tạo Agent mới sẽ:**
   - ❌ Duplicate code
   - ❌ Mất compatibility với existing integrations
   - ❌ Phải maintain 2 code paths
   - ❌ Không tận dụng được existing infrastructure

3. **Extend existing Agent sẽ:**
   - ✅ Reuse existing infrastructure
   - ✅ Maintain backward compatibility
   - ✅ Plug-and-play integration
   - ✅ Follow framework patterns
   - ✅ Easy to test and maintain

**Implementation Strategy:**
```
Existing Agent + Custom Extensions
    ├─ FeedbackCapability (storage)
    ├─ FeedbackWorkflowHandler (commands)
    ├─ FeedbackComponents (UI)
    ├─ FeedbackTools (operations)
    ├─ FeedbackLifecycleHook (auto-collection)
    ├─ FeedbackContextEnhancer (LLM improvement)
    └─ FeedbackObservabilityProvider (metrics)
```

---

## 2. Custom Feedback Flow Logic

### 2.1. High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Interaction Flow                        │
└─────────────────────────────────────────────────────────────────┘

1. USER ASKS QUESTION
   ↓
2. AGENT GENERATES RESPONSE (with tool execution, SQL, charts, etc.)
   ↓
3. FEEDBACK UI COMPONENT DISPLAYED
   │
   ├─ 👍 Helpful button
   ├─ 👎 Not helpful button
   └─ 💬 Detailed feedback textarea
   ↓
4. USER CLICKS FEEDBACK BUTTON OR TYPES /feedback
   ↓
5. FEEDBACKWORKFLOWHANDLER HANDLES THE INPUT
   ↓
6. FEEDBACK STORED IN FEEDBACKCAPABILITY
   │
   ├─ Store feedback record (rating, comment, context)
   ├─ Link to conversation, message, tools used
   ├─ Store timestamp, user_id
   └─ Calculate feedback metrics
   ↓
7. CONFIRMATION UI SHOWN TO USER
   ↓
8. FEEDBACKCONTEXTENHANCER USES FEEDBACK FOR FUTURE QUERIES
   │
   ├─ Search similar queries with feedback
   ├─ Inject learnings into system prompt
   └─ Improve tool selection based on feedback
```

### 2.2. Detailed Component Interactions

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   User       │────▶│ WorkflowHandler  │────▶│ FeedbackTool     │
│              │     │ (detect feedback)│     │ (execute save)   │
└──────────────┘     └──────────────────┘     └──────────────────┘
                              │                         │
                              │                         ▼
                              │                ┌──────────────────┐
                              │                │FeedbackCapability│
                              │                │ (storage layer)  │
                              │                └──────────────────┘
                              ▼                         │
                     ┌──────────────────┐              │
                     │  UiComponent     │◀─────────────┘
                     │  (confirmation)  │
                     └──────────────────┘

                             LATER...

┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ User asks    │────▶│ContextEnhancer   │────▶│FeedbackCapability│
│ new question │     │ (enhance prompt) │     │ (search similar) │
└──────────────┘     └──────────────────┘     └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  Enhanced LLM    │
                     │  with feedback   │
                     │  context         │
                     └──────────────────┘
```

### 2.3. Data Flow

```
FEEDBACK INPUT:
    User interaction → FeedbackTool → FeedbackCapability.save_feedback()

FEEDBACK STORAGE:
    {
        feedback_id: uuid
        user_id: string
        conversation_id: string
        message_id: string (optional, for linking to specific message)
        rating: "helpful" | "not_helpful" | "neutral"
        comment: string (optional detailed feedback)
        timestamp: ISO datetime
        context: {
            question: string (original user question)
            response: string (agent's response)
            tools_used: [tool names]
            execution_time_ms: float
        }
        metadata: {
            user_groups: [strings]
            session_id: string
            source: "button" | "command" | "auto"
        }
    }

FEEDBACK RETRIEVAL:
    Similar query → FeedbackCapability.search_similar_feedback()
        → Returns feedback records with similarity scores
        → Used by ContextEnhancer to improve prompts
```

---

## 3. Pseudo-Code for Data Processing

### 3.1. FeedbackCapability (Storage Layer)

```python
# src/vanna/capabilities/user_feedback/base.py

class FeedbackCapability(ABC):
    """Abstract interface for feedback storage and retrieval"""

    @abstractmethod
    async def save_feedback(
        user_id: str,
        conversation_id: str,
        rating: FeedbackRating,
        context: FeedbackContext,
        comment: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> FeedbackRecord:
        """
        Save user feedback to storage

        Pseudo-logic:
            1. Generate unique feedback_id
            2. Validate rating ("helpful" | "not_helpful" | "neutral")
            3. Create FeedbackRecord with all fields
            4. Embed question text for similarity search
            5. Store in database/vector store
            6. Update metrics (total feedback, avg rating)
            7. Return FeedbackRecord with id
        """
        pass

    @abstractmethod
    async def search_similar_feedback(
        query: str,
        limit: int = 10,
        rating_filter: Optional[FeedbackRating] = None,
        min_similarity: float = 0.7
    ) -> List[FeedbackSearchResult]:
        """
        Search for similar feedback based on query

        Pseudo-logic:
            1. Embed the query text
            2. Perform vector similarity search in feedback store
            3. Filter by rating if specified (e.g., only "helpful")
            4. Filter by similarity threshold
            5. Sort by similarity score (descending)
            6. Return top N results with scores
        """
        pass

    @abstractmethod
    async def get_feedback_stats(
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> FeedbackStats:
        """
        Get feedback statistics

        Pseudo-logic:
            1. Query feedback records with filters
            2. Calculate:
                - Total feedback count
                - Helpful count / percentage
                - Not helpful count / percentage
                - Average rating (if numeric)
                - Feedback over time (time series)
                - Most common issues (from comments)
            3. Return FeedbackStats object
        """
        pass

    @abstractmethod
    async def get_recent_feedback(
        limit: int = 20,
        rating_filter: Optional[FeedbackRating] = None
    ) -> List[FeedbackRecord]:
        """
        Get recent feedback records

        Pseudo-logic:
            1. Query feedback store
            2. Sort by timestamp DESC
            3. Filter by rating if specified
            4. Limit results
            5. Return list of FeedbackRecord
        """
        pass

    @abstractmethod
    async def delete_feedback(
        feedback_id: str
    ) -> bool:
        """
        Delete feedback by ID

        Pseudo-logic:
            1. Find feedback by ID
            2. If exists:
                - Delete from storage
                - Update metrics
                - Return True
            3. Else:
                - Return False
        """
        pass
```

### 3.2. FeedbackWorkflowHandler (Command Handling)

```python
# src/vanna/core/feedback/workflow_handler.py

class FeedbackWorkflowHandler(WorkflowHandler):
    """Handle feedback-related commands and interactions"""

    def __init__(self, feedback_capability: FeedbackCapability):
        self.feedback_capability = feedback_capability

    async def try_handle(
        agent: Agent,
        user: User,
        conversation: Conversation,
        message: str
    ) -> WorkflowResult:
        """
        Handle feedback commands

        Pseudo-logic:
            # 1. Detect feedback button click
            IF message == "__feedback_helpful__":
                CALL _handle_helpful_feedback(user, conversation)
                RETURN WorkflowResult(should_skip_llm=True, components=[...])

            IF message == "__feedback_not_helpful__":
                CALL _handle_not_helpful_feedback(user, conversation)
                RETURN WorkflowResult(should_skip_llm=True, components=[...])

            # 2. Detect feedback command
            IF message STARTS_WITH "/feedback":
                comment = EXTRACT_TEXT_AFTER("/feedback")
                CALL _save_feedback(user, conversation, rating="neutral", comment=comment)
                RETURN WorkflowResult(should_skip_llm=True, components=[confirmation])

            # 3. Detect view feedback command (admin only)
            IF message == "/view-feedback":
                IF "admin" NOT IN user.group_memberships:
                    RETURN access_denied_result

                recent_feedback = AWAIT feedback_capability.get_recent_feedback(limit=20)
                stats = AWAIT feedback_capability.get_feedback_stats()

                components = BUILD_FEEDBACK_DASHBOARD(recent_feedback, stats)
                RETURN WorkflowResult(should_skip_llm=True, components=components)

            # 4. Detect feedback stats command (admin only)
            IF message == "/feedback-stats":
                IF "admin" NOT IN user.group_memberships:
                    RETURN access_denied_result

                stats = AWAIT feedback_capability.get_feedback_stats()
                chart = BUILD_FEEDBACK_CHART(stats)

                RETURN WorkflowResult(should_skip_llm=True, components=[chart])

            # 5. Not a feedback command
            RETURN WorkflowResult(should_skip_llm=False)
        """
        pass

    async def _handle_helpful_feedback(user, conversation) -> List[UiComponent]:
        """
        Pseudo-logic:
            1. Get last assistant message from conversation
            2. Extract context (question, response, tools_used)
            3. Save feedback:
                - rating = "helpful"
                - context = extracted context
                - comment = None
            4. Return confirmation UI component:
                - StatusCardComponent(
                    title="Thanks for your feedback!",
                    status="success",
                    icon="👍"
                  )
        """
        pass

    async def _handle_not_helpful_feedback(user, conversation) -> List[UiComponent]:
        """
        Pseudo-logic:
            1. Get last assistant message
            2. Extract context
            3. Save feedback with rating = "not_helpful"
            4. Return UI asking for more details:
                - RichTextComponent("We're sorry this wasn't helpful...")
                - InputComponent(placeholder="Tell us what went wrong...")
        """
        pass

    async def get_starter_ui(
        agent: Agent,
        user: User,
        conversation: Conversation
    ) -> Optional[List[UiComponent]]:
        """
        Add feedback info to starter UI

        Pseudo-logic:
            IF "admin" IN user.group_memberships:
                stats = AWAIT feedback_capability.get_feedback_stats()

                RETURN [
                    RichTextComponent("Welcome! You have admin access to feedback."),
                    BadgeComponent(text=f"{stats.total_count} feedback items"),
                    ButtonComponent(label="View Feedback", value="/view-feedback")
                ]
            ELSE:
                RETURN None  # No special starter UI for regular users
        """
        pass
```

### 3.3. FeedbackLifecycleHook (Auto-Collection)

```python
# src/vanna/core/feedback/lifecycle_hook.py

class FeedbackCollectionHook(LifecycleHook):
    """Automatically add feedback UI after agent responses"""

    def __init__(self, feedback_capability: FeedbackCapability):
        self.feedback_capability = feedback_capability

    async def after_tool(self, result: ToolResult) -> Optional[ToolResult]:
        """
        Add feedback UI to tool results

        Pseudo-logic:
            # Only add feedback UI for successful results
            IF NOT result.success:
                RETURN None  # Don't modify error results

            # Check if result already has UI component
            IF result.ui_component IS None:
                RETURN None  # No UI to enhance

            # Create feedback button group
            feedback_ui = UiComponent(
                rich_component=ButtonGroupComponent(
                    buttons=[
                        Button(
                            label="👍 Helpful",
                            value="__feedback_helpful__",
                            variant="success"
                        ),
                        Button(
                            label="👎 Not Helpful",
                            value="__feedback_not_helpful__",
                            variant="error"
                        ),
                        Button(
                            label="💬 Comment",
                            value="/feedback ",
                            variant="secondary"
                        )
                    ]
                )
            )

            # Note: Cannot directly modify ToolResult
            # Instead, this would be added in agent.py after tool execution
            # This hook documents the pattern

            RETURN None  # Return None to not modify
        """
        pass

    async def after_message(self, conversation: Conversation) -> None:
        """
        Track message completion for feedback context

        Pseudo-logic:
            # Store the last assistant message context
            # So we can link feedback to the right message

            last_message = GET_LAST_ASSISTANT_MESSAGE(conversation)

            IF last_message:
                # Store in temporary cache for feedback linking
                CACHE.set(
                    key=f"last_message_{conversation.id}",
                    value={
                        "message_id": GENERATE_ID(),
                        "content": last_message.content,
                        "timestamp": NOW(),
                        "tools_used": EXTRACT_TOOL_CALLS(conversation)
                    },
                    ttl=3600  # 1 hour
                )
        """
        pass
```

### 3.4. FeedbackContextEnhancer (LLM Improvement)

```python
# src/vanna/core/feedback/context_enhancer.py

class FeedbackContextEnhancer(LlmContextEnhancer):
    """Use feedback to improve LLM responses"""

    def __init__(
        self,
        agent_memory: AgentMemory,
        feedback_capability: FeedbackCapability
    ):
        self.agent_memory = agent_memory
        self.feedback_capability = feedback_capability

    async def enhance_system_prompt(
        system_prompt: str,
        user_message: str,
        user: User
    ) -> str:
        """
        Enhance system prompt with feedback learnings

        Pseudo-logic:
            # 1. Search for similar queries with helpful feedback
            similar_helpful = AWAIT feedback_capability.search_similar_feedback(
                query=user_message,
                rating_filter="helpful",
                limit=3,
                min_similarity=0.7
            )

            # 2. Search for similar queries with negative feedback
            similar_not_helpful = AWAIT feedback_capability.search_similar_feedback(
                query=user_message,
                rating_filter="not_helpful",
                limit=3,
                min_similarity=0.7
            )

            # 3. Build feedback context section
            feedback_context = ""

            IF similar_helpful:
                feedback_context += "\n\n## Successful Query Patterns\n"
                feedback_context += "Based on user feedback, these approaches worked well for similar queries:\n"

                FOR EACH feedback IN similar_helpful:
                    feedback_context += f"- Question: {feedback.context.question}\n"
                    feedback_context += f"  Approach: {feedback.context.tools_used}\n"
                    feedback_context += f"  User rating: {feedback.rating}\n"

            IF similar_not_helpful:
                feedback_context += "\n\n## Approaches to Avoid\n"
                feedback_context += "These approaches received negative feedback:\n"

                FOR EACH feedback IN similar_not_helpful:
                    feedback_context += f"- Question: {feedback.context.question}\n"
                    feedback_context += f"  Issue: {feedback.comment or 'Not specified'}\n"

            # 4. Append to system prompt
            enhanced_prompt = system_prompt + feedback_context

            RETURN enhanced_prompt
        """
        pass

    async def enhance_user_messages(
        messages: List[LlmMessage],
        user: User
    ) -> List[LlmMessage]:
        """
        Could add feedback hints to user messages

        Pseudo-logic:
            # For now, just return unchanged
            # Could potentially add feedback metadata to messages

            RETURN messages
        """
        pass
```

### 3.5. FeedbackTools (User-Facing Tools)

```python
# src/vanna/tools/feedback/submit_feedback_tool.py

class SubmitFeedbackTool(Tool[SubmitFeedbackArgs]):
    """Allow LLM to suggest submitting feedback"""

    def __init__(self, feedback_capability: FeedbackCapability):
        self.feedback_capability = feedback_capability

    @property
    def name(self) -> str:
        return "submit_feedback"

    @property
    def description(self) -> str:
        return """Submit user feedback about the quality of responses.
        Use this when the user explicitly expresses satisfaction or dissatisfaction.
        """

    @property
    def access_groups(self) -> List[str]:
        return []  # All users can give feedback

    def get_args_schema(self) -> Type[SubmitFeedbackArgs]:
        return SubmitFeedbackArgs

    async def execute(
        context: ToolContext,
        args: SubmitFeedbackArgs
    ) -> ToolResult:
        """
        Pseudo-logic:
            # 1. Get conversation context
            conversation_id = context.conversation_id
            user_id = context.user.id

            # 2. Build feedback context
            feedback_context = FeedbackContext(
                question=args.original_question,
                response=args.response_summary,
                tools_used=EXTRACT_FROM_METADATA(context),
                execution_time_ms=CALCULATE_TIME()
            )

            # 3. Save feedback
            feedback_record = AWAIT feedback_capability.save_feedback(
                user_id=user_id,
                conversation_id=conversation_id,
                rating=args.rating,
                comment=args.comment,
                context=feedback_context,
                metadata={
                    "source": "llm_tool",
                    "user_groups": context.user.group_memberships
                }
            )

            # 4. Create confirmation UI
            ui_component = UiComponent(
                rich_component=StatusCardComponent(
                    title="Feedback Received",
                    status="success",
                    description=f"Thank you for your {args.rating} feedback!",
                    icon="✅"
                )
            )

            # 5. Return result
            RETURN ToolResult(
                success=True,
                result_for_llm=f"Feedback submitted successfully (ID: {feedback_record.id})",
                ui_component=ui_component
            )
        """
        pass


class ViewFeedbackStatsTool(Tool[ViewFeedbackStatsArgs]):
    """Admin tool to view feedback statistics"""

    @property
    def access_groups(self) -> List[str]:
        return ["admin"]  # Admin only

    async def execute(
        context: ToolContext,
        args: ViewFeedbackStatsArgs
    ) -> ToolResult:
        """
        Pseudo-logic:
            # 1. Get feedback stats
            stats = AWAIT feedback_capability.get_feedback_stats(
                start_date=args.start_date,
                end_date=args.end_date
            )

            # 2. Create visualization
            chart_data = {
                "labels": ["Helpful", "Not Helpful", "Neutral"],
                "values": [
                    stats.helpful_count,
                    stats.not_helpful_count,
                    stats.neutral_count
                ]
            }

            # 3. Create UI components
            chart = ChartComponent(
                type="pie",
                data=chart_data,
                title="Feedback Distribution"
            )

            summary = RichTextComponent(
                content=f"""
                ## Feedback Statistics

                - Total Feedback: {stats.total_count}
                - Helpful: {stats.helpful_percentage}%
                - Not Helpful: {stats.not_helpful_percentage}%
                - Average Rating: {stats.avg_rating}/5
                """,
                markdown=True
            )

            # 4. Return with UI
            RETURN ToolResult(
                success=True,
                result_for_llm=f"Feedback stats: {stats.total_count} total, {stats.helpful_percentage}% helpful",
                ui_component=UiComponent(
                    rich_component=chart,
                    simple_component=SimpleTextComponent(text="Feedback stats loaded")
                )
            )
        """
        pass
```

---

## 4. Files to Create/Modify

### 4.1. New Files to Create

#### **Capability Layer (Feedback Storage)**

```
src/vanna/capabilities/user_feedback/
├── __init__.py                     # Export public API
├── base.py                         # FeedbackCapability abstract class
├── models.py                       # Pydantic models
│   ├── FeedbackRecord
│   ├── FeedbackContext
│   ├── FeedbackRating (enum)
│   ├── FeedbackSearchResult
│   └── FeedbackStats
└── local.py                        # Local implementation (in-memory/SQLite)
```

**Priority:** 🔴 HIGH (Foundation)

**Pseudo-code for models.py:**
```python
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class FeedbackRating(str, Enum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    NEUTRAL = "neutral"

class FeedbackContext(BaseModel):
    question: str
    response: str
    tools_used: List[str]
    execution_time_ms: Optional[float] = None

class FeedbackRecord(BaseModel):
    feedback_id: Optional[str] = None
    user_id: str
    conversation_id: str
    message_id: Optional[str] = None
    rating: FeedbackRating
    comment: Optional[str] = None
    context: FeedbackContext
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class FeedbackSearchResult(BaseModel):
    feedback: FeedbackRecord
    similarity_score: float
    rank: int

class FeedbackStats(BaseModel):
    total_count: int
    helpful_count: int
    not_helpful_count: int
    neutral_count: int
    helpful_percentage: float
    not_helpful_percentage: float
    avg_rating: Optional[float] = None
    feedback_over_time: Optional[Dict[str, int]] = None
```

#### **Component Layer (Feedback UI)**

```
src/vanna/components/rich/feedback/
├── feedback_button_group.py        # ButtonGroupComponent for feedback
├── feedback_card.py                # FeedbackCardComponent
└── feedback_stats_chart.py         # FeedbackStatsChartComponent
```

**Priority:** 🟡 MEDIUM (UI Enhancement)

#### **Workflow Handler**

```
src/vanna/core/feedback/
├── __init__.py
├── workflow_handler.py             # FeedbackWorkflowHandler
└── lifecycle_hook.py               # FeedbackCollectionHook
```

**Priority:** 🔴 HIGH (Core Logic)

#### **Tools**

```
src/vanna/tools/feedback/
├── __init__.py
├── submit_feedback_tool.py         # SubmitFeedbackTool
└── view_feedback_stats_tool.py     # ViewFeedbackStatsTool (admin)
```

**Priority:** 🟢 LOW (Nice to have, can use workflow handler instead)

#### **Context Enhancer**

```
src/vanna/core/feedback/
└── context_enhancer.py             # FeedbackContextEnhancer
```

**Priority:** 🟡 MEDIUM (LLM Improvement)

#### **Integration Examples**

```
examples/
├── feedback_integration_example.py  # Complete integration example
└── feedback_analysis_example.py     # Feedback analytics example
```

**Priority:** 🟢 LOW (Documentation)

#### **Tests**

```
tests/
├── capabilities/
│   └── user_feedback/
│       ├── test_base.py
│       ├── test_local.py
│       └── test_models.py
├── feedback/
│   ├── test_workflow_handler.py
│   ├── test_lifecycle_hook.py
│   └── test_context_enhancer.py
└── tools/
    └── feedback/
        ├── test_submit_feedback_tool.py
        └── test_view_feedback_stats_tool.py
```

**Priority:** 🟡 MEDIUM (Quality Assurance)

### 4.2. Files to Modify

#### **Core Agent** (Optional Enhancement)

```
src/vanna/core/agent/agent.py
```

**Modifications:**
```python
# Line ~1040 (after final text response)
# Add feedback buttons to the response

# BEFORE:
yield UiComponent(
    rich_component=RichTextComponent(content=response.content, markdown=True),
    simple_component=SimpleTextComponent(text=response.content),
)

# AFTER:
yield UiComponent(
    rich_component=RichTextComponent(content=response.content, markdown=True),
    simple_component=SimpleTextComponent(text=response.content),
)

# Optionally add feedback buttons
if self.config.enable_feedback_collection:  # New config option
    yield UiComponent(
        rich_component=ButtonGroupComponent(
            buttons=[
                Button(label="👍 Helpful", value="__feedback_helpful__"),
                Button(label="👎 Not Helpful", value="__feedback_not_helpful__"),
            ]
        )
    )
```

**Priority:** 🟢 LOW (Can be done via lifecycle hook instead)

#### **Agent Config**

```
src/vanna/core/agent/config.py
```

**Modifications:**
```python
# Add feedback-related config options

class AgentConfig(BaseModel):
    # ... existing fields ...

    # Feedback configuration
    enable_feedback_collection: bool = Field(
        default=True,
        description="Automatically show feedback buttons after responses"
    )
    feedback_auto_save_context: bool = Field(
        default=True,
        description="Automatically save conversation context for feedback"
    )
```

**Priority:** 🟢 LOW (Optional)

#### **Component Exports**

```
src/vanna/components/rich/feedback/__init__.py
```

**Modifications:**
```python
# Export new feedback components

from .feedback_button_group import FeedbackButtonGroupComponent
from .feedback_card import FeedbackCardComponent
from .feedback_stats_chart import FeedbackStatsChartComponent

__all__ = [
    "FeedbackButtonGroupComponent",
    "FeedbackCardComponent",
    "FeedbackStatsChartComponent",
]
```

**Priority:** 🟡 MEDIUM (When components are created)

#### **Main Package Exports**

```
src/vanna/__init__.py
```

**Modifications:**
```python
# Add feedback capability exports

from .capabilities.user_feedback import (
    FeedbackCapability,
    FeedbackRecord,
    FeedbackRating,
    FeedbackStats,
    LocalFeedbackCapability,
)

# Add to __all__
__all__ = [
    # ... existing exports ...
    "FeedbackCapability",
    "FeedbackRecord",
    "FeedbackRating",
    "FeedbackStats",
    "LocalFeedbackCapability",
]
```

**Priority:** 🟡 MEDIUM (When capability is stable)

### 4.3. Integration Example File

```
examples/feedback_integration_example.py
```

**Full pseudo-code:**
```python
"""
Complete example of integrating feedback system with Vanna 2.0
"""

from vanna import Agent, AgentConfig
from vanna.capabilities.user_feedback import LocalFeedbackCapability
from vanna.core.feedback import FeedbackWorkflowHandler
from vanna.integrations.anthropic import AnthropicLlmService
# ... other imports ...

async def main():
    # 1. Create feedback capability
    feedback_capability = LocalFeedbackCapability(
        storage_path="./feedback_data.db"
    )

    # 2. Create feedback workflow handler
    feedback_handler = FeedbackWorkflowHandler(
        feedback_capability=feedback_capability
    )

    # 3. Create agent with feedback integration
    agent = Agent(
        llm_service=AnthropicLlmService(api_key="..."),
        tool_registry=tools,
        user_resolver=user_resolver,
        agent_memory=memory,

        # Integrate feedback
        workflow_handler=feedback_handler,
        config=AgentConfig(
            enable_feedback_collection=True
        )
    )

    # 4. Use agent normally
    request_context = RequestContext(...)

    async for component in agent.send_message(
        request_context,
        "Show me sales data for Q4"
    ):
        print(component)

    # 5. View feedback stats (admin)
    stats = await feedback_capability.get_feedback_stats()
    print(f"Total feedback: {stats.total_count}")
    print(f"Helpful: {stats.helpful_percentage}%")
```

**Priority:** 🟡 MEDIUM (Documentation)

---

## 5. Implementation Phases

### Phase 1: Foundation (Week 1)
**Priority:** 🔴 CRITICAL

- [ ] Create `FeedbackCapability` interface (`base.py`)
- [ ] Create Pydantic models (`models.py`)
- [ ] Implement `LocalFeedbackCapability` (in-memory/SQLite)
- [ ] Write unit tests for capability layer
- [ ] Create basic feedback UI components

**Deliverable:** Working feedback storage with local implementation

### Phase 2: Workflow Integration (Week 2)
**Priority:** 🔴 CRITICAL

- [ ] Create `FeedbackWorkflowHandler`
- [ ] Implement feedback command handling (/feedback, button clicks)
- [ ] Add feedback confirmation UIs
- [ ] Test workflow integration with Agent
- [ ] Write integration tests

**Deliverable:** Users can submit feedback via commands/buttons

### Phase 3: Auto-Collection & Display (Week 3)
**Priority:** 🟡 IMPORTANT

- [ ] Create `FeedbackCollectionHook`
- [ ] Automatically show feedback buttons after responses
- [ ] Implement admin dashboard (/view-feedback)
- [ ] Create feedback stats visualization
- [ ] Add feedback management commands (/delete-feedback)

**Deliverable:** Automated feedback collection with admin dashboard

### Phase 4: LLM Enhancement (Week 4)
**Priority:** 🟡 IMPORTANT

- [ ] Create `FeedbackContextEnhancer`
- [ ] Implement similarity search for feedback
- [ ] Inject helpful feedback into system prompts
- [ ] Add negative feedback warnings
- [ ] Measure improvement in response quality

**Deliverable:** LLM learns from user feedback

### Phase 5: Advanced Features (Week 5+)
**Priority:** 🟢 OPTIONAL

- [ ] Create LLM tools (SubmitFeedbackTool, etc.)
- [ ] Add ChromaDB integration for feedback storage
- [ ] Implement feedback analytics dashboard
- [ ] Add A/B testing support
- [ ] Create observability metrics

**Deliverable:** Production-ready feedback system with analytics

---

## 6. Testing Strategy

### 6.1. Unit Tests

```python
# Test capability
async def test_save_feedback():
    capability = LocalFeedbackCapability()
    record = await capability.save_feedback(
        user_id="user123",
        conversation_id="conv123",
        rating=FeedbackRating.HELPFUL,
        context=FeedbackContext(...)
    )
    assert record.feedback_id is not None
    assert record.rating == FeedbackRating.HELPFUL

# Test search
async def test_search_similar_feedback():
    results = await capability.search_similar_feedback(
        query="show sales data",
        limit=5
    )
    assert len(results) <= 5
    assert all(r.similarity_score >= 0.7 for r in results)
```

### 6.2. Integration Tests

```python
# Test workflow handler
async def test_feedback_workflow():
    handler = FeedbackWorkflowHandler(capability)

    result = await handler.try_handle(
        agent=mock_agent,
        user=test_user,
        conversation=test_conversation,
        message="__feedback_helpful__"
    )

    assert result.should_skip_llm == True
    assert len(result.components) > 0
    assert "Thanks" in result.components[0].rich_component.content

# Test agent integration
async def test_agent_with_feedback():
    agent = create_test_agent_with_feedback()

    # Send message
    components = []
    async for comp in agent.send_message(context, "test question"):
        components.append(comp)

    # Check feedback buttons present
    assert any("feedback" in str(c).lower() for c in components)
```

### 6.3. End-to-End Tests

```python
# Full user flow
async def test_full_feedback_flow():
    # 1. User asks question
    response = await send_question("show revenue")

    # 2. User clicks helpful
    feedback_response = await send_message("__feedback_helpful__")

    # 3. Verify feedback saved
    stats = await capability.get_feedback_stats()
    assert stats.total_count == 1
    assert stats.helpful_count == 1

    # 4. Ask similar question
    response2 = await send_question("display sales")

    # 5. Verify LLM used feedback
    # (Check system prompt contains previous helpful example)
```

---

## 7. Migration & Rollout Plan

### 7.1. Backward Compatibility

✅ **Fully backward compatible** - feedback is opt-in via configuration

```python
# Without feedback (existing behavior)
agent = Agent(
    llm_service=llm,
    tool_registry=tools,
    user_resolver=resolver,
    agent_memory=memory
)

# With feedback (new behavior)
agent = Agent(
    llm_service=llm,
    tool_registry=tools,
    user_resolver=resolver,
    agent_memory=memory,
    workflow_handler=FeedbackWorkflowHandler(feedback_capability)  # Add this
)
```

### 7.2. Deployment Strategy

**Step 1: Internal Testing**
- Deploy to dev environment
- Test with synthetic data
- Validate all flows work

**Step 2: Beta Testing**
- Enable for power users (admin group)
- Collect initial feedback about the feedback system (meta!)
- Fix bugs and improve UX

**Step 3: Gradual Rollout**
- Enable for 10% of users
- Monitor metrics and performance
- Increase to 50%, then 100%

**Step 4: Production**
- Full rollout to all users
- Monitor feedback collection rates
- Iterate based on analytics

### 7.3. Rollback Plan

If issues arise:

1. **Quick disable:** Set `enable_feedback_collection=False` in config
2. **Workflow removal:** Remove FeedbackWorkflowHandler from agent
3. **Data preservation:** Feedback data remains in storage for later reactivation

---

## 8. Success Metrics

### 8.1. Adoption Metrics

- **Feedback submission rate:** % of responses that receive feedback
  - Target: >30% of responses
- **Helpful vs Not Helpful ratio:** Balance of positive/negative feedback
  - Target: >70% helpful
- **Comment rate:** % of feedback with detailed comments
  - Target: >20% include comments

### 8.2. Quality Metrics

- **Response quality improvement:** Compare feedback before/after using FeedbackContextEnhancer
  - Target: +15% helpful rating improvement for similar queries
- **User satisfaction:** Overall satisfaction score
  - Target: >4.0/5.0 average rating
- **Issue resolution:** % of "not helpful" feedback that leads to improvements
  - Target: >50% of issues addressed

### 8.3. Technical Metrics

- **Feedback save latency:** Time to save feedback
  - Target: <100ms p95
- **Search latency:** Time to search similar feedback
  - Target: <200ms p95
- **Storage size:** Feedback database growth
  - Monitor: Plan for scaling at 1M+ records

---

## 9. Future Enhancements

### 9.1. Advanced Analytics

- Sentiment analysis on comments
- Topic modeling to identify common issues
- Trend analysis (feedback quality over time)
- User segmentation (power users vs beginners)

### 9.2. Active Learning

- Identify low-confidence responses for proactive feedback requests
- Use feedback to fine-tune LLM prompts
- A/B testing different approaches based on feedback

### 9.3. Multi-Modal Feedback

- Screenshot/image feedback for UI issues
- Voice feedback recording
- Session replay for debugging

### 9.4. Integration Extensions

- ChromaDB backend for better similarity search
- PostgreSQL backend for production scale
- Export to analytics platforms (Mixpanel, Amplitude)
- Slack/email notifications for critical feedback

---

## 10. Documentation Requirements

### 10.1. Developer Documentation

- [ ] API reference for FeedbackCapability
- [ ] Integration guide for adding feedback to existing agents
- [ ] Custom component development guide
- [ ] Testing best practices

### 10.2. User Documentation

- [ ] End-user guide for providing feedback
- [ ] Admin guide for viewing feedback dashboard
- [ ] FAQ about feedback collection and privacy

### 10.3. Architecture Documentation

- [ ] System architecture diagrams
- [ ] Data flow diagrams
- [ ] Database schema documentation
- [ ] Performance optimization guide

---

## Summary

**Approach:** Extend existing Agent with 7 extensibility points

**Core Components:**
1. ✅ FeedbackCapability - Storage and retrieval
2. ✅ FeedbackWorkflowHandler - Command handling
3. ✅ FeedbackComponents - UI display
4. ✅ FeedbackContextEnhancer - LLM improvement
5. ✅ FeedbackTools - Optional LLM tools

**Implementation Priority:**
1. 🔴 Phase 1: Foundation (capability + models)
2. 🔴 Phase 2: Workflow integration (commands + buttons)
3. 🟡 Phase 3: Auto-collection (hooks + admin dashboard)
4. 🟡 Phase 4: LLM enhancement (context enricher)
5. 🟢 Phase 5: Advanced features (analytics + tools)

**Timeline:** 4-5 weeks for production-ready implementation

**Risk:** LOW - Fully backward compatible, opt-in integration

---

*Next Step: Implement Phase 1 (Foundation) with FeedbackCapability and models.*
