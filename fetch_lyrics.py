#!/usr/bin/env python3
import os
import re
import sys
import json
import glob
import argparse
import subprocess
import tempfile
import logging
import unicodedata
from pathlib import Path
import readline
import requests

from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.mp4 import MP4
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, USLT

# Optional multi-provider engine (syncedlyrics)
try:
    import syncedlyrics
    logging.getLogger("syncedlyrics").setLevel(logging.WARNING)
    HAS_SYNCEDLYRICS = True
except ImportError:
    HAS_SYNCEDLYRICS = False

# Optional romanization engines
try:
    import pykakasi
    HAS_KAKASI = True
except ImportError:
    HAS_KAKASI = False

try:
    from pypinyin import pinyin, Style
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

# --- Default configuration (fallback if config.json does not exist) ---
DEFAULT_CONFIG = {
    "aliases": [
        ["tomorrow x together", "txt", "투모로우바이투게더"],
        ["bts", "bangtan", "방탄소년단"],
        ["iu", "이지은"],
        ["snsd", "girls' generation", "소녀시대"],
        ["g-idle", "(g)i-dle", "(여자)아이들", "gidle"],
        ["seventeen", "svt", "세븐틴"],
        ["stray kids", "skz", "스트레이 키즈"]
    ],
    "cleaning": {
        "feature_regex": r"[\(\[][\s]*(?:feat\.?|featuring|ft\.?)\s+[^\)\]]+[\)\]]",
        "trailing_feature_regex": r"\s+(?:feat\.?|featuring|ft\.?)\s+.*$",
        "korean_bracket_regex": r"[\(\[][^\)\]]*[가-힣ㄱ-ㅎㅏ-ㅣ][^\)\]]*[\)\]]",
        "japanese_bracket_regex": r"[\(\[][^\)\]]*[ぁ-ゖァ-ヺ一-龥][^\)\]]*[\)\]]",
        "chinese_bracket_regex": r"[\(\[][^\)\]]*[一-龥][^\)\]]*[\)\]]",
        "ignore_words_artist_match": ["the", "and", "feat", "ft", "with", "&"]
    },
    "api": {
        "lrclib_url": "https://lrclib.net/api",
        "netease_search_url": "https://music.163.com/api/search/get/web",
        "netease_lyric_url": "https://music.163.com/api/song/lyric",
        "timeout_seconds": 6,
        "netease_search_limit": 6,
        "user_agent": "LyricsTagger/2.5"
    },
    "settings": {
        "supported_extensions": [".flac", ".mp3", ".ogg", ".opus", ".m4a"],
        "default_editor": "nano",
        "preview_lines": 16,
        "non_latin_ratio_threshold": 0.25,
        "max_search_depth": 3,
        "max_file_count": 250
    }
}

def load_config() -> dict:
    candidate_paths = [
        Path(__file__).resolve().parent / "config.json",
        Path.home() / ".config" / "fetch-lyrics" / "config.json"
    ]
    for path in candidate_paths:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    config = DEFAULT_CONFIG.copy()
                    config.update(loaded)
                    return config
            except Exception as e:
                print(f"\033[33mWarning: Configuration file '{path}' invalid, using defaults: {e}\033[0m")
    return DEFAULT_CONFIG

CONFIG = load_config()
TIMESTAMP_REGEX = re.compile(r"^(\s*(?:\[\d{2}:\d{2}(?:\.\d+)?\]\s*)+)(.*)$")

# --- UI & ANSI Styling ---
class StyleUI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

def badge(text: str, color: str) -> str:
    return f"{color}{StyleUI.BOLD}[{text}]{StyleUI.RESET}"

def print_banner(text: str):
    print(f"\n{StyleUI.CYAN}{StyleUI.BOLD}{'─' * 60}{StyleUI.RESET}")
    print(f"{StyleUI.CYAN}{StyleUI.BOLD} {text}{StyleUI.RESET}")
    print(f"{StyleUI.CYAN}{StyleUI.BOLD}{'─' * 60}{StyleUI.RESET}")

def safe_input(prompt: str = "", default_text: str = "") -> str:
    try:
        if default_text and hasattr(readline, "set_startup_hook"):
            readline.set_startup_hook(lambda: readline.insert_text(default_text))
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n{StyleUI.YELLOW}Program aborted by user.{StyleUI.RESET}")
        sys.exit(0)
    finally:
        if hasattr(readline, "set_startup_hook"):
            readline.set_startup_hook(None)

def exit_script():
    print(f"\n{StyleUI.YELLOW}Program terminated.{StyleUI.RESET}")
    sys.exit(0)

