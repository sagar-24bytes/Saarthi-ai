from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from planner.state import AgentState
from planner.planner import planner_node
from tools.validator import validate_plan_node
from tools.confirmation import confirmation_node, gui_confirmation_node
from tools.executor import execute_plan_node


def build_planner_graph():
    """
    CLI graph — uses voice/keyboard confirmation_node.
    Unchanged from original.
    """
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("validator", validate_plan_node)
    graph.add_node("confirmation", confirmation_node)
    graph.add_node("executor", execute_plan_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "validator")
    graph.add_edge("validator", "confirmation")

    # conditional execution
    graph.add_conditional_edges(
        "confirmation",
        lambda state: state.get("approved", False),
        {
            True: "executor",
            False: END
        }
    )

    graph.add_edge("executor", END)

    return graph.compile()


def build_gui_planner_graph():
    """
    GUI graph — uses gui_confirmation_node which calls interrupt()
    to pause the graph and yield control back to the GUI.

    Requires MemorySaver so LangGraph can checkpoint state between
    the initial stream (planner → validator → interrupt) and the
    resume stream (Command(resume=True/False) → executor/END).

    The graph edges are identical to the CLI graph — the only
    difference is the confirmation node and the checkpointer.
    """
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("validator", validate_plan_node)
    graph.add_node("confirmation", gui_confirmation_node)
    graph.add_node("executor", execute_plan_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "validator")
    graph.add_edge("validator", "confirmation")

    graph.add_conditional_edges(
        "confirmation",
        lambda state: state.get("approved", False),
        {
            True: "executor",
            False: END
        }
    )

    graph.add_edge("executor", END)

    # MemorySaver is required for interrupt()/resume to work.
    # Each GUI planning session uses a unique thread_id so runs
    # are fully isolated from each other.
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
