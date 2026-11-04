import json
import time
from pathlib import Path
from typing import Set

from loguru import logger

from config import settings
from core.lark_cli import cli, LarkCliError
from core.resolver import resolve_table, ResolverError
from core.bitable import fetch_all_records, get_field_order, normalize_records, BitableError
from core.html_gen import generate_html, HtmlGenError
from core.screenshot import screenshot_sync, ScreenshotError


def load_processed() -> Set[str]:
    p = settings.state_path
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(data)
        if isinstance(data, dict):
            ids = data.get("message_ids") or data.get("ids") or []
            return set(ids)
    except Exception as e:
        logger.warning(f"加载去重文件失败: {e}")
    return set()


def save_processed(processed: Set[str]):
    p = settings.state_path
    try:
        p.write_text(json.dumps(sorted(list(processed)), ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"去重文件已更新: {p} (count={len(processed)})")
    except Exception as e:
        logger.warning(f"保存去重文件失败: {e}")


def main():
    logger.info("启动飞书群聊表格自动日报服务")
    logger.info(f"监控群聊: {settings.FEISHU_CHAT_ID} | 触发关键词: {settings.TRIGGER_KEYWORD}")
    processed = load_processed()
    logger.info(f"已加载去重记录: {len(processed)} 条")

    while True:
        try:
            # 轮询消息
            res = cli.chat_messages_list(settings.FEISHU_CHAT_ID, order=settings.ORDER, page_size=settings.MAX_MESSAGES_PER_POLL)
            if not res.get("ok"):
                logger.warning(f"拉取群消息失败: {res}")
                time.sleep(settings.POLL_INTERVAL_SEC)
                continue
            data = res.get("data") or {}
            messages = data.get("messages") or []
            if not messages:
                time.sleep(settings.POLL_INTERVAL_SEC)
                continue

            # 查找未处理的触发消息（优先最新）
            trigger_msg = None
            for m in messages:
                if m.get("deleted"):
                    continue
                if m.get("msg_type") != "text":
                    continue
                msg_id = m.get("message_id")
                if not msg_id or msg_id in processed:
                    continue
                content = (m.get("content") or "").strip()
                if content == settings.TRIGGER_KEYWORD:
                    trigger_msg = m
                    break  # 取最新一条未处理

            if not trigger_msg:
                time.sleep(settings.POLL_INTERVAL_SEC)
                continue

            msg_id_trig = trigger_msg.get("message_id")
            logger.info(f"检测到触发消息: {msg_id_trig} | 内容: {settings.TRIGGER_KEYWORD}")

            try:
                # 1) 解析表格坐标
                app_token, table_id, view_id = resolve_table()
                logger.info(f"解析成功: app_token={app_token}, table_id={table_id}, view_id={view_id}")

                # 2) 拉取记录
                field_order = get_field_order(app_token, table_id)
                records = fetch_all_records(app_token, table_id)
                headers, rows = normalize_records(records, field_order)

                # 3) 生成 HTML
                html_path = settings.html_path
                generate_html(headers, rows, html_path)

                # 4) 截图
                png_path = settings.png_path
                screenshot_sync(html_path, png_path, settings.VIEWPORT_WIDTH, settings.VIEWPORT_HEIGHT)

                # 5) 发送图片回群
                send_res = cli.messages_send_image(settings.FEISHU_CHAT_ID, png_path)
                if send_res.get("ok"):
                    logger.success(f"截图已发送到群聊 {settings.FEISHU_CHAT_ID}")
                    # 仅在发送成功后标记已处理
                    processed.add(msg_id_trig)
                    save_processed(processed)
                else:
                    logger.error(f"发送图片失败: {send_res}")
            except (ResolverError, BitableError, HtmlGenError, ScreenshotError, LarkCliError) as e:
                logger.exception(f"触发流程异常: {e}")
            except Exception as e:
                logger.exception(f"未知异常: {e}")

        except KeyboardInterrupt:
            logger.info("收到退出信号，服务停止")
            break
        except Exception as e:
            logger.exception(f"主循环异常: {e}")

        time.sleep(settings.POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
