# fetch-lyrics

An interactive CLI utility for Linux and Windows to search, inspect, romanize, and embed synchronized (`.lrc`) and regular lyrics into FLAC, MP3, OGG Vorbis, Opus, and M4A audio files.

> **Note:** This script was developed with the assistance of Google Gemini.

---

## Features

* **Multi-Format Tagging:** Native embedding for FLAC (`.flac`), MP3 (`.mp3`), OGG Vorbis (`.ogg`), Opus (`.opus`), and MP4/M4A (`.m4a`).
* **Multi-Provider Search:** Concurrent querying against **LRCLIB** and **NetEase Cloud Music** (native), with optional fallback support via **`syncedlyrics`** (Megalobiz, Deezer, etc.).
* **Search Result Caching:** Search candidates remain cached in memory when returning (`[b]`) from preview or editor menus, eliminating redundant API roundtrips.
* **Smart Tag Cleaning & Aliases:**
  * Strips features (`feat. ...`, `[ft. ...]`).
  * Filters out localized bracketed subtitles (Korean Hangul, Japanese Kanji/Kana, Chinese Hanzi) for cleaner search queries.
  * Resolves artist acronyms and group aliases (e.g., *Tomorrow X Together* ↔ *TXT*).
* **Built-in Romanization:** Identifies non-Latin scripts and transliterates line by line while preserving LRC timestamps:
  * **Korean:** Hangul → Romaja (`korean-romanizer`)
  * **Japanese:** Kanji/Kana → Rōmaji / Hepburn (`pykakasi`)
  * **Mandarin:** Hanzi → Pīnyīn (`pypinyin`)
  * **Universal:** Cyrillic, Greek, Arabic, Thai, etc. → Latin (`anyascii`)
* **Terminal Workflow & Safeguards:**
  * Auto-displays instant preview upon selecting candidates or existing tags.
  * Full-text preview toggle (`[v]`) to verify lyrics to the end of the song without opening an external editor.
  * Search editing (`[m]`) pre-fills the current artist/title query into the prompt for quick edits.
  * Recursion depth (`max_search_depth`) and file count caps (`max_file_count`) protect against runaway directory scans.
  * Interactive path prompt with Tab completion if executed in empty folders or base directories (`~`, `/`).
* **External Configuration:** Centralized `config.json` for aliases, regex patterns, network timeouts, and UI preferences without modifying code.

---

## Requirements & Installation

Python **3.10+** is required.

### 1. Install Base Packages

#### Ubuntu / Debian
```bash
sudo apt update
sudo apt install python3-mutagen python3-requests python3-pip
```

#### RPM-based Distributions (Fedora, RHEL, Bazzite)
```bash
sudo dnf install python3-mutagen python3-requests python3-pip
```

