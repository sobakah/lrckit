# fetch-lyrics

An interactive CLI utility for Linux, macOS and Windows to search, inspect, romanize and embed synchronized (`.lrc`) and plain lyrics into FLAC, MP3, OGG Vorbis, Opus and M4A audio files.

Version 1.0 · Python 3.10+ · MIT

---

## Features

* **Multi-format tagging** — native embedding for FLAC (`.flac`), MP3 (`.mp3`), OGG Vorbis (`.ogg`), Opus (`.opus`) and MP4/M4A (`.m4a`), plus optional companion `.lrc` sidecar files.
* **Truly concurrent multi-provider search** — LRCLIB, NetEase Cloud Music and the optional `syncedlyrics` engine are queried in parallel on a pooled HTTP session with automatic retry and backoff. A lookup costs roughly one round-trip instead of up to thirty sequential requests.
* **Exact-match lookups** — LRCLIB's `/get` endpoint is queried with title, artist, album and duration, which returns the canonical track and prefers synchronized lyrics server-side. Fuzzy `/search` queries run alongside as a fallback.
* **Confidence-aware ranking** — results are ordered by exact match, synchronization, script preference and duration agreement. Candidates with an unknown duration no longer outrank duration-verified ones.
* **Smart tag cleaning & aliases**
  * Strips features (`feat. …`, `[ft. …]`).
  * Filters localized bracketed subtitles (Hangul, Kanji/Kana, Hanzi) out of search queries.
  * Resolves group acronyms and aliases (*Tomorrow X Together* ↔ *TXT*) using word-boundary matching, so `Liu Yifei` is no longer mistaken for `IU`.
* **Built-in romanization** with automatic script detection, preserving LRC timestamps line by line:
  * Korean: Hangul → Romaja (`korean-romanizer`)
  * Japanese: Kanji/Kana → Rōmaji, Hepburn (`pykakasi`)
  * Mandarin: Hanzi → Pīnyīn (`pypinyin`)
  * Universal: Cyrillic, Greek, Arabic, Thai … → Latin (`anyascii`)
* **Batch mode** — `--auto` tags every track that has a confident, duration-verified, synchronized match without prompting. `--dry-run` reports what would change and writes nothing.
* **Terminal workflow & safeguards**
  * Metadata cache keyed by modification time; the tree overview no longer re-parses every file on each redraw.
  * Full-text preview toggle (`v`), unsaved-change tracking with explicit save (`w`) and revert (`z`).
  * Search editing (`m`) pre-fills the current query; `R` repeats the search; returning with `b` reuses cached candidates.
  * Recursion depth and file-count caps protect against runaway scans; interactive path prompt with Tab completion.
  * Colour output honours `NO_COLOR`, non-TTY pipes and `--color`.
* **External configuration** — `config.json` for aliases, regex patterns, network behaviour and UI preferences, merged recursively over the built-in defaults so partial files stay valid.

---

## Installation

Python **3.10+** is required.

### Recommended: pipx

```bash
pipx install git+https://github.com/<username>/fetch-lyrics.git
# with romanization and the extra provider engine:
pipx install "fetch-lyrics[all] @ git+https://github.com/<username>/fetch-lyrics.git"
```

This installs a `fetch-lyrics` command on your `PATH`.

### From a checkout

```bash
git clone https://github.com/<username>/fetch-lyrics.git
cd fetch-lyrics
pip install -e ".[all]"
```

The repository also stays runnable without installation:

```bash
chmod +x fetch_lyrics.py
./fetch_lyrics.py ~/Music/Artist/Album
```

### System packages instead of pip

<details>
<summary>Ubuntu / Debian</summary>

```bash
sudo apt update
sudo apt install python3-mutagen python3-requests python3-pip
```
</details>

<details>
<summary>Fedora / RHEL / Bazzite</summary>

```bash
sudo dnf install python3-mutagen python3-requests python3-pip
```
</details>

<details>
<summary>Windows</summary>

