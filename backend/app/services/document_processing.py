"""Document / voice processing interfaces (Phase 5 — M5.1 / M5.2).

OCR and speech-to-text require an external engine (e.g. Tesseract,
EasyOCR, Whisper). The gateway is text-only, so these are NOT done by
the LLM. We expose a clean processor interface + HTTP endpoints that
return 501 "engine not configured" until a real engine is wired.

This is honest: we do not fake OCR/transcription output.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class DocumentProcessor(ABC):
    @abstractmethod
    async def ocr(self, file_bytes: bytes, content_type: str) -> dict:
        """Return {'text': str, 'fields': dict, 'confidence': float}."""
        ...


class VoiceProcessor(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, content_type: str) -> dict:
        """Return {'text': str, 'confidence': float, 'entries': list}."""
        ...


class UnconfiguredProcessor(DocumentProcessor, VoiceProcessor):
    """Default no-op processor. Raises a clear, actionable error."""

    async def ocr(self, file_bytes: bytes, content_type: str) -> dict:
        raise NotImplementedError(
            "OCR engine not configured. Install EasyOCR/Tesseract and "
            "register a DocumentProcessor via set_document_processor()."
        )

    async def transcribe(self, audio_bytes: bytes, content_type: str) -> dict:
        raise NotImplementedError(
            "Voice/STT engine not configured. Install Whisper and register "
            "a VoiceProcessor via set_voice_processor()."
        )


_document_processor: DocumentProcessor = UnconfiguredProcessor()
_voice_processor: VoiceProcessor = UnconfiguredProcessor()


def set_document_processor(p: DocumentProcessor) -> None:
    global _document_processor
    _document_processor = p


def set_voice_processor(p: VoiceProcessor) -> None:
    global _voice_processor
    _voice_processor = p


def get_document_processor() -> DocumentProcessor:
    return _document_processor


def get_voice_processor() -> VoiceProcessor:
    return _voice_processor
