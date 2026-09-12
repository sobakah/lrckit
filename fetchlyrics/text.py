"""Tag cleaning, artist matching, script detection and romanization."""

from __future__ import annotations

import re
from functools import lru_cache

from . import config

# Accepts [m:ss], [mm:ss.xx], [mmm:ss:xx] and repeated timestamps on one line.
TIMESTAMP_REGEX = re.compile(r"^(\s*(?:\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]\s*)+)(.*)$")

# Metadata lines such as [ar:...] / [ti:...] / [length:...] are not timestamps.
_LRC_META_REGEX = re.compile(r"^\s*\[[a-z]{2,}:[^\]]*\]\s*$", re.IGNORECASE)

# --- optional romanization backends ------------------------------------------
try:
    import pykakasi

    HAS_KAKASI = True
except ImportError:
    HAS_KAKASI = False

try:
    from pypinyin import Style, pinyin

    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

try:
    from korean_romanizer.romanizer import Romanizer as KoRomanizer

    HAS_KOREAN = True
except ImportError:
    HAS_KOREAN = False

try:
    import anyascii

    HAS_ANYASCII = True
except ImportError:
    HAS_ANYASCII = False


@lru_cache(maxsize=1)
def _kakasi_instance():
    """pykakasi converters are expensive to build - create exactly one."""
    return pykakasi.kakasi()


# --- cleaning ----------------------------------------------------------------
@lru_cache(maxsize=512)
def _compiled(pattern: str, ignore_case: bool):
    return re.compile(pattern, re.IGNORECASE if ignore_case else 0)


def clean_tag(text: str) -> str:
    if not text:
        return ""

    cleaned = text
    for key in ("feature_regex", "trailing_feature_regex"):
        pattern = config.get("cleaning", key)
        if pattern:
            try:
                cleaned = _compiled(pattern, True).sub("", cleaned)
            except re.error:
                pass

    for key in ("korean_bracket_regex", "japanese_bracket_regex", "chinese_bracket_regex"):
        pattern = config.get("cleaning", key)
        if pattern:
            try:
                cleaned = _compiled(pattern, False).sub("", cleaned)
            except re.error:
                pass

    return re.sub(r"\s+", " ", cleaned).strip()


# --- artist matching ---------------------------------------------------------
@lru_cache(maxsize=2048)
def _word_pattern(needle: str) -> re.Pattern:
    """Match *needle* only at word boundaries, tolerating punctuation inside it."""
    return re.compile(rf"(?<!\w){re.escape(needle)}(?!\w)", re.IGNORECASE)


