import logging
import re
from typing import Optional

from telegram import Update, constants
from telegram.ext import ContextTypes

from . import article_parser, llm_handler
from .common import send_long_message

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://\S+")


def extract_url(text: str) -> Optional[str]:
    m = URL_PATTERN.search(text)
    return m.group(0) if m else None


def is_only_url(text: str) -> bool:
    """Проверяет, что сообщение — просто URL."""
    stripped = text.strip()
    return bool(URL_PATTERN.fullmatch(stripped))


async def article_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.args[0] if context.args else None
    if not url:
        await update.message.reply_text(
            "📰 **Анализ статей**\n\n"
            "Использование:\n"
            "• `/article https://example.com/article`\n"
            "• Или просто отправьте ссылку в чат\n\n"
            "Бот:\n"
            "1. Извлечёт текст статьи\n"
            "2. Переведёт на русский (если нужно)\n"
            "3. Сделает саммари\n"
            "4. Оценит полезность для пути TL → CTO",
            parse_mode="Markdown",
        )
        return

    await _process_article(update, url)


async def _process_article(update: Update, url: str):
    await update.message.reply_text(
        f"📰 Анализирую статью...\n`{url}`", parse_mode="Markdown"
    )

    article = await article_parser.parse(url)
    if not article:
        await update.message.reply_text(
            "❌ Не удалось извлечь текст статьи. Возможные причины:\n"
            "• Сайт заблокировал парсинг\n"
            "• Страница требует авторизации\n"
            "• Контент загружается через JavaScript"
        )
        return

    lang_label = "🇷🇺 Русский" if article.language == "ru" else "🇬🇧 Английский"
    await update.message.reply_text(
        f"📄 **{article.title}**\n"
        f"🌐 Язык: {lang_label}\n"
        f"📏 ~{article.word_count} слов\n\n"
        f"🤖 Анализирую содержание...",
        parse_mode="Markdown",
    )

    await update.message.chat.send_action(action=constants.ChatAction.TYPING)

    result = await llm_handler.summarize_article(
        text=article.text,
        title=article.title,
        language=article.language,
        url=url,
    )

    await send_long_message(update.message, result, parse_mode="Markdown")


async def handle_url_message(update: Update, message_text: str) -> bool:
    if is_only_url(message_text):
        url = message_text.strip()
        await _process_article(update, url)
        return True
    return False
