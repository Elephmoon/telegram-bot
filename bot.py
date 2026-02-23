#!/usr/bin/env python3
"""Персональный AI-бот: задачи, статьи, книги, напоминания."""

import logging
import re
import sys

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import Config
from handlers.articles import article_command
from handlers.books import book_command
from handlers.common import (
    clear_command,
    handle_message,
    help_command,
    model_command,
    start,
    stats_command,
)
from handlers.reminders import remind_command, setup_reminder
from handlers.tickets import (  # ← убран progress_command
    delete_ticket_command,
    done_command,
    sync_command,
    ticket_command,
    tickets_command,
    today_command,
)

# ── Логирование ──


class TokenMaskingFilter(logging.Filter):
    _pat = re.compile(r"\d+:[A-Za-z0-9_-]+")

    def filter(self, record):
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = self._pat.sub("[TOKEN]", record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._pat.sub("[TOKEN]", v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._pat.sub("[TOKEN]", a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
_mask = TokenMaskingFilter()
for name in ("", "telegram", "httpx"):
    logging.getLogger(name).addFilter(_mask)

logger = logging.getLogger(__name__)


def main():
    config = Config()

    if not config.TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не задан!")
        return

    logger.info("🚀 Запуск бота...")
    logger.info("Модель: %s | Провайдер: %s", config.LLM_MODEL, config.LLM_PROVIDER)
    logger.info(
        "Пользователи: %s",
        config.ALLOWED_USERS if config.ALLOWED_USERS else "Все",
    )
    logger.info("Vault: %s", config.OBSIDIAN_VAULT_PATH)

    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # ── Команды: общие ──
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("stats", stats_command))

    # ── Команды: тикеты ──
    app.add_handler(CommandHandler("ticket", ticket_command))
    app.add_handler(CommandHandler("tickets", tickets_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("done", done_command))
    # progress убран — в формате Tasks нет промежуточного статуса
    app.add_handler(CommandHandler("delete_ticket", delete_ticket_command))
    app.add_handler(CommandHandler("sync", sync_command))

    # ── Команды: статьи и книги ──
    app.add_handler(CommandHandler("article", article_command))
    app.add_handler(CommandHandler("book", book_command))

    # ── Команды: напоминания ──
    app.add_handler(CommandHandler("remind", remind_command))

    # ── Текстовые сообщения ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ── Утреннее напоминание ──
    setup_reminder(app.job_queue)

    logger.info("✅ Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
