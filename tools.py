# 工具库：存放本地检索、网络检索等 @tool 函数
import json
import time
import requests
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchResults
from config import (
    DIFY_APP_API_KEY,
    DIFY_APP_MODE,
    DIFY_CHAT_URL,
    DIFY_COMPLETION_URL,
    DIFY_WORKFLOW_URL,
    DIFY_TIMEOUT_SEC,
    DIFY_HTTP_TRUST_ENV,
    TOOL_RETRY_MAX,
    TOOL_RETRY_BACKOFF,
    ACTION_AUTO_EXECUTE_MAX_RISK,
)
from runtime_context import log_event, is_force_action_confirm
from actions import append_audit_log, should_auto_execute, execute_confirmed_action

HTTP_SESSION = requests.Session()
HTTP_SESSION.trust_env = DIFY_HTTP_TRUST_ENV


def _allow_auto_execute(risk: str) -> bool:
    if is_force_action_confirm():
        return False
    return should_auto_execute(risk, ACTION_AUTO_EXECUTE_MAX_RISK)


def _tool_result(ok: bool, source: str, query: str, data: str = "", error: str = "") -> str:
    """统一工具输出协议，便于下游节点稳定消费。"""
    payload = {
        "ok": ok,
        "source": source,
        "query": query,
        "data": data,
        "error": error
    }
    return json.dumps(payload, ensure_ascii=False)


def _request_with_retry(url: str, headers: dict, payload: dict, source: str):
    last_error = None
    for attempt in range(1, TOOL_RETRY_MAX + 1):
        try:
            log_event(
                node=source,
                event="request_attempt",
                meta={"attempt": attempt, "timeout_sec": DIFY_TIMEOUT_SEC},
            )
            response = HTTP_SESSION.post(
                url,
                headers=headers,
                json=payload,
                timeout=DIFY_TIMEOUT_SEC,
            )
            return response
        except Exception as e:
            last_error = e
            log_event(
                node=source,
                event="request_error",
                meta={"attempt": attempt, "error": str(e)}
            )
            if attempt < TOOL_RETRY_MAX and TOOL_RETRY_BACKOFF > 0:
                time.sleep(TOOL_RETRY_BACKOFF * attempt)

    raise RuntimeError(f"请求失败，已重试 {TOOL_RETRY_MAX} 次。最后错误: {last_error}")


def _action_data(
    action: str,
    risk: str,
    status: str,
    message: str,
    output_path: str = "",
    requires_confirmation: bool = False,
    confirm_payload: dict | None = None,
    command_output: str = "",
) -> str:
    return json.dumps(
        {
            "action": action,
            "risk": risk,
            "status": status,
            "message": message,
            "output_path": output_path,
            "requires_confirmation": requires_confirmation,
            "confirm_payload": confirm_payload or {},
            "command_output": command_output,
        },
        ensure_ascii=False,
    )


def _dify_fallback_web(query: str, reason: str) -> str:
    """当 Dify 不可用时，降级到公网搜索，避免主链路中断。"""
    try:
        search = DuckDuckGoSearchResults(max_results=5)
        results = search.run(query)
        data = f"[DIFY_FALLBACK] 原因: {reason}\n{results}"
        return _tool_result(
            ok=True,
            source="dify_arxiv_db",
            query=query,
            data=data,
        )
    except Exception as e:
        return _tool_result(
            ok=False,
            source="dify_arxiv_db",
            query=query,
            error=f"{reason}; 且公网回退失败: {e}",
        )


_DIFY_MODE_MISMATCH = {"not_workflow_app", "not_chat_app", "not_completion_app"}
_dify_mode_resolved: str | None = None


def extract_dify_answer(result: dict) -> str:
    answer = str(result.get("answer") or "").strip()
    if answer:
        return answer
    data_block = result.get("data")
    if not isinstance(data_block, dict):
        return ""
    nested = str(data_block.get("answer") or "").strip()
    if nested:
        return nested
    outputs = data_block.get("outputs")
    if isinstance(outputs, dict) and outputs:
        return "".join(str(value) for value in outputs.values()).strip()
    return ""


def _dify_headers() -> dict:
    return {
        "Authorization": f"Bearer {DIFY_APP_API_KEY}",
        "Content-Type": "application/json",
    }


