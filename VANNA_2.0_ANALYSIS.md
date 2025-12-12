# Vanna-AI 2.0 Framework Analysis

## Tổng quan (Overview)

Vanna 2.0 là một framework agent-based hoàn toàn mới được thiết kế để xây dựng các AI agent có khả năng:
- Tương tác với LLM (Large Language Models)
- Thực thi tools với user-aware permissions
- Quản lý conversation history
- Stream rich UI components đến client
- Enterprise security với audit logging

---

## 1. Kiến trúc Agent-Based Framework

### 1.1. Core Components

#### **Agent (src/vanna/core/agent/agent.py)**

Agent là thành phần trung tâm điều phối toàn bộ luồng xử lý:

```python
class Agent:
    def __init__(
        self,
        llm_service: LlmService,              # LLM integration
        tool_registry: ToolRegistry,          # Tool management
        user_resolver: UserResolver,          # User authentication
        agent_memory: AgentMemory,            # RAG/memory system
        conversation_store: ConversationStore,# Conversation persistence
        config: AgentConfig,                  # Agent configuration

        # 7 extensibility points:
        lifecycle_hooks: List[LifecycleHook],
        llm_middlewares: List[LlmMiddleware],
        workflow_handler: WorkflowHandler,
        error_recovery_strategy: ErrorRecoveryStrategy,
        context_enrichers: List[ToolContextEnricher],
        llm_context_enhancer: LlmContextEnhancer,
        conversation_filters: List[ConversationFilter],
        observability_provider: ObservabilityProvider,
        audit_logger: AuditLogger,
    )
```

**Luồng xử lý chính (Main Flow):**

```
User Message
    ↓
[UserResolver] → Resolve user identity from request context
    ↓
[Lifecycle: before_message hooks] → Quota checks, logging, filtering
    ↓
[WorkflowHandler.try_handle] → Handle commands/workflows (skip LLM if handled)
    ↓ (if not handled by workflow)
[Load Conversation] → Get conversation history from store
    ↓
[Context Enrichment] → Add user prefs, metadata via ToolContextEnricher
    ↓
[Build System Prompt] → SystemPromptBuilder + LlmContextEnhancer
    ↓
[Tool Loop] (max_tool_iterations times):
    ├─ [LLM Request via Middlewares] → Caching, monitoring
    ├─ [Tool Execution]:
    │   ├─ Permission check (user groups vs tool access_groups)
    │   ├─ Argument validation (Pydantic)
    │   ├─ Argument transformation (ToolRegistry.transform_args)
    │   ├─ Lifecycle: before_tool hooks
    │   ├─ Tool.execute()
    │   ├─ Lifecycle: after_tool hooks
    │   └─ Audit logging
    └─ [Stream UI Components] → Rich/simple components to client
    ↓
[Save Conversation] → Update conversation store
    ↓
[Lifecycle: after_message hooks] → Final logging, cleanup
```

### 1.2. Tool System

#### **Tool Base Class (src/vanna/core/tool/base.py)**

```python
class Tool(ABC, Generic[T]):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """LLM-visible description"""
        pass

    @property
    def access_groups(self) -> List[str]:
        """Groups permitted to use this tool (empty = all users)"""
        return []

    @abstractmethod
    def get_args_schema(self) -> Type[T]:
        """Pydantic model for arguments"""
        pass

    @abstractmethod
    async def execute(self, context: ToolContext, args: T) -> ToolResult:
        """Execute tool with validated arguments"""
        pass
```

**ToolContext** chứa:
- `user: User` - User identity with group memberships
- `conversation_id: str` - Current conversation
- `request_id: str` - Unique request ID for tracing
- `agent_memory: AgentMemory` - RAG/memory system
- `metadata: Dict[str, Any]` - Additional context data
- `observability_provider: ObservabilityProvider` - Metrics/tracing

**ToolResult** trả về:
- `success: bool` - Execution status
- `result_for_llm: str` - Text sent back to LLM
- `ui_component: UiComponent` - Rich UI for client rendering
- `error: Optional[str]` - Error message if failed
- `metadata: Dict[str, Any]` - Additional metadata (execution time, etc.)

### 1.3. Permission System

**User Groups & Tool Access:**

