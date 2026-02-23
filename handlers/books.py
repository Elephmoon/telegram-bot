import logging

from telegram import Update
from telegram.ext import ContextTypes

from . import llm_handler
from .common import send_long_message

logger = logging.getLogger(__name__)


async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /book <название книги> [автор]
    /book Accelerate by Nicole Forsgren
    /book Карьера менеджера — Гроув
    """
    book_info = " ".join(context.args) if context.args else ""
    if not book_info:
        await update.message.reply_text(
            "📚 **Оценка книг для пути TL → CTO**\n\n"
            "Использование:\n"
            "• `/book Accelerate by Nicole Forsgren`\n"
            "• `/book Карьера менеджера — Эндрю Гроув`\n"
            "• `/book The Manager's Path`\n\n"
            "Бот оценит книгу по:\n"
            "• Полезности для роста TL → CTO (1-10)\n"
            "• Ключевым идеям\n"
            "• На каком этапе карьеры читать\n"
            "• Предложит альтернативы",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        f"📚 Оцениваю книгу: *{book_info}*...", parse_mode="Markdown"
    )

    from telegram import constants

    await update.message.chat.send_action(action=constants.ChatAction.TYPING)

    result = await llm_handler.evaluate_book(book_info)
    await send_long_message(update.message, result, parse_mode="Markdown")
