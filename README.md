# fetch-lyrics

Interactive CLI utility for Linux, macOS and Windows to search, inspect, romanize and embed synchronized (`.lrc`) and plain lyrics into FLAC, MP3, OGG Vorbis, Opus and M4A files.

Version 1.0.1 · Python 3.10+ · MIT

---

## Features

* **Multi-format tagging** — FLAC, MP3, OGG Vorbis, Opus and M4A, plus optional companion `.lrc` sidecar files.
* **Concurrent multi-provider search** — LRCLIB, NetEase Cloud Music and the optional `syncedlyrics` engine are queried in parallel on a pooled HTTP session with retry and backoff.
* **Exact-match lookups** — LRCLIB's `/get` endpoint is queried with title, artist, album and duration; fuzzy `/search` queries run alongside as a fallback.
* **Confidence-aware ranking** — ordered by exact match, synchronization, script preference and duration agreement.
* **Smart tag cleaning & aliases** — strips features (`feat. …`), filters localized bracketed subtitles out of queries, and resolves group acronyms (*Tomorrow X Together* ↔ *TXT*) with word-boundary matching.
* **Romanization** with automatic script detection, preserving LRC timestamps: Hangul → Romaja, Kanji/Kana → Hepburn Rōmaji, Hanzi → Pīnyīn, and any other script → Latin via `anyascii`. Lines containing several scripts at once are split into runs and converted per run, and text that is already Latin is never touched — so passes can be combined without destroying each other's output.
* **Batch mode** — `--auto` tags every track with a confident match; `--dry-run` reports without writing.
* **Safeguards** — metadata cached by modification time, recursion depth and file-count caps, Tab-completing path prompt, colour output honouring `NO_COLOR` and non-TTY pipes.

---

## Installation

### pipx (recommended)

```bash
pipx install git+https://github.com/<username>/fetch-lyrics.git
# with romanization and the extra provider engine:
pipx install "fetch-lyrics[all] @ git+https://github.com/<username>/fetch-lyrics.git"
```

This installs a `fetch-lyrics` command on your `PATH`.

> **fish users:** `pipx` and `pip install --user` place their launchers in `~/.local/bin`. On Fedora that directory is added to `PATH` by `~/.bash_profile`, which fish never reads — so the install succeeds but `fetch-lyrics` is not found. Add it once with `fish_add_path ~/.local/bin` (fish 3.2+); it persists across sessions. In a virtual environment, use `source venv/bin/activate.fish` rather than `activate`, and set the editor with `set -gx EDITOR nvim` rather than `export`.

### From a checkout

```bash
git clone https://github.com/<username>/fetch-lyrics.git
cd fetch-lyrics
pip install -e ".[all]"
```

The checkout also runs without installation. `fetch_lyrics.py` is only a launcher — it needs the sibling `fetchlyrics/` package directory next to it, and `config.json` one level above the package:

```
fetch_lyrics.py
config.json
fetchlyrics/
    __init__.py  cli.py  app.py  providers.py
    tagging.py   text.py editor.py ui.py config.py
```

```bash
chmod +x fetch_lyrics.py
./fetch_lyrics.py ~/Music/Artist/Album
```

### Dependencies

Required: `mutagen`, `requests`. On Windows also `pyreadline3`, which supplies the `readline` API that Windows lacks — without it the program still runs, but Tab completion, history and prefilled prompts are disabled.

```bash
pip install mutagen requests          # Linux/macOS
pip install mutagen requests pyreadline3   # Windows
```

Optional. A missing package only disables that one feature and is reported where it is used:

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

> **PEP 668 / externally-managed-environment:** if your package manager blocks global pip installs, use a virtual environment or append `--break-system-packages`.

---

## Usage

```bash
fetch-lyrics                              # interactive, current directory
fetch-lyrics ~/Music/Artist/Album         # interactive, specific album
fetch-lyrics ~/Music/Artist --auto        # tag everything with a confident match
fetch-lyrics ~/Music/Artist --auto --dry-run
```

