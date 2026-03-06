"""Redis news client — reads articles from the news pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime

import redis


@dataclass
class Article:
    """Single news article from the pipeline."""

    title: str
    summary: str
    content: str
    source: str
    url: str
    date_published: datetime | None
    region: str  # 'br' or 'international'

    @classmethod
    def from_redis(cls, raw: bytes | str) -> Article:
        """Parse article from Redis JSON value."""
        data = json.loads(raw)
        dt = None
        if dp := data.get('date_published'):
            try:
                dt = datetime.fromisoformat(dp)
            except ValueError:
                pass
        return cls(
            title=data.get('title', ''),
            summary=data.get('summary', ''),
            content=data.get('content', ''),
            source=data.get('source', ''),
            url=data.get('url', ''),
            date_published=dt,
            region=data.get('region', ''),
        )

    @property
    def is_br(self) -> bool:
        return self.region == 'br'


class NewsClient:
    """Fetches articles from the Redis news pipeline."""

    def __init__(self, redis_url: str | None = None):
        url = redis_url or os.environ.get('REDIS_URL', '')
        if not url:
            raise ValueError('REDIS_URL not set')
        self._r = redis.from_url(url)

    def get_all_articles(self) -> list[Article]:
        """Fetch all cached articles via pipeline (fast)."""
        keys = [k.decode() for k in self._r.keys('news_article:*')]
        if not keys:
            return []

        pipe = self._r.pipeline()
        for k in keys:
            pipe.get(k)
        results = pipe.execute()

        articles = []
        for raw in results:
            if raw:
                try:
                    articles.append(Article.from_redis(raw))
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue
        return articles

    def get_today(self) -> list[Article]:
        """Get only today's articles, sorted newest first."""
        today_str = datetime.now().strftime('%Y-%m-%d')
        articles = [
            a
            for a in self.get_all_articles()
            if a.date_published and a.date_published.strftime('%Y-%m-%d') == today_str
        ]
        articles.sort(key=lambda a: a.date_published or datetime.min, reverse=True)
        return articles

    def get_today_br(self) -> list[Article]:
        """Today's Brazilian articles only."""
        return [a for a in self.get_today() if a.is_br]

    def get_today_intl(self) -> list[Article]:
        """Today's international articles only."""
        return [a for a in self.get_today() if not a.is_br]

    def queue_length(self) -> int:
        """Pending articles in processing queue."""
        return self._r.llen('news_feed_queue')

    def seen_count(self) -> int:
        """Total unique URLs seen historically."""
        return self._r.scard('news:seen_urls')
