from typing import TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_text: str
    # intent and resolved_path are already read by planner_node and
    # validate_plan_node via state.get(...) — adding them here makes
    # the shared state schema accurate without breaking any existing code.
    intent: Optional[str]
    resolved_path: Optional[str]
    plan: dict
    approved: bool