def _dify_url_for(mode: str) -> str:
    if mode == "chat":
        return DIFY_CHAT_URL
    if mode == "completion":
        return DIFY_COMPLETION_URL
    return DIFY_WORKFLOW_URL


def _dify_payload(query: str, mode: str) -> dict:
    if mode == "chat":
        return {
            "inputs": {"query": query},
            "query": query,
            "response_mode": "blocking",
            "user": "vscode-agent-tool",
        }
    return {
        "inputs": {"query": query},
        "response_mode": "blocking",
        "user": "vscode-agent-tool",
    }


def _dify_response_code(response) -> str:
    try:
        body = response.json()
    except Exception:
        return ""
    if isinstance(body, dict):
        return str(body.get("code") or "")
    return ""


def _dify_mode_order() -> list[str]:
    configured = (DIFY_APP_MODE or "auto").strip().lower()
    if configured != "auto":
        return [configured]
    preferred = _dify_mode_resolved or "workflow"
    rest = [item for item in ("workflow", "chat", "completion") if item != preferred]
    return [preferred, *rest]


def call_dify_search(query: str):
    """按 App 类型调用 Dify；auto 模式下接口不匹配会换路由重试。"""
    global _dify_mode_resolved
    last_error = "Dify 未返回有效响应"
    last_response = None
    for mode in _dify_mode_order():
        response = _request_with_retry(
            _dify_url_for(mode),
            _dify_headers(),
            _dify_payload(query, mode),
            source="dify_arxiv_db",
        )
        last_response = response
        if response.status_code == 200:
            _dify_mode_resolved = mode
            return response, mode, ""
        last_error = f"状态码: {response.status_code}, 详情: {response.text}"
        mismatch = _dify_response_code(response) in _DIFY_MODE_MISMATCH
        log_event(
            "dify_arxiv_db",
            "http_error",
            meta={"status_code": response.status_code, "mode": mode, "mismatch": mismatch},
        )
        if mismatch and (DIFY_APP_MODE or "auto") == "auto":
            continue
        break
    return last_response, _dify_mode_resolved or "", last_error


def _pending_action_response(source: str, risk: str, query: str, message: str, confirm_payload: dict) -> str:
    return _tool_result(
        ok=False,
        source=source,
        query=query,
        data=_action_data(
            source,
            risk,
            "pending_confirmation",
            message,
            requires_confirmation=True,
            confirm_payload=confirm_payload,
        ),
        error=message,
    )


def _execute_action_or_error(source: str, confirm_payload: dict, default_error: str = "动作执行失败") -> tuple[bool, str, str, str]:
    result = execute_confirmed_action(source, confirm_payload)
    ok = bool(result.get("ok", False))
    message = str(result.get("message", "")).strip() or default_error
    output_path = str(result.get("output_path", ""))
    command_output = str(result.get("command_output", ""))
    return ok, message, output_path, command_output

# @tool
# def search_local_arxiv_db(query: str) -> str:
#     """
#     当你需要查询 Arxiv 多模态论文的本地知识库时调用此工具。
#     输入：搜索关键词。返回：相关论文的标题和摘要。
#     """

#      # 简化的检索逻辑
#     try:
#         client = chromadb.PersistentClient(path="./multimodal_papers_db")
#         emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-small-zh-v1.5")
#         collection = client.get_collection(name="arxiv_multimodal", embedding_function=emb_fn)

#         # 👉 阶段 1：粗排召回 (Recall Top 20)
#         total_docs = collection.count()
#         print("【本地数据库】当前文档总数:", total_docs)
#         if total_docs == 0:
#             return "【本地数据库】当前为空，请先入库数据。"
            
#         recall_k = min(20, total_docs) 
#         results = collection.query(query_texts=[query], n_results=recall_k)
#         if not results['ids'][0]:
#             return "【本地数据库】未找到相关论文。"

#         # 准备数据对交给重排器
#         docs = results['documents'][0]
#         metadatas = results['metadatas'][0]
#         sentence_pairs = [[query, doc] for doc in docs]
        
#         # 👉 阶段 2：精排打分 (Rerank)
#         scores = reranker.compute_score(sentence_pairs)
        
