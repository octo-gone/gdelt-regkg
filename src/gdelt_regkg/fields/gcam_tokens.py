"""Unicode tokenization for explicitly selected native GCAM dictionaries."""

import unicodedata
from functools import lru_cache

from ..dependencies import require_dependency
from .tone import _normalize, tokenize_tone


def tokenize_gcam(text: str, language: str = "eng") -> list[str]:
    if language == "eng":
        return tokenize_tone(text)
    if not isinstance(text, str):
        raise TypeError("text must be str")
    text = _normalize(text)
    if language == "zho":
        return [
            token
            for part in _chinese_segmenter().cut(text, HMM=False)
            for token in _unicode_tokens(part)
        ]
    return _unicode_tokens(text)


@lru_cache(maxsize=1)
def _chinese_segmenter():
    # An isolated standard dictionary: no inferred new words or corpus updates.
    jieba = require_dependency("jieba", "build")
    return jieba.Tokenizer()


def valid_gcam_word(term: str, language: str) -> bool:
    """Validate source vocabulary without requiring runtime Chinese segmentation."""
    if language == "eng":
        return tokenize_tone(term) == [term]
    return term == _normalize(term) and _unicode_tokens(term) == [term]


def _unicode_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current = ""
    for index, char in enumerate(text):
        kind = unicodedata.category(char)[0]
        if kind in "LN" or (current and (kind == "M" or char in "\u200c\u200d")):
            current += char
        elif (
            char in "'-"
            and current
            and index + 1 < len(text)
            and unicodedata.category(text[index + 1])[0] in "LMN"
        ):
            current += char
        elif current:
            tokens.append(current)
            current = ""
    if current:
        tokens.append(current)
    return tokens


def valid_native_pattern(term: str) -> bool:
    return (
        isinstance(term, str)
        and term == _normalize(term)
        and term == " ".join(term.split())
        and any(unicodedata.category(char)[0] in "LN" for char in term)
        and all(
            unicodedata.category(char)[0] in "LMN" or char in " '*?-\u200c\u200d" for char in term
        )
    )