1. Install Python from the Microsoft Store or [python.org](https://www.python.org/downloads/) (enable **“Add python.exe to PATH”**).
2. Install the dependencies:
   ```powershell
   pip install mutagen requests pyreadline3
   ```

`pyreadline3` supplies the `readline` API that Windows lacks. Without it the program still runs, but Tab completion, input history and prefilled prompts are disabled and you will see a one-line notice at startup.
</details>

> **PEP 668 / externally-managed-environment:** if your package manager blocks global pip installs, use a virtual environment (`python3 -m venv venv && source venv/bin/activate`) or append `--break-system-packages`.

### Optional extensions

Every romanization backend and the secondary scraping engine are optional. A missing package only disables that one feature and is reported where it is used.

```bash
pip install --user pykakasi pypinyin korean-romanizer anyascii syncedlyrics
```

| Package | Functionality |
|---|---|
| `syncedlyrics` | Multi-provider scraping engine (Megalobiz, Deezer, …) |
| `korean-romanizer` | Hangul → Revised Romanization of Korean |
| `pykakasi` | Kanji and Kana → Hepburn Rōmaji |
| `pypinyin` | Hanzi → Pīnyīn with tone marks |
| `anyascii` | Any non-Latin Unicode script → ASCII |
| `pyreadline3` | Windows only: Tab completion, history, prefilled prompts |

---

## Usage

```bash
# Interactive, current directory
fetch-lyrics

# Interactive, specific album
fetch-lyrics ~/Music/Artist/Album

# Unattended: tag everything with a confident match
fetch-lyrics ~/Music/Artist --auto

# See what --auto would do, without writing
fetch-lyrics ~/Music/Artist --auto --dry-run

# Also replace lyrics that are already embedded
fetch-lyrics ~/Music/Artist --auto --overwrite
```

On Windows:

```powershell
fetch-lyrics "D:\Music\K-Pop\Album"
```

### Command-line options

| Option | Effect |
|---|---|
| `path` | Music directory (default: current directory) |
| `--version` | Print the version and exit |
| `-c`, `--config FILE` | Use this config file instead of the search paths |
| `--auto` | Batch mode: tag confident matches without prompting |
| `--overwrite` | In `--auto`, also replace existing lyrics |
| `--dry-run` | In `--auto`, report changes without writing |
| `--color {auto,always,never}` | Override colour handling |
| `-v`, `-vv` | Increase log verbosity (warnings → info → debug, on stderr) |
| `--sidecar` / `--no-sidecar` | Force companion `.lrc` files on or off for this run |

`--auto` only applies a candidate when it is synchronized, the artist matches, and the duration is within `api.duration_tolerance_seconds` (or the match came from LRCLIB's exact `/get` endpoint). Anything less confident is left for interactive review.

---

## Keybindings

### Tree overview (entry screen)

| Key | Action |
|---|---|
| `1`–`N` | Jump to that track |
| `Enter` | Start with the first track |
| `q` | Quit |

### Search results menu

| Key | Action |
|---|---|
| `1`–`N` | Inspect and select a candidate |
| `m` | Adjust the search query (pre-filled with the current title/artist) |
| `R` | Repeat the search with the current query |
| `n` | Create lyrics from scratch in your editor |
| `p` / `s` | Previous / next track |
| `t` | Back to the tree overview |
| `q` | Quit |

### Inspection menu (candidate or manual entry)

| Key | Action |
|---|---|
| `v` | Full preview (all lines) |
| `e` | Open in your editor |
| `r` | Romanize (detected script is offered as the default) |
| `y` | Apply — return the text so it can be embedded |
| `b` | Back to the candidate list (cached, no new requests) |
| `q` | Quit |

### Tag management menu (track already has lyrics)

| Key | Action |
|---|---|
| `v` | Full preview (all lines) |
| `e` | Open in your editor |
| `r` | Romanize |
| `w` | Save pending changes to the file |
| `z` | Revert to the embedded version |
| `d` | Delete the lyrics tag from the file |
| `o` | Ignore the existing tag and search online |
| `p` / `s` | Previous / next track |
| `t` | Back to the tree overview |
| `q` | Quit |

Unsaved edits are marked `(modified, unsaved)` in the header, and navigating away asks before discarding them.

---

## Editor configuration

The editor is taken from `$EDITOR`, then `$VISUAL`, then `settings.default_editor`. Editor commands with arguments are supported:

```bash
export EDITOR=nvim
export EDITOR="code --wait"
export EDITOR="subl -w"
```

```powershell
$env:EDITOR = "notepad"
$env:EDITOR = "code --wait"
```

A non-zero exit status from the editor (for example `:cq` in Vim) is treated as a normal user action; the file is still read back. If the editor cannot be launched at all, you get a message and stay in the menu instead of losing the session.

---

## Configuration (`config.json`)

Lookup order:

1. `--config FILE`, if given
2. `config.json` next to the package
3. `$XDG_CONFIG_HOME/fetch-lyrics/config.json` (falls back to `~/.config/fetch-lyrics/config.json`)

User values are merged **recursively** over the built-in defaults, so a file containing only the keys you care about is valid:

```json
{
  "settings": {
    "prefer_latin": false,
    "write_sidecar_lrc": true
  }
}
```

An invalid or unreadable file produces a warning and the defaults are used — it never aborts the run.

<details>
<summary>Full default configuration</summary>

```json
{
  "aliases": [
    ["tomorrow x together", "txt", "투모로우바이투게더"],
    ["bts", "bangtan", "방탄소년단"],
    ["iu", "이지은"],
    ["snsd", "girls' generation", "소녀시대"],
    ["g-idle", "(g)i-dle", "(여자)아이들", "gidle"],
    ["seventeen", "svt", "세븐틴"],
    ["stray kids", "skz", "스트레이 키즈"],
    ["le sserafim", "르세라핌"],
    ["newjeans", "뉴진스"],
    ["blackpink", "블랙핑크"],
    ["twice", "트와이스"]
  ],
  "cleaning": {
    "feature_regex": "[\\(\\[][\\s]*(?:feat\\.?|featuring|ft\\.?)\\s+[^\\)\\]]+[\\)\\]]",
    "trailing_feature_regex": "\\s+(?:feat\\.?|featuring|ft\\.?)\\s+.*$",
    "korean_bracket_regex": "[\\(\\[][^\\)\\]]*[가-힣ㄱ-ㅎㅏ-ㅣ][^\\)\\]]*[\\)\\]]",
    "japanese_bracket_regex": "[\\(\\[][^\\)\\]]*[ぁ-ゖァ-ヺ一-龥][^\\)\\]]*[\\)\\]]",
    "chinese_bracket_regex": "[\\(\\[][^\\)\\]]*[一-龥][^\\)\\]]*[\\)\\]]",
    "ignore_words_artist_match": ["the", "and", "feat", "ft", "with", "&"]
  },
  "api": {
    "lrclib_url": "https://lrclib.net/api",
    "netease_search_url": "https://music.163.com/api/search/get/web",
    "netease_lyric_url": "https://music.163.com/api/song/lyric",
    "timeout_seconds": 6,
    "netease_search_limit": 6,
    "user_agent": "fetch-lyrics/1.0.0 (https://github.com/<username>/fetch-lyrics)",
    "max_workers": 8,
    "retry_total": 2,
    "retry_backoff": 0.3,
    "duration_tolerance_seconds": 2,
    "enable_lrclib": true,
    "enable_netease": true,
    "enable_syncedlyrics": true
  },
  "settings": {
    "supported_extensions": [".flac", ".mp3", ".ogg", ".opus", ".m4a"],
    "default_editor": "nano",
    "preview_lines": 16,
    "non_latin_ratio_threshold": 0.25,
    "max_search_depth": 3,
    "max_file_count": 250,
    "prefer_latin": true,
    "sort_by_tags": false,
    "write_sidecar_lrc": false,
    "id3_v2_version": 4,
    "uslt_language": "eng",
    "color": "auto"
  }
}
```
</details>

### Key settings

| Key | Meaning |
|---|---|
| `api.max_workers` | Parallel HTTP requests per provider stage |
| `api.retry_total` / `retry_backoff` | Automatic retries on 429 and 5xx responses |
| `api.duration_tolerance_seconds` | Maximum length difference accepted by `--auto` |
| `api.enable_*` | Turn individual providers off |
| `settings.prefer_latin` | `true` ranks romanized versions first; set `false` to prefer the original script |
| `settings.sort_by_tags` | `true` orders tracks by disc/track number; `false` uses natural filename order (`Track 2` before `Track 10`) |
| `settings.write_sidecar_lrc` | Also write a companion `.lrc` next to each track |
| `settings.id3_v2_version` | `4` (default) or `3` for players that only read ID3v2.3 |
| `settings.uslt_language` | ISO-639-2 language code stored in the MP3 `USLT` frame |
| `settings.color` | `auto`, `always` or `never` |
| `settings.max_search_depth` | Directory levels to descend. `3` means files up to three levels below the start directory are collected; deeper directories are not entered. |
| `settings.max_file_count` | Abort the scan above this many files and ask for a narrower path |

The default `user_agent` follows LRCLIB's request to identify your application by name, version and project URL. Please adjust the URL if you fork the project.

---

## Tagging specifications

Lyrics are written directly into standard metadata containers; audio streams are never transcoded.

* **FLAC, OGG Vorbis, Opus** — Vorbis comment `LYRICS`. Competing `UNSYNCEDLYRICS` and `SYNCEDLYRICS` fields are removed on write so players cannot pick up a stale version.
* **MP3** — ID3v2 `USLT` frame (unsynchronized lyrics/text transcription), UTF-8 (`encoding=3`). Written as ID3v2.4 by default; set `id3_v2_version` to `3` for older players.
* **M4A / AAC / ALAC** — MP4 atom `\xa9lyr` (`©lyr`).
* **Sidecar** — with `write_sidecar_lrc` or `--sidecar`, a `<track>.lrc` file is written alongside the audio file. Navidrome, Jellyfin and several players read these in preference to embedded tags.

All embedded tags are recognized by Navidrome, Jellyfin, Symfonium, Feishin and foobar2000.

---

## Project layout

```
fetch_lyrics.py          Standalone launcher for checkouts
fetchlyrics/
  cli.py                 Argument parsing and start-up
  app.py                 Directory scanning, navigation, menus, batch mode
  providers.py           LRCLIB / NetEase / syncedlyrics, ranking
  tagging.py             Metadata reading, writing, caching
  text.py                Tag cleaning, artist matching, romanization
  editor.py              External editor handling
  ui.py                  Colours, prompts, previews, path completion
  config.py              Defaults and recursive config merging
tests/                   pytest regression suite
```

Run the tests with:

```bash
pip install -e ".[dev]"
pytest -q
```

---

## Changes in 1.0

First packaged release. The list below is relative to the earlier single-file
`fetch_lyrics.py` script that this version replaces.

**Fixed**

* Windows start-up crash: `readline` is now imported through a shim with a `pyreadline3` fallback and a no-op stub.
* `EDITOR="code --wait"` and other editor commands with arguments no longer fail; a non-zero editor exit no longer aborts the session.
* The “search online for new lyrics now?” prompt after deleting a tag is now actually evaluated.
* MP3 titles and artists with multiple values are no longer read as NUL-joined strings.
* Alias and artist matching use word boundaries (`Liu Yifei` ≠ `IU`) and require a clear token majority (`Red Velvet` ≠ `The Velvet Underground`).
* Candidates without a known duration no longer sort ahead of duration-verified matches.
* Embedding into Vorbis containers removes competing lyrics fields instead of leaving them behind.
* Write and delete failures raise a handled error and a message instead of a traceback.
* Partial `config.json` files no longer cause `KeyError`; merging is recursive and the defaults are deep-copied.
* Timestamps like `[0:12.34]` are recognized; LRC metadata lines such as `[ar:…]` are not mistaken for timestamps.

**Improved**

* Providers run concurrently on a pooled session with retry and backoff.
* Metadata is cached by modification time; the tree overview no longer re-parses every file on redraw.
* Script detection uses codepoint ranges and caching instead of a `unicodedata.name()` call per character.
* `pykakasi` converters are created once, not per line.
* NetEase and `syncedlyrics` errors are surfaced per provider instead of being swallowed.
* The NetEase lyric fetch honours `timeout_seconds` instead of a hardcoded value.
* Tracks sort naturally (`Track 2` before `Track 10`), optionally by tag numbers.
* Previews truncate to the terminal width.

**Added**

* `--auto`, `--overwrite`, `--dry-run`, `--color`, `--verbose`, `--config`, `--sidecar`, `--version`.
* Companion `.lrc` sidecar export.
* `prefer_latin`, `sort_by_tags`, `id3_v2_version`, `uslt_language` and per-provider toggles.
* Save/revert handling for unsaved edits in the tag management menu.
* Automatic script detection as the default romanization choice.
* A pytest regression suite and `pyproject.toml` packaging with a `fetch-lyrics` entry point.

---

## Credits

Earlier versions of this script were drafted with the assistance of Google Gemini; version 1.0 was reviewed and restructured with Claude.

## License

MIT License. Free for private and commercial use, modification and distribution.
