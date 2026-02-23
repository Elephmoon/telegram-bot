import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional

import trafilatura

logger = logging.getLogger(__name__)


@dataclass
class ParsedArticle:
    title: str
    text: str
    url: str
    language: str = "unknown"
    word_count: int = 0


class ArticleParser:
    @staticmethod
    async def parse(url: str) -> Optional[ParsedArticle]:
        try:
            # trafilatura — синхронная, выносим в thread pool
            downloaded = await asyncio.to_thread(trafilatura.fetch_url, url)
            if not downloaded:
                logger.warning("Не удалось скачать: %s", url)
                return None

            text = await asyncio.to_thread(
                trafilatura.extract,
                downloaded,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            )
            if not text:
                logger.warning("Не удалось извлечь текст: %s", url)
                return None

            title = ArticleParser._extract_title(downloaded) or "Без названия"
            language = ArticleParser._detect_language(text)

            return ParsedArticle(
                title=title,
                text=text,
                url=url,
                language=language,
                word_count=len(text.split()),
            )
        except Exception as e:
            logger.error("Ошибка парсинга %s: %s", url, e)
            return None

    @staticmethod
    def _extract_title(html: str) -> Optional[str]:
        for pattern in [
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            r"<title[^>]*>(.*?)</title>",
        ]:
            m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if m:
                return m.group(1).strip()
        return None

    @staticmethod
    def _detect_language(text: str) -> str:
        ru = len(re.findall(r"[а-яёА-ЯЁ]", text))
        total = len(re.findall(r"[a-zA-Zа-яёА-ЯЁ]", text))
        if total == 0:
            return "unknown"
        return "ru" if ru / total > 0.3 else "en"
