from dataclasses import dataclass
from typing import Protocol

from tractor.core.models import SourceResult


@dataclass(frozen=True)
class Translation:
    text: str
    source_language: str
    target_language: str
    backend: str
    confidence: float | None = None


class TranslationBackend(Protocol):
    async def translate(self, text: str, source: str, target: str) -> Translation: ...


async def translate_result(result: SourceResult, backend: TranslationBackend) -> None:
    title = await backend.translate(
        result.original_title or result.title, result.original_language, "en"
    )
    text = await backend.translate(result.original_text, result.original_language, "en")
    result.translated_title = title.text
    result.translated_text = text.text
    result.translated_excerpt = text.text[:420]
    result.translated_language = "en"
    result.metadata["translation"] = {
        "machine_translated": True,
        "backend": text.backend,
        "confidence": text.confidence,
        "source_language": text.source_language,
    }