#         # 将文档、元数据和得分组合在一起并排序
#         scored_docs = list(zip(docs, metadatas, scores))
#         # 按照 score 降序排列
#         scored_docs.sort(key=lambda x: x[2], reverse=True)
        
#         # 👉 阶段 3：截断 (Top 3)
#         top_3_docs = scored_docs[:3]    
        
#         res_str = "【本地 Arxiv 论文检索结果】\n"
#         for doc, meta, score in top_3_docs:
#             # 加上你原来的清洗逻辑，提取真正的摘要内容
#             clean_abstract = doc.split("Abstract: ")[-1][:300] 
            
#             res_str += f"-[相关度得分: {score:.2f}] 标题: {meta['title']}\n  摘要: {clean_abstract}...\n"
        
#         return res_str
#     except Exception as e:
#         return f"本地检索出错: {str(e)}"

@tool
def search_dify_arxiv_db(query: str) -> str:
    """
    用于在本地 Dify 多模态论文知识库中检索。
    ⚠️【警告：搜索词限制】
    传入的 query 必须是非常简短的 2-3 个核心学术名词组合（例如："多模态 幻觉" 或 "GPT-4o 架构"）。
    绝对禁止输入长句或堆砌超过 5 个词，否则将导致系统崩溃！
    """
    print(f"\n🔍 [Tool] 正在向 Dify 发起检索: '{query}'")
    log_event("dify_arxiv_db", "start", meta={"query": query, "app_mode": DIFY_APP_MODE})

    try:
        response, mode, error_msg = call_dify_search(query)
        if response is None or response.status_code != 200:
            print(f"❌ [Tool] {error_msg}")
            return _dify_fallback_web(query, f"Dify API 报错! {error_msg}")

        try:
            result = response.json()
        except Exception as json_err:
            print(f"❌ [Tool] 解析 Dify JSON 失败！Dify 真实返回内容如下：\n{response.text}")
            log_event("dify_arxiv_db", "json_parse_error", meta={"error": str(json_err)})
            return _dify_fallback_web(query, "Dify 知识库检索出错: 返回了非 JSON 格式的数据。")

        answer = extract_dify_answer(result if isinstance(result, dict) else {})
        if not answer:
            print("⚠️ [Tool] 知识库检索完成，但未返回内容。")
            log_event("dify_arxiv_db", "done", meta={"chars": 0, "mode": mode})
            return _tool_result(
                ok=True,
                source="dify_arxiv_db",
                query=query,
                data="在知识库中未检索到相关内容。",
            )

        print(f"✅ [Tool] Dify 检索成功（{mode}）！总字数: {len(answer)}。")
        log_event("dify_arxiv_db", "done", meta={"chars": len(answer), "mode": mode})
        return _tool_result(
            ok=True,
            source="dify_arxiv_db",
            query=query,
            data=answer,
        )

    except Exception as e:
        error_msg = f"连接 Dify 发生网络异常: {e}"
        print(f"❌ [Tool] {error_msg}")
        log_event("dify_arxiv_db", "error", meta={"error": str(e)})
        return _dify_fallback_web(query, error_msg)
    
@tool
def search_web_news(query: str) -> str:
    """查询互联网最新资讯的工具"""
    print(f"\n   🌐 [工具调用] 正在去互联网搜索关键词: '{query}' ...")
    log_event("web_news", "start", meta={"query": query})
    search = DuckDuckGoSearchResults(max_results=9)
    try:
        results = search.run(query)
        print(f" 🤖【互联网搜索】结果 : ✅ [工具调用] 搜索成功，获取到参考数据。")
        log_event("web_news", "done", meta={"chars": len(str(results))})
        return _tool_result(
            ok=True,
            source="web_news",
            query=query,
            data=str(results)
        )
    except Exception as e:
        print(f" 🤖网络搜索出错: ❌ [工具调用] 搜索失败: {e}")
        log_event("web_news", "error", meta={"error": str(e)})
        return _tool_result(
            ok=False,
            source="web_news",
            query=query,
            error=f"网络搜索出错: {str(e)}"
        )