def _contains_alias(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return bool(_word_pattern(needle.lower()).search(haystack.lower()))


def _alias_groups() -> list[list[str]]:
    groups = config.CONFIG.get("aliases", [])
    return [g for g in groups if isinstance(g, list)] if isinstance(groups, list) else []


def get_artist_aliases(artist: str) -> list[str]:
    """Return alternative spellings for *artist* (word-boundary matched)."""
    if not artist:
        return []
    artist_lower = artist.lower()
    for group in _alias_groups():
        if any(_contains_alias(artist_lower, alias) for alias in group):
            return [a for a in group if a.lower() != artist_lower]
    return []


def matches_artist(target_artist: str, candidate_artist: str) -> bool:
    if not target_artist or not candidate_artist:
        return True

    target = target_artist.lower()
    candidate = candidate_artist.lower()

    if _contains_alias(target, candidate) or _contains_alias(candidate, target):
        return True

    for group in _alias_groups():
        in_target = any(_contains_alias(target, alias) for alias in group)
        in_candidate = any(_contains_alias(candidate, alias) for alias in group)
        if in_target and in_candidate:
            return True

    ignore_words = {w.lower() for w in (config.get("cleaning", "ignore_words_artist_match") or [])}
    target_words = {w for w in re.findall(r"\w+", target) if w not in ignore_words and len(w) > 1}
    candidate_words = {w for w in re.findall(r"\w+", candidate) if w not in ignore_words and len(w) > 1}
    if not target_words or not candidate_words:
        return False

    overlap = target_words & candidate_words
    if not overlap:
        return False
    # Require a clear majority of the shorter name, not a single stray token:
    # "Red Velvet" must not match "The Velvet Underground".
    return len(overlap) / min(len(target_words), len(candidate_words)) > 0.5


# --- script detection --------------------------------------------------------
_LATIN_RANGES = (
    (0x0041, 0x005A),  # Basic Latin uppercase
    (0x0061, 0x007A),  # Basic Latin lowercase
    (0x00C0, 0x024F),  # Latin-1 Supplement / Extended-A / Extended-B
    (0x1E00, 0x1EFF),  # Latin Extended Additional
    (0x2C60, 0x2C7F),  # Latin Extended-C
    (0xA720, 0xA7FF),  # Latin Extended-D
    (0xAB30, 0xAB6F),  # Latin Extended-E
)


def _is_latin_char(char: str) -> bool:
    code = ord(char)
    for low, high in _LATIN_RANGES:
        if low <= code <= high:
            return True
        if code < low:
            return False
    return False


def strip_timestamps(text: str) -> str:
    lines = []
    for line in text.splitlines():
        match = TIMESTAMP_REGEX.match(line)
        lines.append(match.group(2) if match else line)
    return "\n".join(lines)


@lru_cache(maxsize=256)
def _non_latin_ratio(text: str) -> float:
    letters = [c for c in strip_timestamps(text) if c.isalpha()]
    if not letters:
        return 0.0
    non_latin = sum(1 for c in letters if not _is_latin_char(c))
    return non_latin / len(letters)


def is_non_latin(text: str) -> bool:
    if not text:
        return False
    threshold = float(config.get("settings", "non_latin_ratio_threshold", 0.25))
    return _non_latin_ratio(text) > threshold


@lru_cache(maxsize=256)
def has_timestamps(text: str) -> bool:
    for line in text.splitlines():
        if not line.strip() or _LRC_META_REGEX.match(line):
            continue
        if TIMESTAMP_REGEX.match(line):
            return True
    return False


# --- romanization ------------------------------------------------------------
ROMANIZERS = {
    "ko": ("Korean (Hangul → Romaja)", lambda: HAS_KOREAN, "korean-romanizer"),
    "ja": ("Japanese (Kanji/Kana → Rōmaji)", lambda: HAS_KAKASI, "pykakasi"),
    "zh": ("Mandarin (Hanzi → Pīnyīn)", lambda: HAS_PYPINYIN, "pypinyin"),
    "any": ("Universal (anyascii)", lambda: HAS_ANYASCII, "anyascii"),
}


def romanize_segment(segment: str, lang: str) -> str:
    if not segment.strip():
        return segment
    try:
        if lang == "ko" and HAS_KOREAN:
            return KoRomanizer(segment).romanize()
        if lang == "ja" and HAS_KAKASI:
            return " ".join(item["hepburn"] for item in _kakasi_instance().convert(segment))
        if lang == "zh" and HAS_PYPINYIN:
            return " ".join(token[0] for token in pinyin(segment, style=Style.TONE))
        if lang == "any" and HAS_ANYASCII:
            return anyascii.anyascii(segment)
    except Exception:
        return segment
    return segment


def romanize_lyrics(lyrics: str, lang: str) -> str:
    converted = []
    for line in lyrics.splitlines():
        match = TIMESTAMP_REGEX.match(line)
        if match:
            converted.append(f"{match.group(1)}{romanize_segment(match.group(2), lang)}")
        else:
            converted.append(romanize_segment(line, lang))
    return "\n".join(converted)


def detect_script(text: str) -> str | None:
    """Best guess at the dominant non-Latin script, for romanization defaults."""
    stripped = strip_timestamps(text)
    counts = {"ko": 0, "ja": 0, "zh": 0}
    for char in stripped:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF:
            counts["ko"] += 1
        elif 0x3040 <= code <= 0x30FF:
            counts["ja"] += 1
        elif 0x4E00 <= code <= 0x9FFF:
            counts["zh"] += 1
    best = max(counts, key=lambda k: counts[k])
    if counts[best] == 0:
        return "any" if is_non_latin(text) else None
    # Kana present alongside Han characters means Japanese, not Chinese.
    if counts["ja"] > 0 and best == "zh":
        return "ja"
    return best