# --- Cleaning & Metadata ---
def clean_tag(text: str) -> str:
    if not text:
        return ""

    cleaning_cfg = CONFIG.get("cleaning", {})
    feat_pat = cleaning_cfg.get("feature_regex")
    trail_pat = cleaning_cfg.get("trailing_feature_regex")

    cleaned = text
    if feat_pat:
        cleaned = re.sub(feat_pat, "", cleaned, flags=re.IGNORECASE)
    if trail_pat:
        cleaned = re.sub(trail_pat, "", cleaned, flags=re.IGNORECASE)

    language_patterns = [
        cleaning_cfg.get("korean_bracket_regex"),
        cleaning_cfg.get("japanese_bracket_regex"),
        cleaning_cfg.get("chinese_bracket_regex"),
    ]

    for pat in language_patterns:
        if pat:
            cleaned = re.sub(pat, "", cleaned)

    return re.sub(r"\s+", " ", cleaned).strip()

def get_artist_aliases(artist: str) -> list:
    if not artist:
        return []
    art_lower = artist.lower()
    for group in CONFIG.get("aliases", []):
        if any(alias.lower() in art_lower for alias in group):
            return [a for a in group if a.lower() != art_lower]
    return []

def matches_artist(target_artist: str, candidate_artist: str) -> bool:
    if not target_artist or not candidate_artist:
        return True

    t = target_artist.lower()
    c = candidate_artist.lower()

    if t in c or c in t:
        return True

    for group in CONFIG.get("aliases", []):
        g_lower = [a.lower() for a in group]
        if any(a in t for a in g_lower) and any(a in c for a in g_lower):
            return True

    ignore_words = set(CONFIG["cleaning"].get("ignore_words_artist_match", []))
    t_words = set(re.findall(r"\w+", t)) - ignore_words
    c_words = set(re.findall(r"\w+", c)) - ignore_words
    return bool(t_words & c_words)

def is_non_latin(text: str) -> bool:
    if not text:
        return False
    threshold = CONFIG["settings"].get("non_latin_ratio_threshold", 0.25)
    clean_lines = [TIMESTAMP_REGEX.sub(r"\2", line).strip() for line in text.splitlines() if line.strip()]
    letters = [ch for ch in "".join(clean_lines) if ch.isalpha()]
    if not letters:
        return False
    non_latin = sum(1 for ch in letters if "LATIN" not in unicodedata.name(ch, ""))
    return (non_latin / len(letters)) > threshold

def has_timestamps(text: str) -> bool:
    return any(TIMESTAMP_REGEX.match(line) for line in text.splitlines() if line.strip())

def romanize_line(text_segment: str, lang: str) -> str:
    if not text_segment.strip():
        return text_segment

    if lang == "ko":
        if not HAS_KOREAN:
            return text_segment
        return KoRomanizer(text_segment).romanize()

    elif lang == "ja":
        if not HAS_KAKASI:
            return text_segment
        kks = pykakasi.kakasi()
        result = kks.convert(text_segment)
        return " ".join([item["hepburn"] for item in result])

    elif lang == "zh":
        if not HAS_PYPINYIN:
            return text_segment
        tokens = pinyin(text_segment, style=Style.TONE)
        return " ".join([t[0] for t in tokens])

    elif lang == "any":
        if not HAS_ANYASCII:
            return text_segment
        return anyascii.anyascii(text_segment)

    return text_segment

def romanize_lyrics(lyrics: str, lang: str) -> str:
    converted_lines = []
    for line in lyrics.splitlines():
        match = TIMESTAMP_REGEX.match(line)
        if match:
            timestamps = match.group(1)
            content = match.group(2)
            converted_lines.append(f"{timestamps}{romanize_line(content, lang)}")
        else:
            converted_lines.append(romanize_line(line, lang))
    return "\n".join(converted_lines)