```python
# User model
class User(BaseModel):
    id: str
    email: str
    group_memberships: List[str]  # ["admin", "read_sales", "write_reports"]

# Tool permission check
class RunSqlTool(Tool):
    @property
    def access_groups(self) -> List[str]:
        return ["admin", "analyst"]  # Only these groups can use this tool

# Permission logic: set intersection
user_groups = set(user.group_memberships)
tool_groups = set(tool.access_groups)
has_access = bool(user_groups & tool_groups)
```

**Argument Transformation for Row-Level Security:**

```python
class CustomToolRegistry(ToolRegistry):
    async def transform_args(
        self,
        tool: Tool[T],
        args: T,
        user: User,
        context: ToolContext
    ) -> Union[T, ToolRejection]:
        """Apply row-level security to SQL queries"""
        if isinstance(tool, RunSqlTool):
            # Modify SQL query to filter by user's accessible data
            if "analyst" in user.group_memberships:
                args.sql = f"{args.sql} WHERE department = '{user.department}'"
            return args
        return args
```

### 1.4. UI Component System

**Component Architecture:**

```python
class UiComponent(BaseModel):
    timestamp: str
    rich_component: RichComponent  # Advanced rendering
    simple_component: SimpleComponent  # Fallback rendering
```

**Rich Components** (src/vanna/components/rich/):
- `RichTextComponent` - Markdown text with formatting
- `DataFrameComponent` - Interactive tables
- `ChartComponent` - Plotly visualizations
- `StatusCardComponent` - Status indicators with icons
- `BadgeComponent` - Labels and tags
- `ProgressBarComponent` - Progress indicators
- `NotificationComponent` - Alerts and notifications
- `TaskListComponent` - Task tracking
- `ArtifactComponent` - Code blocks, SQL queries
- `ButtonComponent` - Interactive buttons
- `LogViewerComponent` - Log display

**Simple Components** (src/vanna/components/simple/):
- `SimpleTextComponent` - Plain text
- `SimpleImageComponent` - Images
- `SimpleLinkComponent` - Links

---

## 2. Integration Points for Custom Feedback

### 2.1. During Tool Execution

**Option 1: Return UI Components from Tools**

```python
class MyCustomTool(Tool[MyArgs]):
    async def execute(self, context: ToolContext, args: MyArgs) -> ToolResult:
        # Perform work
        result_data = await self.do_work(args)

        # Return with custom feedback component
        return ToolResult(
            success=True,
            result_for_llm=f"Task completed successfully: {result_data}",
            ui_component=UiComponent(
                rich_component=StatusCardComponent(
                    title="✅ Task Complete",
                    status="success",
                    description=f"Processed {result_data['count']} items",
                    metadata=result_data,
                ),
                simple_component=SimpleTextComponent(
                    text=f"Task completed: {result_data['count']} items"
                )
            )
        )
```

**Option 2: Custom Feedback Components**

Create new feedback components in `src/vanna/components/rich/feedback/`:

```python
# src/vanna/components/rich/feedback/custom_feedback.py
from ....core.rich_component import RichComponent, ComponentType

class CustomFeedbackComponent(RichComponent):
    """Custom feedback component for specific use cases"""

    type: ComponentType = ComponentType.CUSTOM_FEEDBACK
    message: str
    severity: str  # "info", "warning", "error", "success"
    details: Optional[Dict[str, Any]] = None
    action_buttons: Optional[List[Dict[str, str]]] = None

# Usage in tools:
return ToolResult(
    success=True,
    result_for_llm="Action completed",
    ui_component=UiComponent(
        rich_component=CustomFeedbackComponent(
            message="Your query returned 1000+ results",
            severity="warning",
            details={"row_count": 1523, "query_time_ms": 245},
            action_buttons=[
                {"label": "View All", "action": "view_all"},
                {"label": "Export", "action": "export"}
            ]
        ),
        simple_component=SimpleTextComponent(text="Query complete: 1523 rows")
    )
)
```

### 2.2. Using Lifecycle Hooks

**Custom Feedback via after_tool Hook:**