@tool
def action_write_report_file(filename: str, content: str) -> str:
    """
    将内容写入本地文件（低风险动作）。
    适用于“生成综述并保存到文件”等任务。
    """
    source = "action_write_report_file"
    risk = "low"
    query = f"filename={filename}"
    confirm_payload = {"filename": filename, "content": content}
    log_event(source, "start", meta={"filename": filename, "chars": len(content or "")})
    try:
        if not _allow_auto_execute(risk):
            message = "当前策略不允许自动执行该动作，请用户确认后再执行。"
            append_audit_log(source, risk, "pending_confirmation", message, {"filename": filename})
            return _pending_action_response(source, risk, query, message, confirm_payload)

        ok, message, output_path, _ = _execute_action_or_error(source, confirm_payload)
        if not ok:
            raise RuntimeError(message)
        append_audit_log(source, risk, "executed", message, {"filename": filename, "output_path": output_path})
        log_event(source, "done", meta={"output_path": output_path})
        return _tool_result(
            ok=True,
            source=source,
            query=query,
            data=_action_data(source, risk, "executed", message, output_path=output_path),
        )
    except Exception as e:
        message = f"写文件失败: {e}"
        append_audit_log(source, risk, "failed", message, {"filename": filename})
        log_event(source, "error", meta={"error": str(e)})
        return _tool_result(ok=False, source=source, query=query, error=message)


@tool
def action_create_email_draft(recipient: str, subject: str, body: str) -> str:
    """
    生成邮件草稿（中风险动作）。
    默认需要确认；若策略允许 medium 自动执行，则会保存草稿文件。
    """
    source = "action_create_email_draft"
    risk = "medium"
    query = f"recipient={recipient};subject={subject}"
    confirm_payload = {"recipient": recipient, "subject": subject, "body": body}
    log_event(source, "start", meta={"recipient": recipient, "subject_len": len(subject or "")})
    try:
        if not _allow_auto_execute(risk):
            message = "邮件草稿属于中风险动作，已生成待确认任务。"
            append_audit_log(source, risk, "pending_confirmation", message, {"recipient": recipient, "subject": subject})
            return _pending_action_response(source, risk, query, message, confirm_payload)

        ok, message, output_path, _ = _execute_action_or_error(source, confirm_payload)
        if not ok:
            raise RuntimeError(message)
        append_audit_log(source, risk, "executed", message, {"recipient": recipient, "output_path": output_path})
        log_event(source, "done", meta={"output_path": output_path})
        return _tool_result(
            ok=True,
            source=source,
            query=query,
            data=_action_data(source, risk, "executed", message, output_path=output_path),
        )
    except Exception as e:
        message = f"创建邮件草稿失败: {e}"
        append_audit_log(source, risk, "failed", message, {"recipient": recipient})
        log_event(source, "error", meta={"error": str(e)})
        return _tool_result(ok=False, source=source, query=query, error=message)


@tool
def action_run_shell_command(command: str) -> str:
    """
    高风险动作占位工具：默认不执行真实命令，返回待确认。
    """
    source = "action_run_shell_command"
    risk = "high"
    query = command
    confirm_payload = {"command": command}
    if not _allow_auto_execute(risk):
        message = "高风险动作默认不自动执行。请用户明确确认后再执行。"
        append_audit_log(source, risk, "pending_confirmation", message, {"command": command})
        log_event(source, "blocked", meta={"reason": "high_risk_requires_confirmation"})
        return _pending_action_response(source, risk, query, message, confirm_payload)

    ok, message, _, command_output = _execute_action_or_error(source, confirm_payload, default_error="高风险动作执行失败")
    if not ok:
        append_audit_log(source, risk, "failed", message, {"command": command})
        return _tool_result(
            ok=False,
            source=source,
            query=query,
            data=_action_data(
                source,
                risk,
                "failed",
                message,
                command_output=command_output,
            ),
            error=message,
        )
    append_audit_log(source, risk, "executed", message, {"command": command})
    return _tool_result(
        ok=True,
        source=source,
        query=query,
        data=_action_data(
            source,
            risk,
            "executed",
            message,
            command_output=command_output,
        ),
    )

# tools = [search_local_arxiv_db, search_web_news,search_dify_arxiv_db]
tools = [
    search_dify_arxiv_db,
    search_web_news,
    action_write_report_file,
    action_create_email_draft,
    action_run_shell_command,
]