def prompt_romanization(lyrics: str) -> str:
    print(f"\n{StyleUI.BOLD}Select romanization language:{StyleUI.RESET}")
    print(f"  [{StyleUI.GREEN}1{StyleUI.RESET}] Korean (Hangul -> Romaja) [{'Available' if HAS_KOREAN else 'Missing: pip install korean-romanizer'}]")
    print(f"  [{StyleUI.GREEN}2{StyleUI.RESET}] Japanese (Kanji/Kana -> Rōmaji) [{'Available' if HAS_KAKASI else 'Missing: pip install pykakasi'}]")
    print(f"  [{StyleUI.GREEN}3{StyleUI.RESET}] Mandarin (Hanzi -> Pīnyīn) [{'Available' if HAS_PYPINYIN else 'Missing: pip install pypinyin'}]")
    print(f"  [{StyleUI.GREEN}4{StyleUI.RESET}] Universal (anyascii) [{'Available' if HAS_ANYASCII else 'Missing: pip install anyascii'}]")
    print(f"  [{StyleUI.YELLOW}c{StyleUI.RESET}] Cancel")

    sel = safe_input(f"{StyleUI.BOLD}Choose language [1-4/c]: {StyleUI.RESET}").strip().lower()
    mapping = {
        "1": ("ko", HAS_KOREAN, "korean-romanizer"),
        "2": ("ja", HAS_KAKASI, "pykakasi"),
        "3": ("zh", HAS_PYPINYIN, "pypinyin"),
        "4": ("any", HAS_ANYASCII, "anyascii")
    }

    if sel not in mapping:
        return lyrics

    lang_code, available, pkg_name = mapping[sel]
    if not available:
        print(f"{StyleUI.RED}Package '{pkg_name}' is not installed.{StyleUI.RESET}")
        return lyrics

    print(f"{StyleUI.CYAN}Converting lyric lines...{StyleUI.RESET}")
    return romanize_lyrics(lyrics, lang_code)

def get_track_metadata(file_path: Path):
    ext = file_path.suffix.lower()
    title, artist, album, duration = "", "", "", 0
    existing_lyrics = ""

    try:
        if ext in (".flac", ".ogg", ".opus"):
            if ext == ".flac":
                audio = FLAC(file_path)
            elif ext == ".ogg":
                audio = OggVorbis(file_path)
            else:
                audio = OggOpus(file_path)

            title = audio.get("title", [""])[0]
            artist = audio.get("artist", [""])[0]
            album = audio.get("album", [""])[0]
            duration = int(audio.info.length) if audio.info else 0
            existing_lyrics = audio.get("LYRICS", [""])[0] or audio.get("UNSYNCEDLYRICS", [""])[0]

        elif ext == ".mp3":
            audio = MP3(file_path, ID3=ID3)
            title = str(audio.get("TIT2", ""))
            artist = str(audio.get("TPE1", ""))
            album = str(audio.get("TALB", ""))
            duration = int(audio.info.length) if audio.info else 0
            if audio.tags:
                for tag in audio.tags.values():
                    if tag.FrameID == "USLT":
                        existing_lyrics = str(tag.text)
                        break

        elif ext == ".m4a":
            audio = MP4(file_path)
            title = audio.get("\xa9nam", [""])[0]
            artist = audio.get("\xa9ART", [""])[0]
            album = audio.get("\xa9alb", [""])[0]
            duration = int(audio.info.length) if audio.info else 0
            existing_lyrics = audio.get("\xa9lyr", [""])[0]

    except Exception:
        pass

    return str(title).strip(), str(artist).strip(), str(album).strip(), duration, str(existing_lyrics).strip()

def open_editor(initial_content: str) -> str:
    fallback_editor = CONFIG["settings"].get("default_editor", "nano")
    editor = os.environ.get("EDITOR", fallback_editor)
    with tempfile.NamedTemporaryFile(suffix=".lrc", mode="w+", encoding="utf-8", delete=False) as tf:
        tf.write(initial_content)
        temp_path = tf.name

    try:
        subprocess.run([editor, temp_path], check=True)
        with open(temp_path, "r", encoding="utf-8") as f:
            return f.read()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def embed_lyrics(file_path: Path, lyrics: str):
    ext = file_path.suffix.lower()
    if ext in (".flac", ".ogg", ".opus"):
        if ext == ".flac":
            audio = FLAC(file_path)
        elif ext == ".ogg":
            audio = OggVorbis(file_path)
        else:
            audio = OggOpus(file_path)
        audio["LYRICS"] = lyrics
        audio.save()

    elif ext == ".mp3":
        audio = MP3(file_path, ID3=ID3)
        try:
            audio.add_tags()
        except Exception:
            pass
        audio.tags.delall("USLT")
        audio.tags.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))
        audio.save()

    elif ext == ".m4a":
        audio = MP4(file_path)
        audio["\xa9lyr"] = [lyrics]
        audio.save()