#### Windows
1. Install Python from the Microsoft Store or [python.org](https://www.python.org/downloads/) (enable **"Add python.exe to PATH"**).
2. Install dependencies via PowerShell or Command Prompt:
   ```powershell
   pip install mutagen requests
   ```

---

### 2. Optional Extensions (Romanization & Multi-Provider)

All romanization modules and secondary scraping providers are modular. If a package is missing, the tool functions normally and alerts you only when invoking that specific feature:

```bash
pip install --user pykakasi pypinyin korean-romanizer anyascii syncedlyrics
```

> **Note for modern Linux environments:** If your package manager restricts global installs via PEP 668 (*externally-managed-environment*), run inside a virtual environment (`python3 -m venv venv && source venv/bin/activate`) or append `--break-system-packages` to the pip command.

| Package | Functionality |
|---|---|
| `syncedlyrics` | Multi-provider scraping engine (Megalobiz, Deezer, etc.) |
| `korean-romanizer` | Transliterates Hangul into Revised Romanization of Korean |
| `pykakasi` | Transliterates Kanji and Kana into Hepburn Rōmaji |
| `pypinyin` | Transliterates Chinese Hanzi into Pīnyīn (with tone marks) |
| `anyascii` | Transliterates any non-Latin Unicode script into ASCII |

---

## Configuration (`config.json`)

The script checks for `config.json` in the script directory or `~/.config/fetch-lyrics/config.json`. If missing, built-in defaults are used.

```json
{
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
    "feature_regex": "[\\[\\(][\\s]*(?:feat\\.?|featuring|ft\\.?)\\s+[^\\)\\]]+[\\)\\]]",
    "trailing_feature_regex": "\\s+(?:feat\\.?|featuring|ft\\.?)\\s+.*$",
    "korean_bracket_regex": "[\\[\\(][^\\)\\]]*[가-힣ㄱ-ㅎㅏ-ㅣ][^\\)\\]]*[\\]\\)]",
    "japanese_bracket_regex": "[\\[\\(][^\\)\\]]*[ぁ-ゖァ-ヺ一-龥][^\\)\\]]*[\\]\\)]",
    "chinese_bracket_regex": "[\\[\\(][^\\)\\]]*[一-龥][^\\)\\]]*[\\]\\)]",
    "ignore_words_artist_match": ["the", "and", "feat", "ft", "with", "&"]
  },
  "api": {
    "lrclib_url": "[https://lrclib.net/api](https://lrclib.net/api)",
    "netease_search_url": "[https://music.163.com/api/search/get/web](https://music.163.com/api/search/get/web)",
    "netease_lyric_url": "[https://music.163.com/api/song/lyric](https://music.163.com/api/song/lyric)",
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
```

---

## Setup & Editor Configuration

Clone the repository:
```bash
git clone [https://github.com/](https://github.com/)<username>/fetch-lyrics.git
cd fetch-lyrics
chmod +x fetch_lyrics.py
```

The script opens your configured text editor when manually modifying or inspecting lyrics:

* **Linux:** Uses `$EDITOR` (defaults to `nano` if unset):
  ```bash
  export EDITOR=nvim  # or: export EDITOR=nano
  ```
* **Windows (PowerShell):**
  ```powershell
  $env:EDITOR = "notepad"
  # or: $env:EDITOR = "code --wait"
  ```

---

## Usage

Run without arguments to inspect the current working directory, or pass a target path:

```bash
# Process current directory (prompts interactively if empty or broad)
./fetch_lyrics.py

# Process specific artist or album folder
./fetch_lyrics.py ~/Music/Artist/Album
```

On Windows:
```powershell
python fetch_lyrics.py "D:\Music\K-Pop\Album"
```

---

## Keybindings

### Search Results Menu
| Key | Action |
|---|---|
| `1`–`N` | Inspect and select the matching lyrics candidate |
| `m` | Adjust search query (pre-filled with current title/artist) |
| `n` | Create custom lyrics from scratch in your text editor |
| `s` | Skip track |
| `q` | Exit script cleanly |

### Inspection & Tag Management Menu
| Key | Action |
|---|---|
| `v` | View complete lyrics preview (all lines) |
| `e` | Open lyrics in editor for manual line adjustments |
| `r` | Romanize lyrics (Korean, Japanese, Mandarin, AnyAscii) |
| `y` | Embed lyrics into audio file metadata |
| `d` | *(Existing tags only)* Permanently delete lyrics tag from file |
| `o` | *(Existing tags only)* Ignore existing tag and search online |
| `b` | Return to candidate list (uses cached search results) |

---

## Tagging Specifications

Lyrics are written directly into standard metadata containers without transcoding audio streams:

* **FLAC, OGG Vorbis, Opus:** Vorbis Comment `LYRICS`.
* **MP3:** ID3v2 frame `USLT` (*Unsynchronized lyrics/text transcription*) using UTF-8 encoding (`encoding=3`).
* **M4A / AAC / ALAC:** MP4 metadata atom `\xa9lyr` (`©lyr`).

All tags are natively recognized by music servers and offline players including Navidrome, Jellyfin, Symfonium, Feishin, and Foobar2000.

---

## License

MIT License. Open for private and commercial use, modification, and distribution.
