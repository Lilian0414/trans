"""Compatibility imports for callers using the older service module."""

from services.google_translator import GoogleTranslationError, GoogleTransTranslator
from services.groq_translator import GroqTranslationError, GroqTranslator

__all__ = [
    "GoogleTranslationError",
    "GoogleTransTranslator",
    "GroqTranslationError",
    "GroqTranslator",
]