def delete_lyrics(file_path: Path):
    ext = file_path.suffix.lower()
    if ext in (".flac", ".ogg", ".opus"):
        if ext == ".flac":
            audio = FLAC(file_path)
        elif ext == ".ogg":
            audio = OggVorbis(file_path)
        else:
            audio = OggOpus(file_path)
        changed = False
        for tag in ["LYRICS", "UNSYNCEDLYRICS"]:
            if tag in audio:
                del audio[tag]
                changed = True
        if changed:
            audio.save()

    elif ext == ".mp3":
        audio = MP3(file_path, ID3=ID3)
        if audio.tags:
            audio.tags.delall("USLT")
            audio.save()

    elif ext == ".m4a":
        audio = MP4(file_path)
        if "\xa9lyr" in audio:
            del audio["\xa9lyr"]
            audio.save()

def preview_text(text: str, max_lines: int = None):
    if max_lines is None:
        max_lines = CONFIG["settings"].get("preview_lines", 16)
    lines = text.splitlines()
    print(f"\n{StyleUI.GRAY}┌─── PREVIEW ({min(len(lines), max_lines)}/{len(lines)} lines) ───{StyleUI.RESET}")
    for line in lines[:max_lines]:
        print(f"{StyleUI.GRAY}│{StyleUI.RESET} {line}")
    if len(lines) > max_lines:
        print(f"{StyleUI.GRAY}│ ... ({len(lines) - max_lines} more lines){StyleUI.RESET}")
    print(f"{StyleUI.GRAY}└{'─' * 42}{StyleUI.RESET}")

# --- Provider queries ---
def query_lrclib(title: str, artist: str, album: str):
    clean_a = clean_tag(artist)
    clean_t = clean_tag(title)
    timeout = CONFIG["api"].get("timeout_seconds", 6)
    api_url = CONFIG["api"].get("lrclib_url", "https://lrclib.net/api")
    headers = {"User-Agent": CONFIG["api"].get("user_agent", "LyricsTagger/2.5")}

    queries = []
    if clean_a:
        queries.append({"track_name": clean_t, "artist_name": clean_a})
        queries.append({"q": f"{clean_a} {clean_t}"})
        queries.append({"q": f"{clean_a} {clean_t} Romanized"})
        for alias in get_artist_aliases(clean_a):
            queries.append({"track_name": clean_t, "artist_name": alias})
            queries.append({"q": f"{alias} {clean_t}"})
    else:
        queries.append({"track_name": clean_t})
        queries.append({"q": clean_t})

    seen_ids = set()
    results = []
    errors = []

    for params in queries:
        clean_params = {k: v for k, v in params.items() if v}
        try:
            r = requests.get(f"{api_url}/search", params=clean_params, headers=headers, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            item_id = item.get("id")
                            if item_id and item_id not in seen_ids:
                                seen_ids.add(item_id)
                                results.append(item)
            elif r.status_code in (500, 502, 503, 504):
                errors.append(f"HTTP {r.status_code} ({r.reason or 'Server busy'})")
            elif r.status_code == 429:
                errors.append("HTTP 429 (Rate Limit)")
        except requests.Timeout:
            errors.append("LRCLIB Timeout")
        except requests.RequestException as e:
            errors.append(f"LRCLIB ({type(e).__name__})")

    return results, list(dict.fromkeys(errors))

def query_netease(title: str, artist: str, track_duration: int = 0):
    clean_a = clean_tag(artist)
    clean_t = clean_tag(title)
    timeout = CONFIG["api"].get("timeout_seconds", 6)
    search_url = CONFIG["api"].get("netease_search_url", "https://music.163.com/api/search/get/web")
    lyric_url = CONFIG["api"].get("netease_lyric_url", "https://music.163.com/api/song/lyric")
    limit = CONFIG["api"].get("netease_search_limit", 6)

    search_terms = []
    if clean_a:
        search_terms.append(f"{clean_a} {clean_t}".strip())
        for alias in get_artist_aliases(clean_a):
            search_terms.append(f"{alias} {clean_t}".strip())
    else:
        search_terms.append(clean_t)

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Referer": "https://music.163.com/"
    }

    results = []
    seen_ids = set()

    for term in search_terms:
        if not term:
            continue
        try:
            params = {"s": term, "type": 1, "offset": 0, "limit": limit}
            r = requests.get(search_url, params=params, headers=headers, timeout=timeout)
            if r.status_code != 200:
                continue

            try:
                data = r.json()
            except Exception:
                continue

            if not isinstance(data, dict):
                continue
            result_obj = data.get("result")
            if not isinstance(result_obj, dict):
                continue
            songs = result_obj.get("songs")
            if not isinstance(songs, list):
                continue

            for song in songs:
                if not isinstance(song, dict):
                    continue

                s_id = song.get("id")
                if not s_id or s_id in seen_ids:
                    continue
                seen_ids.add(s_id)

                s_title = song.get("name") or ""
                artists_list = song.get("artists")
                s_artists = ", ".join([a.get("name", "") for a in artists_list if isinstance(a, dict)]) if isinstance(artists_list, list) else ""
                album_obj = song.get("album")
                s_album = album_obj.get("name", "NetEase") if isinstance(album_obj, dict) else "NetEase"

                s_dur_raw = song.get("duration", 0)
                s_dur = int(s_dur_raw / 1000) if isinstance(s_dur_raw, (int, float)) else 0

                l_r = requests.get(lyric_url, params={"id": s_id, "lv": -1, "kv": -1, "tv": -1}, headers=headers, timeout=5)
                if l_r.status_code == 200:
                    try:
                        l_data = l_r.json()
                    except Exception:
                        continue

                    if isinstance(l_data, dict):
                        lrc_dict = l_data.get("lrc")
                        lrc = lrc_dict.get("lyric", "") if isinstance(lrc_dict, dict) else ""
                        if lrc and lrc.strip():
                            diff = abs(s_dur - track_duration) if (track_duration and s_dur) else 0
                            results.append({
                                "provider": "NetEase",
                                "artist": s_artists,
                                "title": s_title,
                                "album": s_album,
                                "synced": has_timestamps(lrc),
                                "latin": not is_non_latin(lrc),
                                "text": lrc.strip(),
                                "diff": diff,
                                "has_dur": bool(s_dur)
                            })
        except requests.RequestException:
            continue

    return results