| Option | Effect |
|---|---|
| `path` | Music directory (default: current directory) |
| `--version` | Print the version and exit |
| `-c`, `--config FILE` | Use this config file instead of the search paths |
| `--auto` | Batch mode: tag confident matches without prompting |
| `--overwrite` | In `--auto`, also replace existing lyrics |
| `--dry-run` | In `--auto`, report changes without writing |
| `--color {auto,always,never}` | Override colour handling |
| `-v`, `-vv` | Increase log verbosity (on stderr) |
| `--sidecar` / `--no-sidecar` | Force companion `.lrc` files on or off |

`--auto` only applies a candidate when it is synchronized, the artist matches, and the duration is within `api.duration_tolerance_seconds` — or the match came from LRCLIB's exact `/get` endpoint. Anything less confident is left for interactive review.

---

## Keybindings

**Tree overview (entry screen)** — `1`–`N` jump to track · `Enter` start with the first · `c` change directory · `q` quit

**Search results**

| Key | Action |
|---|---|
| `1`–`N` | Inspect and select a candidate |
| `m` | Adjust the search query (pre-filled) |
| `R` | Repeat the search |
| `n` | Create lyrics from scratch in your editor |
| `p` / `s` | Previous / next track |
| `t` | Back to the tree overview |
| `q` | Quit |

**Inspection** (candidate or manual entry)

| Key | Action |
|---|---|
| `v` | Full preview (all lines) |
| `e` | Open in your editor |
| `r` | Romanize (detected script offered as default) |
| `y` | Apply and embed |
| `b` | Back to the candidate list (cached, no new requests) |
| `q` | Quit |

**Tag management** (track already has lyrics)

| Key | Action |
|---|---|
| `v` / `e` / `r` | Full preview · editor · romanize |
| `w` | Save pending changes to the file |
| `z` | Revert to the embedded version |
| `d` | Delete the lyrics tag from the file |
| `o` | Ignore the existing tag and search online |
| `p` / `s` / `t` | Previous track · next track · tree overview |
| `q` | Quit |

Unsaved edits are marked `(modified, unsaved)` in the header; navigating away asks before discarding them.

---

## Romanization of mixed-script lyrics

Chinese and Japanese share Han characters, so handing a whole line to one backend goes wrong in both directions: pykakasi reads Hanzi as Kanji, and a second pass mangles the first pass's output because tone marks are not ASCII.

Each line is therefore split into runs of one script, and only non-Latin runs are converted. A Han run is classified in this order:

1. **Character proof.** A shinjitai form means Japanese. For Chinese, the run is fed to pykakasi and the share of characters it has a reading for is measured — its dictionary contains no simplified forms, so incomplete coverage proves the run is not Japanese. This probes the whole dictionary rather than a curated list.
2. **Kana contact.** Kana directly touching the run means Japanese.
3. **Kana on the line,** but only when nothing else on that line points elsewhere — no Hangul, no run already proven Chinese. This catches spaced Japanese without capturing Chinese on a language-switching line.
4. **Your choice**, for everything still ambiguous.

Pick **Mixed scripts** in the `r` menu. It is preselected only when two different Asian scripts actually share the text — a single Asian script next to Latin does not need it, since Latin passages are left alone anyway. A line like `사랑해 我爱你 ありがとう` becomes `saranghae wǒ ài nǐ arigatou` in one pass.

**Provider credits.** NetEase prepends headers such as `作词 : …` and `编曲 : …` to its LRC files. Those are Chinese metadata, not lyrics, and they are ignored when deciding which scripts a song contains — otherwise every Korean or Japanese song from that provider would look mixed. They are still passed through the conversion, so a Korean name in a credit line gets romanized along with the rest.

**What stays ambiguous.** Text written purely in characters both systems share cannot be told apart without understanding the language — `月光下的思念` and `東京物語` are valid in either reading. Those runs follow the choice you make when starting the conversion. In a measured sample of typical lyric lines, roughly four in five resolved on their own; the rest fell back to that choice. Traditional Chinese resolves less often than simplified, because traditional forms are largely the same characters Japanese uses.

