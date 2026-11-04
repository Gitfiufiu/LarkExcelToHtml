import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from loguru import logger

from config import settings
from core.lark_cli import cli, LarkCliError


class ResolverError(Exception):
    pass


def extract_wiki_token(url: str) -> Optional[str]:
    m = re.search(r"/wiki/([A-Za-z0-9]+)", url)
    if m:
        return m.group(1)
    return None


def extract_table_id(url: str) -> Optional[str]:
    try:
        qs = parse_qs(urlparse(url).query)
        if "table" in qs and qs["table"]:
            return qs["table"][0]
    except Exception:
        pass
    return None


def extract_view_id(url: str) -> Optional[str]:
    try:
        qs = parse_qs(urlparse(url).query)
        if "view" in qs and qs["view"]:
            return qs["view"][0]
    except Exception:
        pass
    return None


def resolve_table() -> Tuple[str, str, Optional[str]]:
    url = getattr(settings, "BASE_URL", None) or getattr(settings, "WIKI_URL", None) or ""
    if not url:
        raise ResolverError("未配置 BASE_URL 或 WIKI_URL")

    parsed = urlparse(url)
    path = parsed.path

    # 1) 云表格(Base)直链：直接从路径/参数抠取，最可靠
    #    （不调用 base +url-resolve，因为 URL 里的 & 会被 Windows 的 .cmd 批处理当成命令分隔符误解析）
    if "/base/" in path:
        m = re.search(r"/base/([A-Za-z0-9]+)", path)
        app_token = m.group(1) if m else None
        table_id = extract_table_id(url) or settings.TABLE_ID
        view_id = extract_view_id(url) or settings.VIEW_ID
        if app_token and table_id:
            logger.success(f"Base 解析成功(直链): app_token={app_token}, table_id={table_id}, view_id={view_id}")
            return app_token, table_id, view_id
        raise ResolverError(f"Base 直链解析失败，缺少 app_token 或 table_id: url={url}")

    # 2) 如果是 Wiki 链接，走原有的 wiki 解析逻辑
    if "/wiki/" in path:
        wiki_token = extract_wiki_token(url) or settings.WIKI_TOKEN_ORIGIN
        table_id = extract_table_id(url) or settings.TABLE_ID
        view_id = extract_view_id(url) or settings.VIEW_ID

        # 尝试 base +url-resolve（对部分 wiki 形态可能也可用）
        try:
            logger.info("尝试 base +url-resolve 解析...")
            r = cli.base_url_resolve(url)
            if r.get("ok"):
                data = r.get("data") or {}
                app_token = data.get("base_token") or data.get("app_token")
                tid = data.get("table_id") or table_id
                vid = data.get("view_id") or view_id
                if app_token and tid:
                    logger.success(f"base+url-resolve 成功: app_token={app_token}, table_id={tid}, view_id={vid}")
                    return app_token, tid, vid
            logger.warning(f"base+url-resolve 未命中: {r}")
        except LarkCliError as e:
            logger.warning(f"base+url-resolve 失败: {e}")

        # 尝试 wiki +node-get
        if wiki_token:
            try:
                logger.info(f"尝试 wiki +node-get --node-token {wiki_token} ...")
                r = cli.wiki_node_get(wiki_token)
                if r.get("ok"):
                    data = r.get("data") or {}
                    obj_type = data.get("obj_type")
                    obj_token = data.get("obj_token")
                    if obj_type == "bitable" and obj_token:
                        logger.success(f"wiki+node-get 成功: app_token={obj_token}, table_id={table_id}, view_id={view_id}")
                        return obj_token, table_id, view_id
                logger.warning(f"wiki+node-get 未命中或非bitable: {r}")
            except LarkCliError as e:
                logger.warning(f"wiki+node-get 失败: {e}")

        # 尝试全量递归遍历
        try:
            logger.info("尝试全量递归遍历 wiki 空间...")
            sp = cli.wiki_space_list()
            if not sp.get("ok"):
                raise ResolverError(f"wiki+space-list 失败: {sp}")
            spaces = (sp.get("data") or {}).get("spaces") or []
            for s in spaces:
                space_id = s.get("space_id")
                if not space_id:
                    continue
                logger.info(f"遍历空间: {space_id} ({s.get('name')})")
                page_token = None
                while True:
                    nl = cli.wiki_node_list(space_id, page_token=page_token, page_size=50)
                    if not nl.get("ok"):
                        break
                    nd = nl.get("data") or {}
                    nodes = nd.get("nodes") or []
                    for n in nodes:
                        n_token = n.get("node_token")
                        if not n_token:
                            continue
                        try:
                            ng = cli.wiki_node_get(n_token)
                            if ng.get("ok"):
                                gdata = ng.get("data") or {}
                                if gdata.get("obj_type") == "bitable" and gdata.get("obj_token"):
                                    obj_token = gdata.get("obj_token")
                                    logger.success(f"递归遍历命中bitable: node={n_token} app_token={obj_token}")
                                    return obj_token, table_id, view_id
                        except Exception as e:
                            logger.debug(f"node-get {n_token} 异常: {e}")
                    page_token = nd.get("page_token") or ""
                    if not page_token or nd.get("has_more") is False:
                        break
            raise ResolverError("未能在可访问的 Wiki 空间中找到 obj_type == 'bitable' 的节点。请确认当前账号对目标 Wiki/多维表格有访问权限。")
        except ResolverError:
            raise
        except Exception as e:
            raise ResolverError(f"递归遍历异常: {e}") from e

    raise ResolverError(f"不支持的链接类型: {url}")


resolve_table = resolve_table