def query_syncedlyrics_provider(title: str, artist: str):
    if not HAS_SYNCEDLYRICS:
        return []

    clean_a = clean_tag(artist)
    clean_t = clean_tag(title)

    queries = []
    if clean_a:
        queries.append(f"{clean_a} - {clean_t}")
        for alias in get_artist_aliases(clean_a):
            queries.append(f"{alias} - {clean_t}")
    else:
        queries.append(clean_t)

    results = []
    for q in queries:
        try:
            text = syncedlyrics.search(q, allow_plain_format=True)
            if text and text.strip():
                results.append(text.strip())
        except Exception:
            continue
    return list(dict.fromkeys(results))

def collect_candidates(title: str, artist: str, album: str, track_duration: int):
    valid = []
    seen_texts = set()
    clean_a = clean_tag(artist)

    # 1. Query LRCLIB
    lrclib_items, errors = query_lrclib(title, artist, album)
    for item in lrclib_items:
        synced = bool(item.get("syncedLyrics"))
        plain = bool(item.get("plainLyrics"))
        if not (synced or plain):
            continue

        raw_text = (item.get("syncedLyrics") or item.get("plainLyrics")).strip()
        if raw_text in seen_texts:
            continue
        seen_texts.add(raw_text)

        item_dur = item.get("duration")
        item_dur_int = int(item_dur) if item_dur is not None else 0
        dur_diff = abs(item_dur_int - track_duration) if (track_duration and item_dur_int) else 0
        item_artist = item.get("artistName") or ""

        valid.append({
            "provider": "LRCLIB",
            "artist": item_artist,
            "title": item.get("trackName") or title,
            "album": item.get("albumName") or "N/A",
            "synced": synced,
            "latin": not is_non_latin(raw_text),
            "text": raw_text,
            "diff": dur_diff,
            "has_dur": bool(item_dur_int),
            "match_artist": matches_artist(clean_a, item_artist)
        })

    # 2. Query NetEase
    netease_items = query_netease(title, artist, track_duration)
    for item in netease_items:
        if item["text"] in seen_texts:
            continue
        seen_texts.add(item["text"])
        item["match_artist"] = matches_artist(clean_a, item["artist"])
        valid.append(item)

    # 3. Query syncedlyrics
    if HAS_SYNCEDLYRICS:
        sl_texts = query_syncedlyrics_provider(title, artist)
        for sl_text in sl_texts:
            if sl_text in seen_texts:
                continue
            seen_texts.add(sl_text)
            valid.append({
                "provider": "MULTI",
                "artist": clean_a or "Web",
                "title": title,
                "album": "Web/Multi",
                "synced": has_timestamps(sl_text),
                "latin": not is_non_latin(sl_text),
                "text": sl_text,
                "diff": 0,
                "has_dur": False,
                "match_artist": True
            })

    artist_matches = [c for c in valid if c.get("match_artist", True)]
    candidates = artist_matches if artist_matches else valid
    candidates.sort(key=lambda x: (not x["synced"], not x["latin"], x["diff"]))
    return candidates, errors