```python
from vanna.core.lifecycle import LifecycleHook
from vanna.core.tool import ToolResult
from vanna.components import UiComponent, NotificationComponent, SimpleTextComponent

class FeedbackHook(LifecycleHook):
    """Add custom feedback after tool execution"""

    async def after_tool(self, result: ToolResult) -> Optional[ToolResult]:
        # Check if tool took too long
        execution_time = result.metadata.get("execution_time_ms", 0)

        if execution_time > 5000:  # 5 seconds
            # Add warning notification
            warning_component = UiComponent(
                rich_component=NotificationComponent(
                    title="Slow Query Detected",
                    message=f"This query took {execution_time/1000:.1f}s to execute. Consider optimizing.",
                    type="warning",
                    dismissible=True,
                    duration=10000,
                ),
                simple_component=SimpleTextComponent(
                    text=f"⚠️ Query took {execution_time/1000:.1f}s"
                )
            )

            # Modify result to include feedback
            result.ui_component = warning_component

        return result

# Register hook:
agent = Agent(
    llm_service=llm,
    tool_registry=tools,
    user_resolver=resolver,
    agent_memory=memory,
    lifecycle_hooks=[FeedbackHook()],
)
```

### 2.3. Using WorkflowHandler for Feedback

**Custom Feedback Workflows:**

```python
from vanna.core.workflow import WorkflowHandler, WorkflowResult
from vanna.components import UiComponent, RichTextComponent, ButtonComponent

class FeedbackWorkflowHandler(WorkflowHandler):
    async def try_handle(
        self,
        agent: Agent,
        user: User,
        conversation: Conversation,
        message: str
    ) -> WorkflowResult:
        # Handle feedback commands
        if message.startswith("/feedback"):
            feedback_text = message.replace("/feedback", "").strip()

            # Store feedback
            await self.store_feedback(user, feedback_text)

            # Return confirmation
            return WorkflowResult(
                should_skip_llm=True,
                components=[
                    UiComponent(
                        rich_component=StatusCardComponent(
                            title="Thank you for your feedback!",
                            status="success",
                            description="Your feedback has been recorded.",
                            icon="💬",
                        ),
                        simple_component=SimpleTextComponent(
                            text="Feedback recorded. Thank you!"
                        )
                    )
                ]
            )

        # Not a feedback command, continue to LLM
        return WorkflowResult(should_skip_llm=False)

    async def get_starter_ui(
        self,
        agent: Agent,
        user: User,
        conversation: Conversation
    ) -> Optional[List[UiComponent]]:
        # Show feedback button on startup
        return [
            UiComponent(
                rich_component=ButtonComponent(
                    label="📝 Send Feedback",
                    value="/feedback ",
                    variant="secondary",
                ),
                simple_component=SimpleTextComponent(text="Type /feedback to send feedback")
            )
        ]
```

### 2.4. Using LLM Context Enhancer for Feedback

**Inject Feedback Context into LLM:**

```python
from vanna.core.enhancer import LlmContextEnhancer

class FeedbackContextEnhancer(LlmContextEnhancer):
    def __init__(self, agent_memory: AgentMemory):
        self.agent_memory = agent_memory

    async def enhance_system_prompt(
        self,
        system_prompt: str,
        user_message: str,
        user: User
    ) -> str:
        # Check if similar queries have had issues before
        similar_queries = await self.agent_memory.search_similar(
            user_message,
            limit=3,
            filters={"has_feedback": True}
        )

        if similar_queries:
            feedback_context = "\n\n## Previous User Feedback:\n"
            for query in similar_queries:
                feedback_context += f"- Query: {query['text']}\n"
                feedback_context += f"  Feedback: {query['feedback']}\n"

            return system_prompt + feedback_context

        return system_prompt
```

### 2.5. Using Observability for Feedback Metrics

**Track Feedback Metrics:**

```python
from vanna.core.observability import ObservabilityProvider

class FeedbackObservabilityProvider(ObservabilityProvider):
    async def record_feedback(
        self,
        user_id: str,
        conversation_id: str,
        rating: int,
        comment: str
    ):
        await self.record_metric(
            "user.feedback.rating",
            float(rating),
            "rating",
            tags={
                "user_id": user_id,
                "conversation_id": conversation_id,
            }
        )

        # Store detailed feedback
        await self.create_span(
            "user.feedback.detailed",
            attributes={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "rating": rating,
                "comment": comment,
            }
        )
```

---

