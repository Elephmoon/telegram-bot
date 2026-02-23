import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from . import config, vault, vault_sync
from .common import send_long_message

logger = logging.getLogger(__name__)


def _parse_ticket_args(text: str) -> dict:
    result = {
        "title": "",
        "description": "",
        "priority": "medium",
        "due_date": None,
        "tags": [],
    }

    if " -- " in text:
        text, desc = text.split(" -- ", 1)
        result["description"] = desc.strip()

    priority_m = re.search(r"-p\s+(low|medium|high|critical)", text, re.IGNORECASE)
    if priority_m:
        result["priority"] = priority_m.group(1).lower()
        text = text[: priority_m.start()] + text[priority_m.end() :]

    due_m = re.search(r"-d\s+(\d{4}-\d{2}-\d{2})", text)
    if due_m:
        result["due_date"] = due_m.group(1)
        text = text[: due_m.start()] + text[due_m.end() :]

    due_rel = re.search(r"-d\s+(today|tomorrow|week)", text, re.IGNORECASE)
    if due_rel:
        word = due_rel.group(1).lower()
        today = datetime.now().date()
        if word == "today":
            result["due_date"] = today.isoformat()
        elif word == "tomorrow":
            result["due_date"] = (today + timedelta(days=1)).isoformat()
        elif word == "week":
            result["due_date"] = (today + timedelta(days=7)).isoformat()
        text = text[: due_rel.start()] + text[due_rel.end() :]

    tags_m = re.search(r"-t\s+([\w,\s]+?)(?:\s+-|$)", text)
    if tags_m:
        result["tags"] = [t.strip() for t in tags_m.group(1).split(",") if t.strip()]
        text = text[: tags_m.start()] + text[tags_m.end() :]

    result["title"] = text.strip()
    return result


async def ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Создать тикет.
    /ticket Заголовок задачи
    /ticket Подготовить отчёт -p high -d 2024-12-31 -t work,report
    /ticket Ревью PR -d tomorrow -- посмотреть ветку feature/auth
    """
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "📝 **Создание тикета**\n\n"
            "Использование:\n"
            "`/ticket Заголовок задачи`\n"
            "`/ticket Описание -p high -d 2024-12-31 -t tag1,tag2`\n"
            "`/ticket Задача -d tomorrow -- описание`\n\n"  # ← обновлено
            "**Флаги:**\n"
            "• `-p` — приоритет: `low`, `medium`, `high`, `critical`\n"
            "• `-d` — дедлайн: `2024-12-31`, `today`, `tomorrow`, `week`\n"
            "• `-t` — теги: `work,meeting`\n"
            "• `--` — после двойного тире идёт описание",  # ← НОВОЕ
            parse_mode="Markdown",
        )
        return

    parsed = _parse_ticket_args(text)
    if not parsed["title"]:
        await update.message.reply_text("❌ Укажите заголовок тикета.")
        return

    ticket = vault.create_ticket(
        title=parsed["title"],
        description=parsed["description"],  # ← НОВОЕ
        priority=parsed["priority"],
        due_date=parsed["due_date"],
        tags=parsed["tags"],
    )

    sync_msg = ""
    if config.ICLOUD_SYNC_ENABLED and vault_sync.is_configured:
        ok, msg = vault_sync.sync()
        sync_msg = f"\n\n🔄 {msg}" if ok else ""

    await update.message.reply_text(
        f"✅ **Тикет создан!**\n\n{vault.format_ticket_full(ticket)}{sync_msg}",
        parse_mode="Markdown",
    )


async def tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список активных тикетов. /tickets [all|done|todo]"""
    status_filter = context.args[0] if context.args else None

    if status_filter == "all":
        tickets = vault.get_all_tickets()
        header = "📋 **Все тикеты:**"
    elif status_filter == "done":
        tickets = vault.get_all_tickets(status="done")
        header = "✅ **Завершённые тикеты:**"
    else:
        tickets = vault.get_active_tickets()
        header = "📋 **Активные тикеты:**"

    if not tickets:
        await update.message.reply_text("📭 Тикетов не найдено.")
        return

    lines = [header, ""]
    for i, t in enumerate(tickets, 1):
        lines.append(f"{i}. {vault.format_ticket_short(t)}")
    lines.append(f"\n📊 Всего: {len(tickets)}")

    await send_long_message(update.message, "\n".join(lines), parse_mode="Markdown")


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Задачи на сегодня."""
    today_tickets = vault.get_today_tickets()
    overdue = vault.get_overdue_tickets()

    lines = ["🌅 **Задачи на сегодня:**\n"]

    if overdue:
        lines.append("⚠️ **Просроченные:**")
        for t in overdue:
            lines.append(f"  • {vault.format_ticket_short(t)}")
        lines.append("")

    active = [t for t in today_tickets if t not in overdue]
    if active:
        lines.append("📋 **На сегодня:**")
        for t in active:
            lines.append(f"  • {vault.format_ticket_short(t)}")
    elif not overdue:
        lines.append("✨ На сегодня задач нет! Можно планировать новые.")

    total_active = len(vault.get_active_tickets())
    lines.append(f"\n📊 Всего активных: {total_active}")

    await send_long_message(update.message, "\n".join(lines), parse_mode="Markdown")


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/done T-240115-a3f2"""
    if not context.args:
        await update.message.reply_text(
            "Использование: `/done T-XXXXXX-XXXX`", parse_mode="Markdown"
        )
        return

    ticket_id = context.args[0]
    if vault.update_status(ticket_id, "done"):
        await update.message.reply_text(
            f"✅ Тикет `{ticket_id}` завершён!", parse_mode="Markdown"
        )
        if config.ICLOUD_SYNC_ENABLED and vault_sync.is_configured:
            vault_sync.sync()
    else:
        await update.message.reply_text(
            f"❌ Тикет `{ticket_id}` не найден.", parse_mode="Markdown"
        )


async def delete_ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/delete_ticket T-240115-a3f2"""
    if not context.args:
        await update.message.reply_text(
            "Использование: `/delete_ticket T-XXXXXX-XXXX`",
            parse_mode="Markdown",
        )
        return

    ticket_id = context.args[0]
    if vault.delete_ticket(ticket_id):
        await update.message.reply_text(
            f"🗑 Тикет `{ticket_id}` удалён.", parse_mode="Markdown"
        )
        if config.ICLOUD_SYNC_ENABLED and vault_sync.is_configured:
            vault_sync.sync()
    else:
        await update.message.reply_text(
            f"❌ Тикет `{ticket_id}` не найден.", parse_mode="Markdown"
        )


async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ручная синхронизация с iCloud."""
    if not vault_sync.is_configured:
        await update.message.reply_text(
            "⚙️ Синхронизация не настроена.\n\n"
            "Укажите в `.env`:\n"
            "• `ICLOUD_VAULT_PATH` — для macOS\n"
            "• `RCLONE_REMOTE` — для Linux + rclone",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("🔄 Синхронизация...")
    ok, msg = vault_sync.sync()
    await update.message.reply_text(msg, parse_mode="Markdown")