# --- Menus & Interaction ---
def inspect_and_confirm_lyrics(lyrics: str, source_label: str = "Selection") -> str:
    current = lyrics
    show_preview = True

    while True:
        non_lat = is_non_latin(current)
        synced = has_timestamps(current)

        b_mode = badge("SYNC", StyleUI.GREEN) if synced else badge("PLAIN", StyleUI.YELLOW)
        b_script = badge("LATIN", StyleUI.CYAN) if not non_lat else badge("ORIGINAL", StyleUI.MAGENTA)

        print(f"\n{StyleUI.BOLD}Status [{source_label}]:{StyleUI.RESET} {b_mode} {b_script}")
        if show_preview:
            preview_text(current)
        else:
            show_preview = True

        print(f"  [{StyleUI.GREEN}e{StyleUI.RESET}] Editor       [{StyleUI.GREEN}r{StyleUI.RESET}] Romanize      [{StyleUI.GREEN}v{StyleUI.RESET}] Full Preview")
        print(f"  [{StyleUI.CYAN}y{StyleUI.RESET}] Apply        [{StyleUI.YELLOW}b{StyleUI.RESET}] Back          [{StyleUI.RED}q{StyleUI.RESET}] Quit")

        action = safe_input(f"{StyleUI.BOLD}Action: {StyleUI.RESET}").strip().lower()

        if action == "q":
            exit_script()
        elif action == "v":
            preview_text(current, max_lines=len(current.splitlines()))
            show_preview = False
        elif action == "e":
            current = open_editor(current)
            print(f"{StyleUI.GREEN}Changes applied.{StyleUI.RESET}")
        elif action == "r":
            current = prompt_romanization(current)
        elif action == "y":
            return current
        elif action == "b":
            return ""

def manage_existing_lyrics(file_path: Path, lyrics: str) -> str:
    current_lyrics = lyrics
    show_preview = True

    while True:
        synced = has_timestamps(current_lyrics)
        non_lat = is_non_latin(current_lyrics)

        b_mode = badge("SYNC", StyleUI.GREEN) if synced else badge("PLAIN", StyleUI.YELLOW)
        b_script = badge("LATIN", StyleUI.CYAN) if not non_lat else badge("ORIGINAL", StyleUI.MAGENTA)

        print(f"\n{StyleUI.BOLD}Embedded lyrics found:{StyleUI.RESET} {b_mode} {b_script}")
        if show_preview:
            preview_text(current_lyrics)
        else:
            show_preview = True

        print(f"{StyleUI.BOLD}Options:{StyleUI.RESET}")
        print(f"  [{StyleUI.GREEN}e{StyleUI.RESET}] Open in editor      [{StyleUI.GREEN}r{StyleUI.RESET}] Romanize        [{StyleUI.GREEN}v{StyleUI.RESET}] Full Preview")
        print(f"  [{StyleUI.RED}d{StyleUI.RESET}] Delete from file    [{StyleUI.CYAN}o{StyleUI.RESET}] Search online   [{StyleUI.YELLOW}s{StyleUI.RESET}] Keep & Next")
        print(f"  [{StyleUI.RED}q{StyleUI.RESET}] Quit program")

        action = safe_input(f"{StyleUI.BOLD}Action: {StyleUI.RESET}").strip().lower()

        if action == "q":
            exit_script()
        elif action == "v":
            preview_text(current_lyrics, max_lines=len(current_lyrics.splitlines()))
            show_preview = False
        elif action == "e":
            current_lyrics = open_editor(current_lyrics)
            if safe_input("Save changes? [y/N]: ").strip().lower() == "y":
                embed_lyrics(file_path, current_lyrics)
                print(f"{StyleUI.GREEN}File updated.{StyleUI.RESET}")
        elif action == "r":
            current_lyrics = prompt_romanization(current_lyrics)
            if safe_input("Save romanized lyrics? [y/N]: ").strip().lower() == "y":
                embed_lyrics(file_path, current_lyrics)
                print(f"{StyleUI.GREEN}File updated.{StyleUI.RESET}")
        elif action == "d":
            if safe_input(f"{StyleUI.RED}Delete lyrics from file? [y/N]: {StyleUI.RESET}").strip().lower() == "y":
                delete_lyrics(file_path)
                print(f"{StyleUI.YELLOW}Lyrics removed.{StyleUI.RESET}")
                sub = safe_input("Search online for new lyrics now? [y/N]: ").strip().lower()
                return "search_online" if sub == "y" else "done"
        elif action == "o":
            return "search_online"
        elif action == "s":
            return "done"

