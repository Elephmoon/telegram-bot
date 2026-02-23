import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from . import llm_handler

logger = logging.getLogger(__name__)


def mask_token(text: str) -> str:
    if not text:
        return text
    return re.sub(r"\d+:[A-Za-z0-9_-]+", "[TOKEN_HIDDEN]", text)


class SafeLogger:
    @staticmethod
    def info(msg, *a, **kw):
        logger.info(mask_token(str(msg)), *(mask_token(str(x)) for x in a), **kw)

    @staticmethod
    def error(msg, *a, **kw):
        logger.error(mask_token(str(msg)), *(mask_token(str(x)) for x in a), **kw)

    @staticmethod
    def warning(msg, *a, **kw):
        logger.warning(mask_token(str(msg)), *(mask_token(str(x)) for x in a), **kw)


safe_logger = SafeLogger()


async def send_long_message(message, text: str, parse_mode: str = None):
    MAX_LEN = 4096
    if len(text) <= MAX_LEN:
        try:
            await message.reply_text(text, parse_mode=parse_mode)
        except Exception:
            await message.reply_text(text)
        return
    for i in range(0, len(text), MAX_LEN):
        chunk = text[i : i + MAX_LEN]
        try:
            await message.reply_text(chunk, parse_mode=parse_mode)
        except Exception:
            await message.reply_text(chunk)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 🚀\n\n"
        f"Я — персональный ассистент для тимлида на пути к CTO.\n\n"
        f"**Что я умею:**\n"
        f"📋 Управление задачами (Obsidian)\n"
        f"📰 Анализ статей с оценкой полезности\n"
        f"📚 Оценка книг для карьерного роста\n"
        f"⏰ Утренние напоминания о задачах\n"
        f"💬 AI-ассистент для любых вопросов\n\n"
        f"/help — полная справка по командам",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Полная справка**\n\n"
        "**💬 Чат:**\n"
        "/clear — очистить историю диалога\n"
        "/model — информация о модели\n"
        "/stats — статистика диалога\n\n"
        "**📋 Тикеты (Obsidian):**\n"
        "`/ticket Заголовок задачи` — создать тикет\n"
        "`/ticket Задача -p high -d tomorrow` — с приоритетом и дедлайном\n"
        "/tickets — список активных тикетов\n"
        "/today — задачи на сегодня\n"
        "`/done T-XXXX` — завершить тикет\n"
        "`/progress T-XXXX` — отметить «в работе»\n"
        "`/delete_ticket T-XXXX` — удалить тикет\n\n"
        "**📰 Статьи:**\n"
        "`/article URL` — анализ статьи\n"
        "или просто отправьте ссылку\n\n"
        "**📚 Книги:**\n"
        "`/book Название — Автор` — оценка книги\n\n"
        "**⏰ Напоминания:**\n"
        "/remind — текущие настройки\n"
        "`/remind 08:30` — изменить время\n"
        "/remind off | /remind on\n\n"
        "**🔄 Синхронизация:**\n"
        "/sync — синхронизировать vault с iCloud",
        parse_mode="Markdown",
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if llm_handler.clear_history(user_id):
        await update.message.reply_text("🧹 История диалога очищена!")
    else:
        await update.message.reply_text("📭 История и так пуста.")


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = llm_handler.config
    key_ok = "✅" if cfg.OPENROUTER_API_KEY else "❌"
    await update.message.reply_text(
        f"⚙️ **Конфигурация:**\n\n"
        f"• Провайдер: `{cfg.LLM_PROVIDER}`\n"
        f"• Модель: `{cfg.LLM_MODEL}`\n"
        f"• Макс. история: `{cfg.MAX_HISTORY}` сообщений\n"
        f"• API ключ: {key_ok}\n"
        f"• Активных диалогов: `{len(llm_handler.conversations)}`",
        parse_mode="Markdown",
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "?"
    history_length = llm_handler.get_history_length(user_id)
    from . import vault  # ленивый импорт — ок тут

    active_tickets = len(vault.get_active_tickets())
    overdue = len(vault.get_overdue_tickets())

    await update.message.reply_text(
        f"📊 **Статистика @{username}**\n\n"
        f"💬 Сообщений в диалоге: `{history_length}`\n"
        f"📋 Активных тикетов: `{active_tickets}`\n"
        f"⚠️ Просроченных: `{overdue}`",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "NoUsername"
    message_text = update.message.text

    safe_logger.info(f"Msg from @{username} ({user_id}): {message_text[:50]}...")

    # Проверка доступа
    allowed = llm_handler.config.ALLOWED_USERS
    if allowed and user_id not in allowed:
        safe_logger.warning(f"Blocked: @{username} ({user_id})")
        await update.message.reply_text("🚫 Доступ запрещён.")
        return

    # ── Ленивый импорт — разрываем цикл ──
    from .articles import handle_url_message

    # Если сообщение — просто URL → анализ статьи
    if await handle_url_message(update, message_text):
        return

    # Иначе — обычный LLM-диалог
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        response = await llm_handler.get_response(user_id, message_text)
        await send_long_message(update.message, response)
    except Exception as e:
        safe_logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка. Попробуйте /clear и повторите.")
