"""Explicit local translation before English NLP, with reusable provenance."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol

from .language import LanguageDetection, LanguageDetector, detect_language, verify_language
from .wire import text_component

# M2M100 languages: ISO 639-1, ISO 639-2/T, and common English names.
_LANGUAGES = """
af afr afrikaans
am amh amharic
ar ara arabic
ast ast asturian
az aze azerbaijani
ba bak bashkir
be bel belarusian
bg bul bulgarian
bn ben bengali
br bre breton
bs bos bosnian
ca cat catalan
ceb ceb cebuano
cs ces czech
cy cym welsh
da dan danish
de deu german
el ell greek
en eng english
es spa spanish
et est estonian
fa fas persian
ff ful fulah
fi fin finnish
fr fra french
fy fry frisian
ga gle irish
gd gla gaelic
gl glg galician
gu guj gujarati
ha hau hausa
he heb hebrew
hi hin hindi
hr hrv croatian
ht hat haitian
hu hun hungarian
hy hye armenian
id ind indonesian
ig ibo igbo
ilo ilo iloko
is isl icelandic
it ita italian
ja jpn japanese
jv jav javanese
ka kat georgian
kk kaz kazakh
km khm khmer
kn kan kannada
ko kor korean
lb ltz luxembourgish
lg lug ganda
ln lin lingala
lo lao lao
lt lit lithuanian
lv lav latvian
mg mlg malagasy
mk mkd macedonian
ml mal malayalam
mn mon mongolian
mr mar marathi
ms msa malay
my mya burmese
ne nep nepali
nl nld dutch
no nor norwegian
ns nso northern-sotho
oc oci occitan
or ori odia
pa pan punjabi
pl pol polish
ps pus pashto
pt por portuguese
ro ron romanian
ru rus russian
sd snd sindhi
si sin sinhala
sk slk slovak
sl slv slovenian
so som somali
sq sqi albanian
sr srp serbian
ss ssw swati
su sun sundanese
sv swe swedish
sw swa swahili
ta tam tamil
te tel telugu
th tha thai
tl tgl tagalog
tn tsn tswana
tr tur turkish
uk ukr ukrainian
ur urd urdu
uz uzb uzbek
vi vie vietnamese
wo wol wolof
xh xho xhosa
yi yid yiddish
yo yor yoruba
zh zho chinese
zu zul zulu
"""
_CODES = {}
_MODEL_CODES = {}
for _line in _LANGUAGES.strip().splitlines():
    _short, _iso, _name = _line.split()
    _MODEL_CODES[_iso] = _short
    for _alias in (_short, _iso, _name):
        _CODES[_alias] = _iso
_CODES.update(
    {
        "arb": "ara",
        "farsi": "fas",
        "per": "fas",
        "ger": "deu",
        "fre": "fra",
        "chi": "zho",
        "zhs": "zho",
        "zht": "zho",
        "mandarin": "zho",
        "cze": "ces",
        "dut": "nld",
        "gre": "ell",
        "rum": "ron",
        "bur": "mya",
        "iw": "heb",
        "in": "ind",
        "nb": "nor",
        "nn": "nor",
        "fil": "tgl",
    }
)


def normalize_language(value: str) -> str:
    """Return ISO 639-2/T for supported codes/names and regional/script tags.

    Examples: UR, Urdu, ur_PK, ur-PK, urPK, and urd_Arab all become urd.
    Unknown or missing labels fail explicitly; no domain-based guessing runs.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A source language is required for translation")
    label = re.sub(r"[\s_]+", "-", value.strip().casefold())
    if label in _CODES:
        return _CODES[label]
    base = label.split("-", 1)[0]
    if base in _CODES:
        return _CODES[base]
    # Compact language+region or language+script forms, e.g. urpk, zhHant.
    for width in (3, 2):
        suffix = label[width:]
        if label[:width] in _CODES and (
            re.fullmatch(r"[a-z]{2}", suffix)
            or suffix
            in {
                "latn",
                "arab",
                "hans",
                "hant",
                "cyrl",
                "deva",
                "jpan",
                "kore",
                "hebr",
                "thai",
            }
        ):
            return _CODES[label[:width]]
    raise ValueError(f"Unsupported source language {value!r}")


@dataclass(frozen=True)
class TranslationResult:
    original_text: str
    text: str
    source_language: str
    engine: str | None
    language_detection: LanguageDetection | None = None

    @property
    def translated(self) -> bool:
        return self.source_language != "eng"


class Translator(Protocol):
    engine: str

    def translate(self, text: str, source_language: str) -> str: ...