def handle_lyrics_selection(initial_title: str, initial_artist: str, initial_album: str, duration: int):
    current_title = initial_title
    current_artist = initial_artist
    current_album = initial_album

    last_query = f"{initial_artist} - {initial_title}" if initial_artist else initial_title
    valid = []
    errors = []
    need_search = True

    while True:
        if need_search:
            status_msg = "Searching lyrics (LRCLIB + NetEase)..."
            print(f"{StyleUI.GRAY}{status_msg}{StyleUI.RESET}", end="\r")
            valid, errors = collect_candidates(current_title, current_artist, current_album, duration)
            print(" " * len(status_msg), end="\r")
            need_search = False

        if errors:
            print(f"{StyleUI.RED}{StyleUI.BOLD}⚠️  LRCLIB notice:{StyleUI.RESET}")
            for err in errors:
                print(f"  {StyleUI.RED}• {err}{StyleUI.RESET}")

        if not valid:
            print(f"{StyleUI.YELLOW}No matching results found for this artist.{StyleUI.RESET}")
        else:
            print(f"{StyleUI.BOLD}Found lyrics ({len(valid)}):{StyleUI.RESET}")
            for idx, cand in enumerate(valid, 1):
                b_sync = badge("SYNC", StyleUI.GREEN) if cand["synced"] else badge("PLAIN", StyleUI.YELLOW)
                b_lang = badge("LATIN", StyleUI.CYAN) if cand["latin"] else badge("ORIG ", StyleUI.MAGENTA)

                src_col = StyleUI.BLUE if cand["provider"] == "LRCLIB" else StyleUI.MAGENTA
                b_src = badge(cand["provider"], src_col)

                dur = f"±{cand['diff']}s" if cand["has_dur"] and cand["diff"] else ("Duration OK" if cand["has_dur"] else "N/A")

                artist_str = f"{cand['artist']} - " if cand.get("artist") else ""
                full_title = f"{artist_str}{cand['title']}"
                a_name = cand["album"]
                print(f"  [{StyleUI.GREEN}{idx}{StyleUI.RESET}] {b_src} {b_sync} {b_lang} {StyleUI.GRAY}{dur:<9}{StyleUI.RESET} {full_title} {StyleUI.GRAY}({a_name}){StyleUI.RESET}")

        print(f"\n{StyleUI.BOLD}Options:{StyleUI.RESET}")
        print(f"  [{StyleUI.GREEN}1-{len(valid) if valid else 1}{StyleUI.RESET}] Select       [{StyleUI.CYAN}m{StyleUI.RESET}] Adjust search   [{StyleUI.CYAN}n{StyleUI.RESET}] Enter manually (Editor)")
        print(f"  [{StyleUI.YELLOW}s{StyleUI.RESET}] Skip         [{StyleUI.RED}q{StyleUI.RESET}] Quit")

        choice = safe_input(f"{StyleUI.BOLD}Selection: {StyleUI.RESET}").strip().lower()

        if choice == "q":
            exit_script()
        elif choice == "s":
            return None

        elif choice == "m":
            q = safe_input("New search query (title or 'Artist - Title'): ", default_text=last_query).strip()
            if q:
                last_query = q
                if " - " in q:
                    parts = q.split(" - ", 1)
                    current_artist = parts[0].strip()
                    current_title = parts[1].strip()
                else:
                    current_title = q
                    current_artist = ""
                current_album = ""
                need_search = True
            continue

        elif choice == "n":
            print(f"{StyleUI.CYAN}Opening editor for manual input...{StyleUI.RESET}")
            user_text = open_editor("")
            if not user_text.strip():
                print(f"{StyleUI.YELLOW}No text entered.{StyleUI.RESET}")
                continue
            final_text = inspect_and_confirm_lyrics(user_text, source_label="Manual")
            if final_text:
                return final_text
            continue

        elif choice.isdigit() and 1 <= int(choice) <= len(valid):
            selected = valid[int(choice) - 1]
            final_text = inspect_and_confirm_lyrics(selected["text"], source_label=f"Entry #{choice}")
            if final_text:
                return final_text
            continue

# --- File search with depth and quantity safeguards ---
def complete_path(text, state):
    expanded = os.path.expanduser(text)
    matches = glob.glob(expanded + "*")
    results = [m + ("/" if os.path.isdir(m) else " ") for m in matches]
    return results[state] if state < len(results) else None