## 3. Coding Conventions

### 3.1. Naming Conventions

**Classes:**
- PascalCase
- Descriptive names with suffixes indicating type:
  - `*Tool` - Tools (e.g., `RunSqlTool`, `EmailTool`)
  - `*Component` - UI Components (e.g., `StatusCardComponent`, `BadgeComponent`)
  - `*Hook` - Lifecycle hooks (e.g., `LoggingHook`, `QuotaCheckHook`)
  - `*Middleware` - LLM middlewares (e.g., `CachingMiddleware`)
  - `*Enricher` - Context enrichers (e.g., `UserPreferencesEnricher`)
  - `*Enhancer` - LLM enhancers (e.g., `DefaultLlmContextEnhancer`)
  - `*Handler` - Workflow handlers (e.g., `DefaultWorkflowHandler`)
  - `*Provider` - Service providers (e.g., `ObservabilityProvider`)
  - `*Service` - Services (e.g., `LlmService`, `AnthropicLlmService`)
  - `*Store` - Storage implementations (e.g., `ConversationStore`, `MemoryConversationStore`)

**Functions/Methods:**
- snake_case
- Async methods prefixed with `async def`
- Private methods prefixed with `_` (e.g., `_validate_tool_permissions`)
- Boolean methods start with `is_`, `has_`, `can_` (e.g., `can_user_access_feature`)

**Variables:**
- snake_case
- Descriptive names avoiding abbreviations
- Private attributes prefixed with `_` (e.g., `_tools`, `_wrapped_tool`)

**Constants:**
- UPPER_SNAKE_CASE (e.g., `DEFAULT_UI_FEATURES`, `MAX_RETRIES`)

### 3.2. Type Annotations

**Vanna 2.0 uses strong typing throughout:**

```python
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Generic, TypeVar

# Type variables for generics
T = TypeVar("T")

class Tool(ABC, Generic[T]):
    @abstractmethod
    async def execute(self, context: ToolContext, args: T) -> ToolResult:
        pass

# Pydantic models for data validation
from pydantic import BaseModel, Field

class ToolCall(BaseModel):
    id: str = Field(description="Unique identifier")
    name: str = Field(description="Tool name")
    arguments: Dict[str, Any] = Field(description="Arguments")

# Forward references to avoid circular imports
if TYPE_CHECKING:
    from ..user.models import User
    from ..tool import Tool

class ToolContext(BaseModel):
    user: "User"  # Forward reference
    conversation_id: str
```

**Common Type Patterns:**

1. **Optional for nullable values:**
   ```python
   system_prompt: Optional[str] = None
   ```

2. **List for collections:**
   ```python
   lifecycle_hooks: List[LifecycleHook] = []
   ```

3. **Dict for key-value data:**
   ```python
   metadata: Dict[str, Any] = Field(default_factory=dict)
   ```

4. **Union for multiple types:**
   ```python
   from typing import Union
   result: Union[T, ToolRejection]
   ```

5. **AsyncGenerator for streaming:**
   ```python
   from typing import AsyncGenerator
   async def send_message(...) -> AsyncGenerator[UiComponent, None]:
       yield component
   ```

6. **Generic types:**
   ```python
   class Tool(ABC, Generic[T]):
       def get_args_schema(self) -> Type[T]:
           pass
   ```

### 3.3. Pydantic Models

**All data models use Pydantic for validation:**

```python
from pydantic import BaseModel, Field, model_validator

class ToolResult(BaseModel):
    success: bool = Field(description="Whether execution succeeded")
    result_for_llm: str = Field(description="String content for LLM")
    ui_component: Optional[UiComponent] = Field(
        default=None,
        description="Optional UI component"
    )
    error: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Custom validation
class UiComponent(BaseModel):
    @model_validator(mode="after")
    def validate_components(self) -> "UiComponent":
        if not isinstance(self.rich_component, RichComponent):
            raise ValueError("rich_component must be a RichComponent")
        return self

    model_config = {"arbitrary_types_allowed": True}
```

### 3.4. Abstract Base Classes

**Use ABC for defining interfaces:**

```python
from abc import ABC, abstractmethod

class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Subclasses must implement"""
        pass

    @abstractmethod
    async def execute(self, context: ToolContext, args: T) -> ToolResult:
        """Subclasses must implement"""
        pass
```

