"""English translation with source-language and engine metadata."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from ..dependencies import require_dependency
from ..types import LanguageCheck
from ..wire import text_component
from .language import LanguageDetection, LanguageDetector, detect_language, verify_language

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
    """Prepared English text and its translation provenance.

    Attributes:
        original_text: Original input body.
        text: English body for downstream analysis.
        source_language: Normalized source-language code.
        engine: Translation engine citation, or `None` for English input.
        language_detection: Detection or verification evidence, when collected.
    """

    original_text: str
    text: str
    source_language: str
    engine: str | None
    language_detection: LanguageDetection | None = None

    @property
    def translated(self) -> bool:
        """Whether the source language required translation into English."""
        return self.source_language != "eng"


class Translator(Protocol):
    """English translation backend exposing `engine` and `translate(text, source_language)`."""

    engine: str

    def translate(self, text: str, source_language: str) -> str: ...


def translate_text(
    text: str,
    *,
    language: str | None = None,
    translator: Translator,
    detect_missing_language: bool = True,
    language_detector: LanguageDetector | None = None,
    language_check: LanguageCheck = "script",
) -> TranslationResult:
    """Prepare English text and record its source language and translation engine.

    English input passes through unchanged.

    Args:
        text: Prepared article body.
        language: Supported language code, name, or regional tag.
        translator: Backend used for non-English input.
        detect_missing_language: Detect the language when its label is missing.
        language_detector: Custom detection backend. Defaults to local Lingua.
        language_check: `none`, `script` for alphabet conflicts, or `all` to check
            every supplied label.

    Returns:
        English text with original text, language, engine, and detection evidence.

    Raises:
        TypeError: If `text` is not a string or detection output is invalid.
        ValueError: If language settings, the engine, or translated text are invalid.
        LanguageDetectionError: If detection fails or a script conflict is unresolved.
        OptionalDependencyError: If a required detection dependency is unavailable.
    """
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


def _validate_translation_options(
    chunk_tokens, batch_size, num_beams, max_new_tokens, min_new_tokens
):
    if type(chunk_tokens) is not int or not 1 <= chunk_tokens <= 512:
        raise ValueError("chunk_tokens must be an integer between 1 and 512")
    for name, value in (
        ("batch_size", batch_size),
        ("num_beams", num_beams),
        ("max_new_tokens", max_new_tokens),
    ):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if type(min_new_tokens) is not int or not 0 <= min_new_tokens <= max_new_tokens:
        raise ValueError("min_new_tokens must be an integer between 0 and max_new_tokens")


class M2M100Translator:
    """Local M2M100 translation with sentence chunking and batched inference.

    Load with `from_model` and reuse one instance for sequential translation calls.
    """

    def __init__(
        self,
        tokenizer,
        model,
        *,
        engine,
        chunk_tokens=384,
        batch_size=4,
        num_beams=4,
        max_new_tokens=768,
        min_new_tokens=1,
    ):
        _validate_translation_options(
            chunk_tokens, batch_size, num_beams, max_new_tokens, min_new_tokens
        )
        self.tokenizer, self.model, self.engine = tokenizer, model, engine
        self.chunk_tokens = chunk_tokens
        self.batch_size, self.num_beams = batch_size, num_beams
        self.max_new_tokens, self.min_new_tokens = max_new_tokens, min_new_tokens

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
        chunk_tokens=384,
        max_new_tokens=768,
        min_new_tokens=1,
    ) -> M2M100Translator:
        """Load a reusable M2M100 model and tokenizer.

        Args:
            model (str): Model identifier or local model directory.
            device (str): PyTorch device, such as `cpu` or `cuda:0`.
            allow_download (bool): Allow model downloads when local files are missing.
            revision (str | None): Optional model revision.
            batch_size (int): Positive number of text chunks per inference batch.
            num_beams (int): Positive beam count for generation.
            chunk_tokens (int): Source tokens per chunk, between 1 and 512.
            max_new_tokens (int): Positive output-token limit per chunk.
            min_new_tokens (int): Minimum output tokens per chunk, between zero
                and `max_new_tokens`.

        Returns:
            A translator with an engine citation identifying its configuration.

        Raises:
            OptionalDependencyError: If a required backend dependency is unavailable.
            TranslationUnavailableError: If model resources cannot be loaded.
            ValueError: If chunk, batch, beam, or output-length settings are invalid.
        """
        _validate_translation_options(
            chunk_tokens, batch_size, num_beams, max_new_tokens, min_new_tokens
        )
        require_dependency("torch", "translate")
        transformers = require_dependency("transformers", "translate")
        require_dependency("sentencepiece", "translate")
        model_class = transformers.M2M100ForConditionalGeneration
        tokenizer_class = transformers.M2M100Tokenizer
        options: dict[str, Any] = {"local_files_only": not allow_download}
        if revision is not None:
            options["revision"] = revision
        try:
            tokenizer = tokenizer_class.from_pretrained(model, **options)
            network = model_class.from_pretrained(model, **options).to(device).eval()
            if str(device).startswith("cuda"):
                network = network.half()
        except OSError as error:
            raise TranslationUnavailableError(
                "M2M100 resources unavailable; download explicitly with allow_download=True or supply a local model directory"
            ) from error
        commit = getattr(network.config, "_commit_hash", None) or revision or "local"
        precision = "fp16" if str(device).startswith("cuda") else "fp32"
        engine = (
            f"M2M100 {model}@{commit}; transformers {transformers.__version__}; "
            f"chunk{chunk_tokens} beam{num_beams} "
            f"new{min_new_tokens}-{max_new_tokens} packed-v2 {precision}"
        )
        return cls(
            tokenizer,
            network,
            engine=engine,
            chunk_tokens=chunk_tokens,
            batch_size=batch_size,
            num_beams=num_beams,
            max_new_tokens=max_new_tokens,
            min_new_tokens=min_new_tokens,
        )

    def translate(self, text: str, source_language: str) -> str:
        """Translate one body into English using the batch translation path.

        Args:
            text: Source body.
            source_language: Supported language code, name, or regional tag.

        Returns:
            The English translation.

        Raises:
            ValueError: If the language, input, or generated output is unsupported.
        """
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
        # M2M100 starts decoding with one token. Express the minimum as a total
        # length to avoid conflicting with the model's inherited min_length.
        generated = self.model.generate(
            **inputs,
            forced_bos_token_id=self.tokenizer.get_lang_id("en"),
            num_beams=1 if retry else self.num_beams,
            max_length=None,
            max_new_tokens=self.max_new_tokens,
            min_length=self.min_new_tokens + 1,
            min_new_tokens=None,
        )
        outputs = []
        for sequence in generated:
            ids = sequence.tolist()
            while ids and ids[-1] == self.tokenizer.pad_token_id:
                ids.pop()
            if not ids or ids[-1] != self.tokenizer.eos_token_id:
                raise ValueError(
                    f"Translation reached its output limit (max_new_tokens={self.max_new_tokens}); "
                    "reduce chunk_tokens or increase max_new_tokens; article not exported as complete"
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

    def translate_many(self, texts: Iterable[str], source_language: str) -> list[str]:
        """Translate same-language bodies in bounded batches of text chunks.

        Args:
            texts: Source bodies sharing one language.
            source_language: Supported language code, name, or regional tag.

        Returns:
            English translations in input order, with translated chunks joined
            by newlines.

        Raises:
            ValueError: If the language is unsupported or a body produces invalid
                or empty output.
            OptionalDependencyError: If PyTorch is unavailable.
        """
        torch = require_dependency("torch", "translate")

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
