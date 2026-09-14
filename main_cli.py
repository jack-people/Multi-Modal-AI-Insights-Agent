import os
import sqlite3
from langchain_core.messages import HumanMessage
from graph import create_agent_app
from config import AGENT_DB_PATH, validate_config
from runtime_context import set_thread_id, log_event

EXIT_COMMANDS = {"exit", "quit"}


def get_all_sessions(db_path=AGENT_DB_PATH):
    """从 SQLite 数据库中提取所有已有的 thread_id"""
    if not os.path.exists(db_path):
        return []
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # LangGraph 的 SqliteSaver 默认将数据存在 checkpoints 表中
            cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"读取历史记录失败: {e}")
        return []

def select_session():
    """交互式选择会话 ID"""
    sessions = get_all_sessions()
    
    print("\n--- 历史会话列表 ---")
    if not sessions:
        print("（暂无历史记录）")
    else:
        for i, session in enumerate(sessions, 1):
            print(f"[{i}] {session}")
    print("[0] 新建会话")
    print("-------------------")
    
    choice = input("\n请选择会话编号 (直接输入名称则新建): ").strip()
    
    # 判断用户输入的是编号还是新名称
    if choice.isdigit():
        idx = int(choice)
        if idx == 0:
            new_id = input("请输入新会话的名称: ").strip() or "default"
            return new_id
        elif 1 <= idx <= len(sessions):
            selected_id = sessions[idx-1]
            print(f"✅ 已加载历史会话: {selected_id}")
            return selected_id
        else:
            print("⚠️ 无效编号，将使用默认名称。")
            return "default"
    else:
        # 如果输入的不是数字，直接作为新 ID
        return choice if choice else "default"

if __name__ == "__main__":
    validate_config()
    app = create_agent_app()
    print("==================================================")
    print("🤖 欢迎使用多模态智能体 Agent！(输入 'exit' 退出)")
    print("==================================================")
    
    # 1. 获取用户选择的会话 ID
    session_id = select_session()
    set_thread_id(session_id)
    config = {"configurable": {"thread_id": session_id}}
    log_event("main_cli", "session_start", meta={"thread_id": session_id})
    
    print(f"\n🚀 当前对话 ID: {session_id} (已进入聊天模式)")

    while True:
        user_input = input("\n🧑‍💻 用户提问: \n")
        if user_input.lower() in EXIT_COMMANDS:
            break
        if not user_input.strip(): 
            continue
            
        try:
            # 使用 stream_mode="updates" 实时观察节点变化
            log_event("main_cli", "user_query", meta={"chars": len(user_input)})
            for output in app.stream(
                {"messages": [HumanMessage(content=user_input)]}, 
                config=config, 
                stream_mode="updates"
            ):
                # 打印节点名方便调试，正式使用时可以只打印最终回复
                for node_name, state in output.items():
                    print(f"[{node_name}] 处理完毕...")
                    # 如果你想在控制台直接看到回答，可以取消下面注释：
                    # if node_name == "synthesizer":
                    #    print(f"Assistant: {state['messages'][-1].content}")
                    
        except Exception as e:
            log_event("main_cli", "error", meta={"error": str(e)})
            print(f"\n❌ 运行错误: {e}")