### 3.5. Async/Await Patterns

**All I/O operations are async:**

```python
# Async methods
async def send_message(
    self,
    request_context: RequestContext,
    message: str
) -> AsyncGenerator[UiComponent, None]:
    # Resolve user
    user = await self.user_resolver.resolve_user(request_context)

    # Load conversation
    conversation = await self.conversation_store.get_conversation(
        conversation_id, user
    )

    # Execute tool
    result = await tool.execute(context, args)

    # Stream components
    yield component
```

### 3.6. Error Handling

```python
try:
    result = await tool.execute(context, args)
except Exception as e:
    logger.error(f"Tool execution failed: {e}", exc_info=True)
    return ToolResult(
        success=False,
        result_for_llm=f"Execution failed: {str(e)}",
        error=str(e),
    )
```

### 3.7. Logging

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Initialized Agent")
logger.warning(f"Tool iteration limit reached: {iterations}")
logger.error(f"Error in send_message: {e}", exc_info=True)
```

### 3.8. Documentation

**Docstrings use Google style:**

```python
def execute(self, context: ToolContext, args: T) -> ToolResult:
    """Execute the tool with validated arguments.

    Args:
        context: Execution context containing user, conversation_id, and request_id
        args: Validated tool arguments

    Returns:
        ToolResult with success status, result for LLM, and optional UI component

    Raises:
        ToolExecutionError: If execution fails
    """
    pass
```

### 3.9. Module Organization

```
src/vanna/
├── core/                      # Core framework
│   ├── agent/                 # Agent implementation
│   │   ├── __init__.py
│   │   ├── agent.py           # Main Agent class
│   │   └── config.py          # AgentConfig
│   ├── tool/                  # Tool system
│   │   ├── __init__.py
│   │   ├── base.py            # Tool base class
│   │   └── models.py          # ToolContext, ToolResult
│   ├── storage/               # Conversation storage
│   ├── llm/                   # LLM integration
│   ├── user/                  # User management
│   ├── lifecycle/             # Lifecycle hooks
│   ├── middleware/            # LLM middlewares
│   ├── workflow/              # Workflow handlers
│   ├── enricher/              # Context enrichers
│   ├── enhancer/              # LLM enhancers
│   ├── filter/                # Conversation filters
│   ├── observability/         # Observability
│   ├── audit/                 # Audit logging
│   └── registry.py            # ToolRegistry
├── components/                # UI components
│   ├── rich/                  # Rich components
│   │   ├── data/              # Data viz components
│   │   ├── feedback/          # Feedback components
│   │   ├── interactive/       # Interactive components
│   │   ├── specialized/       # Specialized components
│   │   └── text.py            # Text components
│   └── simple/                # Simple components
├── integrations/              # External integrations
│   ├── anthropic.py           # Anthropic LLM
│   ├── openai.py              # OpenAI LLM
│   ├── chromadb.py            # ChromaDB memory
│   ├── sqlite.py              # SQLite runner
│   └── local.py               # Local implementations
├── capabilities/              # Built-in capabilities
│   ├── agent_memory/          # AgentMemory
│   ├── file_system/           # File operations
│   └── sql_runner/            # SQL execution
└── servers/                   # Server implementations
    ├── fastapi/               # FastAPI integration
    └── flask/                 # Flask integration
```

---

## 4. Best Practices

### 4.1. Creating Custom Tools

```python
from vanna.core.tool import Tool, ToolContext, ToolResult
from pydantic import BaseModel, Field
from typing import Type

class MyToolArgs(BaseModel):
    """Arguments for MyTool"""
    param1: str = Field(description="First parameter")
    param2: int = Field(default=10, description="Second parameter")

class MyTool(Tool[MyToolArgs]):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Performs my custom operation"

    @property
    def access_groups(self) -> List[str]:
        return ["admin", "power_user"]  # Restrict access

    def get_args_schema(self) -> Type[MyToolArgs]:
        return MyToolArgs

    async def execute(self, context: ToolContext, args: MyToolArgs) -> ToolResult:
        # Access user context
        user = context.user

        # Perform operation
        result = await self.do_work(args.param1, args.param2)

        # Return with UI component
        return ToolResult(
            success=True,
            result_for_llm=f"Operation completed: {result}",
            ui_component=UiComponent(
                rich_component=StatusCardComponent(
                    title="✅ Success",
                    status="success",
                    description=f"Processed {result}",
                ),
                simple_component=SimpleTextComponent(text=f"Success: {result}")
            )
        )