def translate_text(
    text: str,
    *,
    language: str | None = None,
    translator: Translator,
    detect_missing_language: bool = True,
    language_detector: LanguageDetector | None = None,
    language_check: str = "script",
) -> TranslationResult:
    """Translate to English; detect missing labels locally, and bypass English."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    detection = None
    if detect_missing_language and (
        language is None or (isinstance(language, str) and not language.strip())
    ):
        detection = detect_language(text, detector=language_detector)
        language = detection.language
    source = normalize_language(language or "")
    if detection is None:
        detection = verify_language(text, source, check=language_check, detector=language_detector)
        if detection is not None:
            source = normalize_language(detection.language)
    if source == "eng":
        return TranslationResult(text, text, source, None, detection)
    if not text.strip():
        raise ValueError("Cannot translate a blank body")
    engine = translator.engine
    if not isinstance(engine, str):
        raise ValueError("Translator must identify its engine")
    engine = text_component(engine, separators=";")
    if not engine:
        raise ValueError("Translator must identify its engine")
    translated = translator.translate(text, source)
    if not isinstance(translated, str) or not translated.strip():
        raise ValueError("Translator returned an empty or invalid English body")
    return TranslationResult(text, translated, source, engine, detection)


class TranslationUnavailableError(RuntimeError):
    """Optional dependencies or local model resources are unavailable."""


class M2M100Translator:
    """Local sentence/chunk translation; load once, use sequentially, reuse."""

    def __init__(self, tokenizer, model, *, engine, chunk_tokens=384, batch_size=4, num_beams=4):
        if type(chunk_tokens) is not int or not 1 <= chunk_tokens <= 512:
            raise ValueError("chunk_tokens must be between 1 and 512")
        self.tokenizer, self.model, self.engine = tokenizer, model, engine
        self.chunk_tokens = chunk_tokens
        if (
            type(batch_size) is not int
            or batch_size < 1
            or type(num_beams) is not int
            or num_beams < 1
        ):
            raise ValueError("batch_size and num_beams must be positive integers")
        self.batch_size, self.num_beams = batch_size, num_beams

    @classmethod
    def from_model(
        cls,
        model="facebook/m2m100_418M",
        *,
        device="cpu",
        allow_download=False,
        revision=None,
        batch_size=4,
        num_beams=4,
    ):
        try:
            import_module("torch")
        except ImportError as error:
            raise TranslationUnavailableError(
                "Local M2M100 translation requires PyTorch. Install a compatible CPU/CUDA "
                "build as described in docs/installation.md#non-english-bodies"
            ) from error
        try:
            import transformers
            from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
        except ImportError as error:
            raise TranslationUnavailableError(
                "Install gdelt-regkg for local M2M100 translation"
            ) from error
        options: dict[str, Any] = {"local_files_only": not allow_download}
        if revision is not None:
            options["revision"] = revision
        try:
            tokenizer = M2M100Tokenizer.from_pretrained(model, **options)
            network = (
                M2M100ForConditionalGeneration.from_pretrained(model, **options).to(device).eval()
            )
            if str(device).startswith("cuda"):
                network = network.half()
        except OSError as error:
            raise TranslationUnavailableError(
                "M2M100 resources unavailable; download explicitly with allow_download=True or supply a local model directory"
            ) from error
        commit = getattr(network.config, "_commit_hash", None) or revision or "local"
        precision = "fp16" if str(device).startswith("cuda") else "fp32"
        engine = f"M2M100 {model}@{commit}; transformers {transformers.__version__}; chunk384 beam{num_beams} packed-v2 {precision}"
        return cls(tokenizer, network, engine=engine, batch_size=batch_size, num_beams=num_beams)

    def translate(self, text, source_language):
        return self.translate_many([text], source_language)[0]

    def _chunks(self, text):
        """Pack consecutive sentences, bounding tokens without truncating text."""
        chunks: list[str] = []
        pending: list[int] = []
        for sentence in re.split(r"(?<=[.!?\u3002\u061f\u06d4])\s+|\n+", text):
            if not sentence.strip():
                continue
            ids = self.tokenizer.encode(sentence, add_special_tokens=False)
            if pending and len(pending) + len(ids) > self.chunk_tokens:
                chunks.append(self.tokenizer.decode(pending, skip_special_tokens=True))
                pending = []
            for index in range(0, len(ids), self.chunk_tokens):
                window = ids[index : index + self.chunk_tokens]
                if len(window) == self.chunk_tokens:
                    chunks.append(self.tokenizer.decode(window, skip_special_tokens=True))
                else:
                    pending.extend(window)
        if pending:
            chunks.append(self.tokenizer.decode(pending, skip_special_tokens=True))
        return chunks

    def _generate(self, chunks, *, retry=False):
        # Batching only changes scheduling; model settings remain explicit.
        inputs = self.tokenizer(
            chunks if len(chunks) > 1 else chunks[0],
            return_tensors="pt",
            padding=True,
            truncation=False,
        ).to(self.model.device)
        generated = self.model.generate(
            **inputs,
            forced_bos_token_id=self.tokenizer.get_lang_id("en"),
            num_beams=1 if retry else self.num_beams,
            max_new_tokens=768,
            min_new_tokens=1,
        )
        outputs = []
        for sequence in generated:
            ids = sequence.tolist()
            while ids and ids[-1] == self.tokenizer.pad_token_id:
                ids.pop()
            if not ids or ids[-1] != self.tokenizer.eos_token_id:
                raise ValueError(
                    "Translation reached its output limit; article not exported as complete"
                )
            outputs.append(self.tokenizer.decode(ids, skip_special_tokens=True).strip())
        if len(outputs) != len(chunks):
            raise ValueError("Translation model returned the wrong batch size")
        return outputs

    def _retry_empty(self, chunk, depth=0):
        if not any(char.isalpha() for char in chunk):
            return chunk.strip()
        output = self._generate([chunk], retry=True)[0]
        if output:
            return output
        ids = self.tokenizer.encode(chunk, add_special_tokens=False)
        if depth >= 2 or len(ids) < 2:
            raise ValueError(
                f"Model returned an empty translation chunk after retries: {chunk[:120]!r}"
            )
        middle = len(ids) // 2
        parts = [
            self.tokenizer.decode(part, skip_special_tokens=True)
            for part in (ids[:middle], ids[middle:])
        ]
        return " ".join(self._retry_empty(part, depth + 1) for part in parts)

    def translate_many(self, texts, source_language):
        """Translate same-language bodies in bounded chunk batches, preserving order."""
        import torch

        source = normalize_language(source_language)
        if _MODEL_CODES[source] not in self.tokenizer.lang_code_to_id:
            raise ValueError(f"Model does not support language {source}")
        self.tokenizer.src_lang = _MODEL_CODES[source]
        texts = list(texts)
        chunks = [
            (index, chunk) for index, text in enumerate(texts) for chunk in self._chunks(text)
        ]
        outputs: list[list[str]] = [[] for _ in texts]
        with torch.inference_mode():
            for start in range(0, len(chunks), self.batch_size):
                batch = chunks[start : start + self.batch_size]
                translated = self._generate([chunk for _, chunk in batch])
                for (index, chunk), output in zip(batch, translated):
                    outputs[index].append(output or self._retry_empty(chunk))
        result = ["\n".join(parts) for parts in outputs]
        if any(not text.strip() for text in result):
            raise ValueError("Cannot translate an empty body")
        return result


class CachedTranslator:
    """Persistent SQLite cache keyed by engine, normalized language, and body."""

    def __init__(self, translator: Translator, path):
        self.translator = translator
        self.engine = translator.engine
        # Export workers use independent connections; wait for short concurrent writes.
        self.connection = sqlite3.connect(path, timeout=60)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS translations (key TEXT PRIMARY KEY, body TEXT NOT NULL)"
        )

    def translate(self, text, source_language):
        source = normalize_language(source_language)
        key = hashlib.sha256(
            (self.engine + "\0" + source + "\0" + text).encode("utf-8")
        ).hexdigest()
        cached = self.connection.execute(
            "SELECT body FROM translations WHERE key = ?", (key,)
        ).fetchone()
        if cached is not None:
            return cached[0]
        result = translate_text(text, language=source, translator=self.translator)
        self.connection.execute(
            "INSERT OR REPLACE INTO translations VALUES (?, ?)", (key, result.text)
        )
        self.connection.commit()
        return result.text

    def close(self):
        self.connection.close()

    def translate_many(self, texts, source_language):
        source = normalize_language(source_language)
        texts = list(texts)
        keys = [
            hashlib.sha256((self.engine + "\0" + source + "\0" + text).encode("utf-8")).hexdigest()
            for text in texts
        ]
        outputs: list[str | None] = [None] * len(texts)
        missing: dict[str, tuple[str, list[int]]] = {}
        for index, (key, text) in enumerate(zip(keys, texts)):
            cached = self.connection.execute(
                "SELECT body FROM translations WHERE key = ?", (key,)
            ).fetchone()
            if cached is not None:
                outputs[index] = cached[0]
            else:
                missing.setdefault(key, (text, []))[1].append(index)
        if missing:
            bodies = [text for text, _ in missing.values()]
            method = getattr(self.translator, "translate_many", None)
            translated = (
                method(bodies, source)
                if callable(method)
                else [self.translator.translate(text, source) for text in bodies]
            )
            if len(translated) != len(bodies) or any(
                not isinstance(text, str) or not text.strip() for text in translated
            ):
                raise ValueError("Translator returned an invalid batch")
            entries = []
            for (key, (_, indexes)), text in zip(missing.items(), translated):
                for index in indexes:
                    outputs[index] = text
                entries.append((key, text))
            self.connection.executemany(
                "INSERT OR REPLACE INTO translations VALUES (?, ?)", entries
            )
            self.connection.commit()
        return outputs
