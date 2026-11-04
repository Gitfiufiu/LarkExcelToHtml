import os
import time
import tempfile
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from config import settings


class LarkCliError(Exception):
    pass


class LarkCli:
    def __init__(self, cmd: Optional[str] = None):
        self.cmd = cmd or settings.LARK_CLI_CMD

    def run_raw(self, args: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
        cmd_list = [self.cmd] + list(args)
        logger.debug(f"lark-cli run: {' '.join(cmd_list)}")
        try:
            res = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",  # 遇到无法解码的字节用   替换，避免崩溃
                shell=False,
                timeout=timeout,
            )
            return res
        except subprocess.TimeoutExpired as e:
            raise LarkCliError(f"Timeout after {timeout}s for command: {' '.join(cmd_list)}") from e
        except FileNotFoundError as e:
            raise LarkCliError(f"Command not found: {self.cmd}. Ensure lark-cli is installed and in PATH") from e

    def run_json(self, args: List[str], timeout: int = 60) -> Dict[str, Any]:
        res = self.run_raw(args, timeout=timeout)
        stdout = res.stdout or ""
        stderr = res.stderr or ""
        if res.returncode != 0:
            # 尝试从 stdout 解析 JSON 错误
            try:
                err = json.loads(stdout.strip()) if stdout.strip() else {}
                raise LarkCliError(f"lark-cli failed (code={res.returncode}): {json.dumps(err, ensure_ascii=False)}\nstderr: {stderr}")
            except json.JSONDecodeError:
                raise LarkCliError(f"lark-cli failed (code={res.returncode}):\nstdout: {stdout}\nstderr: {stderr}")
        try:
            data = json.loads(stdout.strip()) if stdout.strip() else {}
            return data
        except json.JSONDecodeError as e:
            raise LarkCliError(f"Failed to parse JSON from stdout: {stdout}\nstderr: {stderr}") from e

    # 常用快捷方法
    def chat_messages_list(self, chat_id: str, order: str = "desc", page_size: int = 20) -> Dict[str, Any]:
        return self.run_json([
            "im", "+chat-messages-list",
            "--chat-id", chat_id,
            "--order", order,
            f"--page-size", str(page_size),
        ])

    def messages_send_image(self, chat_id: str, image_path: Path) -> Dict[str, Any]:
        # 已实测：一步上传并发送
        return self.run_json([
            "im", "+messages-send",
            "--chat-id", chat_id,
            "--image", str(image_path.resolve()),
        ])

    def base_url_resolve(self, url: str) -> Dict[str, Any]:
        return self.run_json(["base", "+url-resolve", "--url", url])

    def wiki_node_get(self, node_token: str) -> Dict[str, Any]:
        return self.run_json(["wiki", "+node-get", "--node-token", node_token])

    def wiki_space_list(self) -> Dict[str, Any]:
        return self.run_json(["wiki", "+space-list"])

    def wiki_node_list(self, space_id: str, page_token: Optional[str] = None, page_size: int = 50) -> Dict[str, Any]:
        args = ["wiki", "+node-list", "--space-id", space_id, f"--page-size", str(page_size)]
        if page_token:
            args += ["--page-token", page_token]
        return self.run_json(args)

  
    def base_record_list(self, app_token: str, table_id: str, page_size: int = 2000, offset: int = 0, overwrite: bool = True) -> Dict[str, Any]:
        tmp_dir = Path(tempfile.gettempdir())
        out_file = tmp_dir / f"_lark_records_{os.getpid()}_{int(time.time())}.ndjson"
        args = [
            "base", "+record-list",
            "--base-token", app_token,
            "--table-id", table_id,
            "--offset", str(offset),
            "--limit", str(page_size),
            "--format", "ndjson",
            "--output", str(out_file),
        ]
        if overwrite:
            args.append("--overwrite")
        # 先清理旧的同名残留（保险）
        manifest = out_file.with_suffix(".manifest.json")
        for p in [out_file, manifest]:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        res = self.run_raw(args, timeout=120)
        # lark-cli 用文件输出时，成功通常返回简短信息到 stdout/stderr
        # 实际数据在 out_file 里
        return {"ok": res.returncode == 0, "file": str(out_file), "stdout": res.stdout, "stderr": res.stderr, "code": res.returncode}

    def base_field_list(self, app_token: str, table_id: str) -> Dict[str, Any]:
        return self.run_json(["base", "+field-list", "--base-token", app_token, "--table-id", table_id])

    def api_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        args = ["api", "GET", path]
        if params is not None:
            args += ["--params", json.dumps(params, ensure_ascii=False)]
        return self.run_json(args)


cli = LarkCli()