```

### 4.2. Registering Tools

```python
from vanna.core.registry import ToolRegistry

# Create registry
tools = ToolRegistry()

# Register tools with access control
tools.register_local_tool(MyTool(), access_groups=["admin"])
tools.register_local_tool(PublicTool(), access_groups=[])  # All users
```

### 4.3. Creating Lifecycle Hooks

```python
from vanna.core.lifecycle import LifecycleHook
from vanna.core.user import User
from vanna.core.tool import Tool, ToolContext, ToolResult

class QuotaCheckHook(LifecycleHook):
    async def before_message(self, user: User, message: str) -> Optional[str]:
        # Check if user has exceeded quota
        usage = await self.get_user_usage(user.id)
        if usage > user.quota:
            raise AgentError("Quota exceeded")
        return None

    async def before_tool(self, tool: Tool, context: ToolContext) -> None:
        # Log tool usage
        await self.log_tool_usage(context.user.id, tool.name)

    async def after_tool(self, result: ToolResult) -> Optional[ToolResult]:
        # Add quota warning if close to limit
        usage = await self.get_user_usage(result.user.id)
        if usage > 0.9 * result.user.quota:
            # Modify result to include warning
            result.ui_component = self.create_quota_warning()
        return result
```

### 4.4. Testing

```python
import pytest
from vanna.core.user import User
from vanna.core.tool import ToolContext

@pytest.mark.asyncio
async def test_my_tool():
    # Setup
    tool = MyTool()
    user = User(id="test", email="test@example.com", group_memberships=["admin"])
    context = ToolContext(
        user=user,
        conversation_id="conv-123",
        request_id="req-456",
        agent_memory=mock_memory,
    )
    args = MyToolArgs(param1="test", param2=20)

    # Execute
    result = await tool.execute(context, args)

    # Assert
    assert result.success
    assert "completed" in result.result_for_llm
    assert result.ui_component is not None
```

---

## 5. Key Takeaways

### Agent Architecture
1. **Agent** là core orchestrator điều phối LLM, tools, và conversation
2. **7 extensibility points** cho phép customize hành vi tại mọi giai đoạn
3. **User-aware** - mọi thành phần đều biết user identity và permissions

### Custom Feedback Integration Points
1. **ToolResult.ui_component** - Trả feedback trực tiếp từ tools
2. **Lifecycle Hooks** - Thêm feedback sau tool execution
3. **WorkflowHandler** - Xử lý feedback commands
4. **Custom Components** - Tạo component types mới
5. **LLM Context Enhancer** - Inject feedback vào LLM context
6. **Observability** - Track feedback metrics

### Coding Conventions
1. **Strong typing** với Pydantic và type hints
2. **Async/await** cho mọi I/O operations
3. **ABC** cho interfaces
4. **PascalCase** classes, **snake_case** methods/variables
5. **Type-safe generics** với TypeVar
6. **Descriptive naming** với type suffixes

### Best Practices
1. Sử dụng Pydantic models cho validation
2. Implement abstract methods từ base classes
3. Return rich UI components từ tools
4. Add observability spans cho debugging
5. Use lifecycle hooks cho cross-cutting concerns
6. Keep tools focused và single-purpose

---

## 6. Next Steps để mở rộng Vanna 2.0

1. **Create Custom Tools**: Xây dựng tools cụ thể cho domain của bạn
2. **Design Feedback Components**: Thiết kế UI components cho feedback system
3. **Implement Lifecycle Hooks**: Tạo hooks để track và respond to feedback
4. **Extend WorkflowHandler**: Xử lý feedback commands và workflows
5. **Setup Observability**: Integrate metrics và tracing cho feedback analytics
6. **Build Memory System**: Sử dụng AgentMemory để học từ feedback
7. **Create Tests**: Viết tests cho tools và feedback system

---

**Tài liệu này cung cấp foundation để hiểu và mở rộng Vanna 2.0 framework.**
