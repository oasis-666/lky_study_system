from __future__ import annotations

import json
import random
from pathlib import Path


class QuoteEngine:
    def __init__(self, quotes_file: Path) -> None:
        self.quotes_file = quotes_file
        self._last_quote: str | None = None

    def load_quotes(self) -> list[str]:
        if not self.quotes_file.exists():
            return []
        payload = json.loads(self.quotes_file.read_text(encoding="utf-8"))
        quotes = payload.get("quotes", [])
        return [str(x) for x in quotes]

    def next_quote(self) -> str:
        quotes = self.load_quotes()
        if not quotes:
            return "保持专注，持续前进。"

        if len(quotes) == 1:
            self._last_quote = quotes[0]
            return quotes[0]

        choices = [q for q in quotes if q != self._last_quote]
        quote = random.choice(choices if choices else quotes)
        self._last_quote = quote
        return quote
