import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from core.lark_cli import cli, LarkCliError


class BitableError(Exception):
    pass


def get_field_order(app_token: str, table_id: str) -> Optional[List[str]]:
    try:
        r = cli.base_field_list(app_token, table_id)
        if r.get("ok"):
            data = r.get("data") or {}
            fields = data.get("fields") or []
            order = []
            for f in fields:
                name = f.get("name") or f.get("field_name")
                if name and name != "record_id":
                    order.append(name)
            if order:
                logger.info(f"获取字段顺序成功: {order}")
                return order
    except LarkCliError as e:
        logger.debug(f"base_field_list 失败，改用记录字段顺序: {e}")
    return None


def fetch_all_records(app_token: str, table_id: str) -> List[Dict[str, Any]]:
    items_all: List[Dict[str, Any]] = []
    # 这个版本 lark-cli 一次可能就能拉全部（limit 2000），也可能需要分页
    # 先按单次拉取处理，实测成功后再按 page_token/offset 适配
    res = cli.base_record_list(app_token, table_id, page_size=2000, offset=0, overwrite=True)
    if not res.get("ok"):
        raise BitableError(f"base_record_list 失败 (exit={res.get('code')}): {res.get('stderr') or res.get('stdout')}")
    out_file = Path(res.get("file"))
    if not out_file.exists():
        raise BitableError(f"ndjson 文件未生成: {out_file}")
    try:
        with out_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    items_all.append(rec)
                except json.JSONDecodeError:
                    continue
    finally:
        # 清理临时文件
        try:
            out_file.unlink(missing_ok=True)
            out_file.with_suffix(".manifest.json").unlink(missing_ok=True)
        except Exception:
            pass
    logger.info(f"共拉取记录数: {len(items_all)}")
    return items_all

def _manifest_has_more(ndjson_path: Path) -> Optional[bool]:
    # manifest 文件名可能是 <stem>.manifest.json 或 <name>.manifest.json，两种都试
    candidates = [
        ndjson_path.with_name(ndjson_path.stem + ".manifest.json"),
        ndjson_path.with_suffix(".manifest.json"),
    ]
    for manifest in candidates:
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                return bool(data.get("has_more"))
            except Exception:
                return None
    return None


def normalize_records(records: List[Dict[str, Any]], field_order: Optional[List[str]] = None):
    if not records:
        return (field_order or []), []

    # 推断表头（排除系统字段 record_id）
    if field_order:
        headers = [h for h in field_order if h != "record_id"]
    else:
        headers: List[str] = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            for k in rec.keys():
                if k != "record_id" and k not in headers:
                    headers.append(k)

    rows: List[Dict[str, str]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        row = {h: _to_str(rec.get(h)) for h in headers}
        rows.append(row)

    return headers, rows


def _name_of(v: Any) -> str:
    if isinstance(v, dict):
        for key in ["name", "text", "title", "value", "id"]:
            if key in v and v[key] is not None:
                return str(v[key])
        return str(v)
    return str(v)


def _to_str(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, list):
        parts: List[str] = []
        for x in v:
            if isinstance(x, list):
                for y in x:
                    n = _name_of(y)
                    if n:
                        parts.append(n)
            else:
                n = _name_of(x)
                if n:
                    parts.append(n)
        return ", ".join(parts) if parts else "-"
    if isinstance(v, dict):
        return _name_of(v)
    return str(v)