---

## Editor

Taken from `$EDITOR`, then `$VISUAL`, then `settings.default_editor`. Commands with arguments are supported:

```bash
export EDITOR="code --wait"     # or: nvim, "subl -w", …
```
```powershell
$env:EDITOR = "notepad"
```

A non-zero exit status (for example `:cq` in Vim) is treated as a normal user action and the file is still read back. If the editor cannot be launched, you get a message and stay in the menu.

---

## Configuration

Lookup order: `--config FILE` → `config.json` next to the package → `$XDG_CONFIG_HOME/fetch-lyrics/config.json` (falling back to `~/.config/fetch-lyrics/config.json`).

User values are merged **recursively** over the built-in defaults, so a file with only the keys you care about is valid:

```json
{
  "settings": {
    "prefer_latin": false,
    "write_sidecar_lrc": true
  }
}
```

An invalid or unreadable file produces a warning and the defaults are used — it never aborts the run. The shipped `config.json` contains every key with its default value.

**`aliases`** — groups of equivalent artist spellings, matched at word boundaries.

**`cleaning`** — `feature_regex`, `trailing_feature_regex` and the `korean_`/`japanese_`/`chinese_bracket_regex` patterns removed from search queries, plus `ignore_words_artist_match`.

**`api`**

| Key | Meaning |
|---|---|
| `lrclib_url`, `netease_search_url`, `netease_lyric_url` | Provider endpoints |
| `timeout_seconds` | Per-request timeout |
| `netease_search_limit` | Results requested per NetEase query |
| `user_agent` | Sent to LRCLIB; identify your fork by name, version and URL |
| `max_workers` | Parallel HTTP requests per provider stage |
| `retry_total`, `retry_backoff` | Automatic retries on 429 and 5xx |
| `duration_tolerance_seconds` | Maximum length difference accepted by `--auto` |
| `enable_lrclib`, `enable_netease`, `enable_syncedlyrics` | Turn individual providers off |

**`settings`**

| Key | Meaning |
|---|---|
| `supported_extensions` | File types included in a scan |
| `default_editor` | Fallback when `$EDITOR` and `$VISUAL` are unset |
| `preview_lines` | Lines shown in the short preview |
| `non_latin_ratio_threshold` | Share of non-Latin letters above which lyrics count as original-script |
| `max_search_depth` | Directory levels to descend. `3` collects files up to three levels below the start directory; deeper directories are not entered. |
| `max_file_count` | Abort the scan above this many files and ask for a narrower path |
| `prefer_latin` | `true` ranks romanized versions first; `false` prefers the original script |
| `sort_by_tags` | `true` orders by disc/track number; `false` uses natural filename order (`Track 2` before `Track 10`) |
| `write_sidecar_lrc` | Also write a companion `.lrc` next to each track |
| `id3_v2_version` | `4` (default) or `3` for players that only read ID3v2.3 |
| `uslt_language` | ISO-639-2 code stored in the MP3 `USLT` frame |
| `color` | `auto`, `always` or `never` |

---

## Tagging

Lyrics are written into standard metadata containers; audio streams are never transcoded.

* **FLAC, OGG Vorbis, Opus** — Vorbis comment `LYRICS`. Competing `UNSYNCEDLYRICS` and `SYNCEDLYRICS` fields are removed on write.
* **MP3** — ID3v2 `USLT` frame, UTF-8 (`encoding=3`), written as ID3v2.4 by default.
* **M4A / AAC / ALAC** — MP4 atom `\xa9lyr` (`©lyr`).
* **Sidecar** — with `write_sidecar_lrc` or `--sidecar`, a `<track>.lrc` is written alongside the audio file.

Embedded tags are recognized by Navidrome, Jellyfin, Symfonium, Feishin and foobar2000.

---

## Development

```
fetch_lyrics.py          Launcher for checkouts
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

```bash
pip install -e ".[dev]"
pytest -q
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

---

## License

MIT. Free for private and commercial use, modification and distribution.
