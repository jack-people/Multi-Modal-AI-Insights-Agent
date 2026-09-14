"""LangGraph 工作流装配模块。"""
import os
import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.sqlite import SqliteSaver
from state import AgentState
from tools import tools
from nodes import synthesizer_node, critic_node, intent_router_node, planner_node, skill_execution_node
from config import AGENT_DB_PATH


def critic_condition(state: AgentState) -> str:
    return state.get("critic_decision", "ACCEPT")


def create_agent_app(db_path: str = AGENT_DB_PATH):
    workflow = StateGraph(AgentState)

    workflow.add_node("intent_router", intent_router_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", skill_execution_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("critic", critic_node)

    workflow.add_edge(START, "intent_router")
    workflow.add_edge("intent_router", "planner")
    workflow.add_edge("planner", "executor")
    workflow.add_conditional_edges(
        "executor",
        tools_condition,
        {
            "tools": "tools",
            END: "synthesizer",
        }
    )
    workflow.add_edge("tools", "executor")
    workflow.add_edge("synthesizer", "critic")
    workflow.add_conditional_edges(
        "critic",
        critic_condition,
        {
            "ACCEPT": END,
            "REJECT": "executor",
        }
    )

    # 配置 SQLite 持久化（用于会话 checkpoint）
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)

    return workflow.compile(checkpointer=memory)
