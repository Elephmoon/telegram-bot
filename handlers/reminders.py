import logging
from datetime import time as dt_time

import pytz
from telegram.ext import ContextTypes

from . import config, vault

logger = logging.getLogger(__name__)


async def morning_reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    today_tickets = vault.get_today_tickets()
    overdue = vault.get_overdue_tickets()
    all_active = vault.get_active_tickets()

    lines = ["🌅 **Доброе утро! Обзор задач на сегодня:**\n"]

    if overdue:
        lines.append("⚠️ **Просроченные:**")
        for t in overdue:
            lines.append(f"  • {vault.format_ticket_short(t)}")
        lines.append("")

    non_overdue = [t for t in today_tickets if t not in overdue]
    if non_overdue:
        lines.append("📋 **Запланировано на сегодня:**")
        for t in non_overdue:
            lines.append(f"  • {vault.format_ticket_short(t)}")
        lines.append("")

    # Тикеты без дедлайна
    no_date = [t for t in all_active if t.due_date is None and t not in today_tickets]
    if no_date:
        lines.append(f"📌 **Без дедлайна:** {len(no_date)} тикет(ов)")

    if not overdue and not non_overdue and not no_date:
        lines.append(
            "✨ На сегодня задач нет! Время для стратегического планирования 🚀"
        )

    lines.append(f"\n📊 Активных тикетов: {len(all_active)}")
    lines.append("\n_Управление: /tickets, /today, /done_")

    message = "\n".join(lines)

    # Отправляем всем разрешённым пользователям
    for user_id in config.ALLOWED_USERS:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="Markdown",
            )
            logger.info("Morning reminder sent to %d", user_id)
        except Exception as e:
            logger.error("Failed to send reminder to %d: %s", user_id, e)


def setup_reminder(job_queue, hour: int = None, minute: int = None):
    if not config.REMINDER_ENABLED:
        logger.info("Reminders disabled")
        return

    if not config.ALLOWED_USERS:
        logger.warning("ALLOWED_USERS пуст — напоминания некому отправлять!")
        return

    h = hour if hour is not None else config.REMINDER_HOUR
    m = minute if minute is not None else config.REMINDER_MINUTE

    tz = pytz.timezone(config.TIMEZONE)
    reminder_time = dt_time(hour=h, minute=m, tzinfo=tz)

    for job in job_queue.get_jobs_by_name("morning_reminder"):
        job.schedule_removal()

    job_queue.run_daily(
        morning_reminder_callback,
        time=reminder_time,
        name="morning_reminder",
    )
    logger.info("Morning reminder scheduled at %02d:%02d %s", h, m, config.TIMEZONE)


async def remind_command(update, context):
    """
    /remind — показать текущие настройки
    /remind HH:MM — изменить время
    /remind off — отключить
    /remind on — включить
    """
    args = context.args

    if not args:
        jobs = context.job_queue.get_jobs_by_name("morning_reminder")
        status = "✅ Включено" if jobs else "❌ Выключено"
        await update.message.reply_text(
            f"⏰ **Настройки напоминаний**\n\n"
            f"Статус: {status}\n"
            f"Время: `{config.REMINDER_HOUR:02d}:{config.REMINDER_MINUTE:02d}`\n"
            f"Часовой пояс: `{config.TIMEZONE}`\n\n"
            f"Команды:\n"
            f"• `/remind 08:30` — изменить время\n"
            f"• `/remind off` — выключить\n"
            f"• `/remind on` — включить",
            parse_mode="Markdown",
        )
        return

    arg = args[0].lower()

    if arg == "off":
        for job in context.job_queue.get_jobs_by_name("morning_reminder"):
            job.schedule_removal()
        await update.message.reply_text("❌ Напоминания выключены.")
        return

    if arg == "on":
        setup_reminder(context.job_queue)
        await update.message.reply_text(
            f"✅ Напоминания включены: `{config.REMINDER_HOUR:02d}:{config.REMINDER_MINUTE:02d}`",
            parse_mode="Markdown",
        )
        return

    # Парсим время HH:MM
    import re

    m = re.match(r"(\d{1,2}):(\d{2})", arg)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            setup_reminder(context.job_queue, hour=h, minute=mn)
            await update.message.reply_text(
                f"✅ Напоминания установлены на `{h:02d}:{mn:02d}` ({config.TIMEZONE})",
                parse_mode="Markdown",
            )
            return

    await update.message.reply_text(
        "❌ Неверный формат. Используйте: `/remind 09:00`", parse_mode="Markdown"
    )
