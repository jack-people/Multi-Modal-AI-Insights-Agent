import json
import os
import subprocess
import time


def _safe_output_path(filename: str) -> str:
    clean = (filename or "").strip().replace("\\", "/")
    if not clean:
        raise ValueError("filename 不能为空")
    if clean.startswith("/") or ":" in clean:
        raise ValueError("filename 不能是绝对路径")
    if ".." in clean.split("/"):
        raise ValueError("filename 不能包含上级目录跳转")
    return os.path.join("action_outputs", clean)


def execute_write_report_file(filename: str, content: str) -> dict:
    output_path = _safe_output_path(filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content or "")
    return {"ok": True, "message": f"文件写入成功: {output_path}", "output_path": output_path}


def execute_create_email_draft(recipient: str, subject: str, body: str) -> dict:
    safe_name = f"email_draft_{int(time.time())}.json"
    output_path = os.path.join("action_outputs", "email_drafts", safe_name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    payload = {"recipient": recipient, "subject": subject, "body": body}
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    return {"ok": True, "message": f"邮件草稿已写入: {output_path}", "output_path": output_path}


def execute_shell_command(command: str, timeout_sec: int = 20) -> dict:
    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    output = output.strip()
    if completed.returncode != 0:
        return {
            "ok": False,
            "message": f"命令执行失败，exit_code={completed.returncode}",
            "output_path": "",
            "command_output": output[:1000],
        }
    return {
        "ok": True,
        "message": "命令执行成功",
        "output_path": "",
        "command_output": output[:1000],
    }


def execute_confirmed_action(action_name: str, payload: dict) -> dict:
    if action_name == "action_write_report_file":
        return execute_write_report_file(payload.get("filename", ""), payload.get("content", ""))
    if action_name == "action_create_email_draft":
        return execute_create_email_draft(
            payload.get("recipient", ""),
            payload.get("subject", ""),
            payload.get("body", ""),
        )
    if action_name == "action_run_shell_command":
        return execute_shell_command(payload.get("command", ""))
    return {"ok": False, "message": f"未知动作: {action_name}", "output_path": ""}
