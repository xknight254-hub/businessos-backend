"""Document / voice processing (Phase 5 — M5.1 / M5.2).

OCR and speech-to-text require an external engine. We expose a clean
processor interface + HTTP endpoints.

OCR engines (auto-selected by availability):
  - Tesseract (pytesseract) — lightweight, preferred for printed receipts.
  - EasyOCR — heavier (torch), better for varied/handwritten text.

Voice/STT (Whisper) remains a clear, honest 501 until an engine is
registered. We do not fake OCR/transcription output.
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
            "OCR engine not configured. Install Tesseract (apt-get install "
            "tesseract-ocr + pip install pytesseract) or EasyOCR, then restart."
        )

    async def transcribe(self, audio_bytes: bytes, content_type: str) -> dict:
        raise NotImplementedError(
            "Voice/STT engine not configured. Install Whisper and register "
            "a VoiceProcessor via set_voice_processor()."
        )


class TesseractDocumentProcessor(DocumentProcessor):
    """OCR via Tesseract (lightweight; preferred for printed receipts)."""

    def __init__(self, lang: str = "eng+swa") -> None:
        self._lang = lang

    async def ocr(self, file_bytes: bytes, content_type: str) -> dict:
        import io
        import tempfile
        import os
        import pytesseract
        from PIL import Image

        suffix = ".png" if "png" in content_type else ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
            tf.write(file_bytes)
            path = tf.name
        try:
            img = Image.open(path)
            text = pytesseract.image_to_string(img, lang=self._lang)
            data = pytesseract.image_to_data(img, lang=self._lang, output_type=pytesseract.Output.DICT)
            confs = [float(c) for c in data.get("conf", []) if str(c).replace(".", "").isdigit()]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            return {
                "text": text.strip(),
                "fields": {},
                "confidence": round(avg_conf / 100.0, 4),
                "line_count": len([l for l in text.splitlines() if l.strip()]),
            }
        finally:
            os.unlink(path)


class EasyOCRDocumentProcessor(DocumentProcessor):
    """OCR via EasyOCR (heavier; better for varied/handwritten text)."""

    def __init__(self, languages: Optional[list[str]] = None) -> None:
        self._languages = languages or ["en", "sw"]
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(self._languages, gpu=False)
        return self._reader

    async def ocr(self, file_bytes: bytes, content_type: str) -> dict:
        import tempfile
        import os

        reader = self._get_reader()
        suffix = ".png" if "png" in content_type else ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
            tf.write(file_bytes)
            path = tf.name
        try:
            results = reader.readtext(path, detail=1)
            lines: list[str] = []
            confidences: list[float] = []
            for _bbox, text, conf in results:
                lines.append(text)
                confidences.append(float(conf))
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            return {
                "text": "\n".join(lines),
                "fields": {},
                "confidence": round(avg_conf, 4),
                "line_count": len(lines),
            }
        finally:
            os.unlink(path)


_document_processor: DocumentProcessor = UnconfiguredProcessor()
_voice_processor: VoiceProcessor = UnconfiguredProcessor()


def _auto_configure() -> None:
    """Prefer Tesseract (light); fall back to EasyOCR if installed."""
    global _document_processor
    try:
        import pytesseract  # noqa: F401
        _document_processor = TesseractDocumentProcessor()
        return
    except ImportError:
        pass
    try:
        import easyocr  # noqa: F401
        _document_processor = EasyOCRDocumentProcessor()
    except ImportError:
        pass


_auto_configure()


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
