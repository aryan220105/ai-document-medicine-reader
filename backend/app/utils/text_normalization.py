from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


WHITESPACE_RE = re.compile(r"\s+")

# Script ranges we support. Field labels on Indian forms mix Latin with one Indic or
# Arabic script, so a token regex limited to [a-z0-9] silently discards every Devanagari,
# Kannada, and Urdu label.
LATIN = r"a-z0-9"
DEVANAGARI = r"ऀ-ॿ"
KANNADA = r"ಀ-೿"
ARABIC = r"؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿"

TOKEN_RE = re.compile(rf"[{LATIN}{DEVANAGARI}{KANNADA}{ARABIC}]+")

DEVANAGARI_RE = re.compile(rf"[{DEVANAGARI}]")
KANNADA_RE = re.compile(rf"[{KANNADA}]")
ARABIC_RE = re.compile(rf"[{ARABIC}]")
LATIN_RE = re.compile(r"[A-Za-z]")

# Combining marks that carry no lexical weight for matching. Dropping them makes alias
# lookup tolerant of the vowel signs Tesseract most often loses on a noisy scan.
DEVANAGARI_MARKS = re.compile(r"[ऺ-ॏ॑-ॗॢॣऀ-ः]")
KANNADA_MARKS = re.compile(r"[ಾ-್ೕೖಂಃ]")
# Harakat, tatweel, and the Quranic marks Urdu forms never need.
ARABIC_MARKS = re.compile(r"[ً-ٰٟۖ-ۭـ‌‍]")

# Urdu and Arabic encode the same letter several ways depending on the keyboard used.
ARABIC_FOLD = {
    "آ": "ا",  # alef with madda
    "أ": "ا",  # alef with hamza above
    "إ": "ا",  # alef with hamza below
    "ٱ": "ا",  # alef wasla
    "ى": "ی",  # alef maksura -> farsi yeh
    "ي": "ی",  # arabic yeh -> farsi yeh
    "ے": "ی",  # yeh barree -> farsi yeh
    "ۓ": "ی",
    "ك": "ک",  # arabic kaf -> keheh
    "ة": "ہ",  # teh marbuta -> heh goal
    "ه": "ہ",  # heh -> heh goal
    "ۃ": "ہ",
    "ؤ": "و",  # waw with hamza
}

ZERO_WIDTH = re.compile(r"[​‎‏‪-‮⁠﻿]")

SCRIPT_LANGUAGE = {
    "devanagari": "hi",
    "kannada": "kn",
    "arabic": "ur",
    "latin": "en",
}

RTL_SCRIPTS = {"arabic"}


def normalize_text(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text or "")
    cleaned = ZERO_WIDTH.sub("", cleaned)
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def fold(text: str) -> str:
    return normalize_text(text).lower()


def fold_for_match(text: str) -> str:
    """Aggressive fold used only for alias lookup: case, combining marks, Arabic letter
    variants, and punctuation all removed so one alias list serves clean and noisy OCR."""
    cleaned = fold(text)
    cleaned = "".join(ARABIC_FOLD.get(char, char) for char in cleaned)
    cleaned = DEVANAGARI_MARKS.sub("", cleaned)
    cleaned = KANNADA_MARKS.sub("", cleaned)
    cleaned = ARABIC_MARKS.sub("", cleaned)
    cleaned = "".join(
        char for char in unicodedata.normalize("NFD", cleaned) if unicodedata.category(char) != "Mn" or ARABIC_RE.match(char)
    )
    return WHITESPACE_RE.sub(" ", " ".join(TOKEN_RE.findall(cleaned))).strip()


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(fold(text))


def match_tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(fold_for_match(text))


def script_counts(text: str) -> dict[str, int]:
    cleaned = normalize_text(text)
    return {
        "devanagari": len(DEVANAGARI_RE.findall(cleaned)),
        "kannada": len(KANNADA_RE.findall(cleaned)),
        "arabic": len(ARABIC_RE.findall(cleaned)),
        "latin": len(LATIN_RE.findall(cleaned)),
    }


def dominant_script(text: str) -> str:
    """The script with the most letters. Latin only wins when no Indic or Arabic letters
    are present at all, because form headings are often bilingual with English subtitles
    while the field labels themselves are in the regional script."""
    counts = script_counts(text)
    non_latin = {name: count for name, count in counts.items() if name != "latin" and count > 0}
    if non_latin:
        return max(non_latin.items(), key=lambda item: item[1])[0]
    return "latin" if counts["latin"] else "unknown"


def present_scripts(text: str, min_letters: int = 3) -> list[str]:
    counts = script_counts(text)
    return [name for name, count in sorted(counts.items(), key=lambda item: -item[1]) if count >= min_letters]


def is_rtl(text: str) -> bool:
    return dominant_script(text) in RTL_SCRIPTS


def language_for_script(script: str) -> str:
    return SCRIPT_LANGUAGE.get(script, "en")


def similarity(left: str, right: str) -> float:
    """Character similarity on match-folded text. Used to absorb the single-character
    substitutions Tesseract makes on noisy scans ('Nane' for 'Name')."""
    a = fold_for_match(left).replace(" ", "")
    b = fold_for_match(right).replace(" ", "")
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def token_overlap(left: str, right: str) -> float:
    a = set(match_tokens(left))
    b = set(match_tokens(right))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def fuzzy_sequence_match(
    haystack_tokens: list[str],
    needle_tokens: list[str],
    min_token: float = 0.72,
    min_mean: float = 0.80,
) -> float:
    """Best per-token similarity of `needle_tokens` against any window of the same length
    in `haystack_tokens`, or 0.0 when no window is close enough.

    Comparing whole strings is too blunt for noisy OCR: 'Ful Nane' against 'full name'
    scores below any usable threshold, because two small substitutions in a short string
    are a large fraction of it. Aligning token by token recovers that, while the per-token
    floor keeps genuinely different words apart -- 'mother' and 'father' differ too much
    in their opening characters to pass it even though they share a suffix.
    """
    if not needle_tokens or len(needle_tokens) > len(haystack_tokens):
        return 0.0
    best = 0.0
    span = len(needle_tokens)
    for start in range(len(haystack_tokens) - span + 1):
        window = haystack_tokens[start : start + span]
        ratios: list[float] = []
        for left, right in zip(window, needle_tokens):
            # A one- or two-letter particle is a different word from anything merely
            # nearby: Urdu "کا" was scoring as "کام" and every "… کا نام" line became
            # an occupation. A dropped character in a longer word is still allowed.
            if min(len(left), len(right)) <= 2 and left != right:
                ratios = []
                break
            if abs(len(left) - len(right)) > 1:
                ratios = []
                break
            ratios.append(1.0 if left == right else SequenceMatcher(None, left, right).ratio())
        if not ratios or min(ratios) < min_token:
            continue
        mean = sum(ratios) / len(ratios)
        if mean >= min_mean:
            best = max(best, mean)
    return best


def contains_token_sequence(haystack: str, needle: str) -> bool:
    """True when every token of `needle` appears in `haystack` in order. Avoids the false
    positives bare substring matching produces across script boundaries."""
    hay = match_tokens(haystack)
    need = match_tokens(needle)
    if not need or len(need) > len(hay):
        return False
    for start in range(len(hay) - len(need) + 1):
        if hay[start : start + len(need)] == need:
            return True
    return False