def find_music_files(base_dir: Path):
    supported = set(ext.lower() for ext in CONFIG["settings"].get("supported_extensions", [".flac", ".mp3", ".ogg", ".opus", ".m4a"]))
    max_depth = CONFIG["settings"].get("max_search_depth", 3)
    max_files = CONFIG["settings"].get("max_file_count", 250)

    found_files = []
    base_parts_len = len(base_dir.resolve().parts)

    for root, dirs, files in os.walk(base_dir, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        root_path = Path(root)
        rel_depth = len(root_path.resolve().parts) - base_parts_len

        if rel_depth >= max_depth:
            dirs[:] = []

        for f in files:
            if not f.startswith(".") and Path(f).suffix.lower() in supported:
                found_files.append(root_path / f)
                if len(found_files) > max_files:
                    return None, "TOO_MANY_FILES"

    return sorted(found_files), None

def resolve_music_directory(initial_path: Path):
    current = initial_path
    max_depth = CONFIG["settings"].get("max_search_depth", 3)
    max_files = CONFIG["settings"].get("max_file_count", 250)

    while True:
        resolved = current.resolve()

        if resolved in (Path.home(), Path("/")):
            print(f"\n{StyleUI.YELLOW}Execution in root or home directory ('{resolved}') detected.{StyleUI.RESET}")
            print(f"{StyleUI.YELLOW}To prevent unintended large-scale scans, please select a specific music folder.{StyleUI.RESET}")
        elif resolved.exists() and resolved.is_dir():
            files, err = find_music_files(resolved)

            if err == "TOO_MANY_FILES":
                print(f"\n{StyleUI.YELLOW}⚠️  Found more than {max_files} music files in '{resolved}'.{StyleUI.RESET}")
                print(f"{StyleUI.YELLOW}Search scope is too broad. Please specify an artist or album directory.{StyleUI.RESET}")
            elif files:
                return resolved, files
            else:
                print(f"\n{StyleUI.YELLOW}No supported music files found in '{resolved}' (max depth: {max_depth} levels).{StyleUI.RESET}")
        elif not resolved.exists():
            print(f"\n{StyleUI.RED}Path does not exist: {resolved}{StyleUI.RESET}")
        else:
            print(f"\n{StyleUI.RED}Path is not a directory: {resolved}{StyleUI.RESET}")

        readline.set_completer_delims(" \t\n;")
        readline.parse_and_bind("tab: complete")
        readline.set_completer(complete_path)

        user_input = safe_input(f"{StyleUI.BOLD}Enter music directory path (or 'q' to quit): {StyleUI.RESET}").strip()
        readline.set_completer(None)

        clean_input = user_input.strip("'\" ")
        if not clean_input or clean_input.lower() == "q":
            exit_script()

        current = Path(clean_input).expanduser()

def process_directory(target_dir: Path):
    target_dir, files = resolve_music_directory(target_dir)

    print(f"\n{StyleUI.BOLD}{len(files)} audio file(s) found in '{target_dir}'.{StyleUI.RESET}")

    for idx, file_path in enumerate(files, 1):
        title, artist, album, duration, existing_lyrics = get_track_metadata(file_path)

        print_banner(f"[{idx}/{len(files)}] {file_path.name}")

        if not title or not artist:
            print(f"{StyleUI.YELLOW}Incomplete tags: Title or artist missing. Skipped.{StyleUI.RESET}")
            continue

        dur_str = f"{duration // 60}:{duration % 60:02d} min" if duration else "N/A"
        print(f"{StyleUI.BOLD}Track:{StyleUI.RESET}  {artist} - {title}")
        print(f"{StyleUI.BOLD}Album:{StyleUI.RESET}  {album or 'N/A'} | {dur_str}")

        if existing_lyrics:
            result = manage_existing_lyrics(file_path, existing_lyrics)
            if result == "done":
                continue

        chosen_lyrics = handle_lyrics_selection(title, artist, album, duration)
        if chosen_lyrics:
            embed_lyrics(file_path, chosen_lyrics)
            print(f"{StyleUI.GREEN}{StyleUI.BOLD}✓ Lyrics successfully embedded into file.{StyleUI.RESET}")
        else:
            print(f"{StyleUI.YELLOW}Skipped.{StyleUI.RESET}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage and embed synchronized & plain lyrics in MP3, FLAC, OGG, OPUS, and M4A.")
    parser.add_argument("path", nargs="?", default=".", help="Path to music directory (default: current directory)")
    args = parser.parse_args()

    target = Path(args.path).expanduser()

    try:
        process_directory(target)
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n{StyleUI.YELLOW}Program aborted by user.{StyleUI.RESET}")
        sys.exit(0)
