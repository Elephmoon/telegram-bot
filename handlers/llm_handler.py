import logging
from collections import defaultdict
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from config import Config

logger = logging.getLogger(__name__)

# ── Системные промты ──

SYSTEM_PROMPT_CHAT = (
    "Ты — персональный AI-ассистент тимлида, который стремится стать CTO. "
    "Отвечай на том же языке, на котором задан вопрос. "
    "Когда уместно — учитывай карьерные цели пользователя. "
    "Будь конкретным, давай actionable советы."
)

SYSTEM_PROMPT_ARTICLE = """Ты — персональный ассистент тимлида, который стремится стать CTO.

Проанализируй статью и дай ответ **на русском языке**:

1. 📌 **Саммари** — краткое изложение (3-5 предложений)
2. 💡 **Ключевые идеи** — список основных мыслей (3-7 пунктов)
3. 🎯 **Полезность для пути TL → CTO** — оценка от 1 до 10 с обоснованием
4. 📂 **Категория** — технологии / архитектура / менеджмент / лидерство / стратегия / продукт / культура / другое
5. ✅ **Рекомендация** — стоит ли читать полностью, кому и почему
6. 🔑 **Actionable insights** — что конкретно можно применить в работе

Если статья не на русском — переведи все пункты на русский.
Если статья слабая или нерелевантная — скажи об этом прямо."""

SYSTEM_PROMPT_BOOK = """Ты — персональный ассистент тимлида, который стремится стать CTO.

Оцени книгу и дай ответ **на русском языке**:

1. 📖 **О чём книга** — краткое описание (2-3 предложения)
2. 🎯 **Полезность для пути TL → CTO** — оценка от 1 до 10 с обоснованием
3. 📂 **Категория** — технический менеджмент / лидерство / архитектура / стратегия / soft skills / продуктовое мышление / другое
4. 💡 **Чему научит** — основные навыки и знания (список)
5. ⏱ **Когда читать** — на каком этапе карьеры наиболее полезна (TL / Senior TL / Engineering Manager / VP Eng / CTO)
6. ⚡ **Ключевые идеи** — 3-5 самых важных мыслей из книги
7. 📚 **Альтернативы** — 2-3 похожие книги (лучше/дополняющие)
8. 🏆 **Вердикт** — стоит ли читать, приоритет (must read / стоит почитать / можно пропустить / не стоит)

Если не знаешь книгу — честно скажи и дай оценку на основе названия/автора.
Если книга устарела — отметь это и предложи современную замену."""


class LLMHandler:
    def __init__(self):
        self.conversations: Dict[int, List[Dict[str, str]]] = defaultdict(list)
        self.config = Config()
        self.client: Optional[AsyncOpenAI] = None

        if not self.config.OPENROUTER_API_KEY:
            logger.error("OPENROUTER_API_KEY не задан!")
        else:
            try:
                self.client = AsyncOpenAI(
                    base_url=self.config.OPENROUTER_BASE_URL,
                    api_key=self.config.OPENROUTER_API_KEY,
                    timeout=120.0,
                    max_retries=2,
                    default_headers=self._build_extra_headers(),
                )
                logger.info("OpenRouter OK, модель: %s", self.config.LLM_MODEL)
            except Exception as e:
                logger.error("Ошибка инициализации OpenRouter: %s", e)

    def _build_extra_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.config.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = self.config.OPENROUTER_SITE_URL
        if self.config.OPENROUTER_APP_NAME:
            headers["X-Title"] = self.config.OPENROUTER_APP_NAME
        return headers

    # ──────────────────────────────────────────
    #  Низкоуровневый вызов API
    # ──────────────────────────────────────────

    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        if not self.client:
            return (
                "❌ OpenRouter клиент не инициализирован. Проверьте OPENROUTER_API_KEY."
            )

        try:
            response = await self.client.chat.completions.create(
                model=self.config.LLM_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if not content:
                return "⚠️ Модель вернула пустой ответ."

            if response.usage:
                logger.info(
                    "Токены: prompt=%d, completion=%d, total=%d",
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    response.usage.total_tokens,
                )
            return content

        except Exception as e:
            return self._handle_api_error(e)

    def _handle_api_error(self, e: Exception) -> str:
        err = str(e)
        if "401" in err or "Unauthorized" in err:
            return "❌ Неверный API ключ OpenRouter."
        if "402" in err or "Payment Required" in err:
            return "❌ Недостаточно средств на OpenRouter."
        if "429" in err or "rate limit" in err.lower():
            return "⏳ Слишком много запросов. Подождите."
        if "model" in err.lower() and "not found" in err.lower():
            return f"❌ Модель `{self.config.LLM_MODEL}` не найдена."
        logger.error("OpenRouter error: %s", e, exc_info=True)
        return f"❌ Ошибка API: {e}"

    def _prepare_messages(self, user_id: int) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT_CHAT}]
        history = self.conversations[user_id][-(self.config.MAX_HISTORY * 2) :]
        messages.extend(history)
        return messages

    async def get_response(self, user_id: int, message: str) -> str:
        self.conversations[user_id].append({"role": "user", "content": message})

        max_items = self.config.MAX_HISTORY * 2
        if len(self.conversations[user_id]) > max_items:
            self.conversations[user_id] = self.conversations[user_id][-max_items:]

        try:
            messages = self._prepare_messages(user_id)
            response = await self._call_api(messages)
            self.conversations[user_id].append(
                {"role": "assistant", "content": response}
            )
            return response
        except Exception as e:
            logger.error("get_response error: %s", e, exc_info=True)
            return f"Ошибка: {e}"

    async def summarize_article(
        self, text: str, title: str, language: str, url: str
    ) -> str:
        # Обрезаем текст для экономии токенов
        max_chars = self.config.ARTICLE_MAX_CHARS
        truncated = text[:max_chars]
        if len(text) > max_chars:
            truncated += "\n\n[...текст обрезан...]"

        user_msg = (
            f"**Название:** {title}\n"
            f"**URL:** {url}\n"
            f"**Язык оригинала:** {language}\n"
            f"**Слов:** ~{len(text.split())}\n\n"
            f"**Текст статьи:**\n{truncated}"
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_ARTICLE},
            {"role": "user", "content": user_msg},
        ]
        return await self._call_api(messages, temperature=0.3)

    async def evaluate_book(self, book_info: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_BOOK},
            {"role": "user", "content": f"Оцени книгу: {book_info}"},
        ]
        return await self._call_api(messages, temperature=0.3)

    def clear_history(self, user_id: int) -> bool:
        if user_id in self.conversations and self.conversations[user_id]:
            self.conversations[user_id] = []
            return True
        return False

    def get_history_length(self, user_id: int) -> int:
        return len(self.conversations.get(user_id, []))
