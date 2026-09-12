# fetch-lyrics

An interactive CLI utility for Linux and Windows to search, inspect, romanize, and embed synchronized (`.lrc`) and regular lyrics into FLAC and MP3 audio files.

> **Note:** This script was developed with the assistance of Google Gemini.

---

## Features

* **Multi-Provider Search:** Parallel querying of **LRCLIB** and **NetEase Cloud Music** (native) with an optional multi-provider fallback using **`syncedlyrics`** (Megalobiz, Deezer, etc.).
* **Prioritizes Synchronization:** Prefers timestamped lyrics (`[SYNC]`) over plain text (`[PLAIN]`) and checks track duration offsets (`±Xs`).
* **Built-in Romanization:** Detects non-Latin scripts and transliterates line by line while preserving all LRC timestamps:
  * **Korean:** Hangul → Romaja (`korean-romanizer`)
  * **Japanese:** Kanji/Kana → Rōmaji / Hepburn (`pykakasi`)
  * **Mandarin:** Hanzi → Pīnyīn (`pypinyin`)
  * **Universal:** Cyrillic, Greek, Arabic, Thai, etc. → Latin (`anyascii`)
* **Terminal Workflow:**
  * Instant terminal preview of existing embedded tags when a file is opened.
  * Direct editing and fine-tuning in your preferred terminal editor (`$EDITOR`, e.g., `nano`, `nvim`, or Notepad).
  * Manual input mode (`[n]`) for unlisted, live, or rare tracks.
* **Smart Tag Cleaning:** Filters noise such as `(feat. ...)` or `[ft. ...]` for cleaner queries and supports popular group aliases (e.g., *Tomorrow X Together* ↔ *TXT*).
* **Tag Management:** Existing lyrics can be inspected, romanized on the fly, edited, wiped cleanly, or replaced via fresh online searches.

---

## Requirements & Installation

Python **3.10+** is required.

### 1. Install Base Packages

#### Ubuntu / Debian
```bash
sudo apt update
sudo apt install python3-mutagen python3-requests python3-pip
```

#### RPM-based Linux Distributions
```bash
sudo dnf install python3-mutagen python3-requests python3-pip
```

#### Windows
1. Install Python from the Microsoft Store or [python.org](https://www.python.org/downloads/) (ensure **"Add python.exe to PATH"** is checked during setup).
2. Run in PowerShell or Command Prompt:
   ```powershell
   pip install mutagen requests
   ```

---

### 2. Optional Extensions (Romanization & Multi-Provider)

Engines for transliteration and multi-provider searches are optional. If a package is missing, the script remains functional and alerts you only when you select that feature:

```bash
pip install --user pykakasi pypinyin korean-romanizer anyascii syncedlyrics
```

> **Note for newer Linux distributions:** If the system prevents global installation due to an *externally-managed-environment* (PEP 668), use a Python virtual environment (`python3 -m venv venv && source venv/bin/activate`) or append `--break-system-packages` to the pip command.

| Package | Purpose |
|---|---|
| `syncedlyrics` | Multi-provider scraping (Megalobiz, Deezer, etc.) |
| `korean-romanizer` | Hangul to Romaja transliteration |
| `pykakasi` | Kanji/Kana to Rōmaji transliteration |
| `pypinyin` | Hanzi to Pīnyīn transliteration (with tone marks) |
| `anyascii` | Universal transliteration for other writing systems |

---

## Setup

Clone the repository:
```bash
git clone [https://github.com/](https://github.com/)<username>/fetch-lyrics.git
cd fetch-lyrics
```

### Editor Configuration

The script uses the `EDITOR` environment variable to launch your preferred text editor for manual review.

* **Linux:** Defaults to `nano`. To change it:
  ```bash
  export EDITOR=nvim  # or: export EDITOR=vim
  ```
* **Windows:** In PowerShell, point it to Notepad or VS Code:
  ```powershell
  $env:EDITOR = "notepad"
  # or: $env:EDITOR = "code --wait"
  ```

---

## Usage

### On Linux
```bash
# Make executable
chmod +x fetch_lyrics.py

# Process current working directory
./fetch_lyrics.py

# Process specific music directory recursively
./fetch_lyrics.py /path/to/your/music
```

### On Windows
```powershell
# Process current directory
python fetch_lyrics.py

# Process specific folder
python fetch_lyrics.py "D:\Music\K-Pop"
```

---

## Menu Shortcuts

### Search Results & Selection
| Key | Action |
|---|---|
| `1`–`N` | Select the corresponding lyrics entry |
| `m` | Adjust search query manually |
| `n` | Create and paste custom lyrics directly in editor |
| `s` | Skip current audio file |
| `q` | Quit script cleanly (or press `Ctrl+C`) |

### Inspection Menu (After Selection or for Existing Tags)
| Key | Action |
|---|---|
| `v` | View text preview in terminal |
| `e` | Open text in editor for manual adjustment |
| `r` | Open romanization selector (Korean, Japanese, Mandarin, AnyAscii) |
| `y` | Confirm and embed lyrics into file |
| `d` | *(Existing tags only)* Completely remove lyrics tag from file |
| `o` | *(Existing tags only)* Ignore existing tag and search online |
| `b` | Return to candidate list |

---

## Tagging Specifications

Lyrics are embedded directly into file metadata containers according to open standards:

* **FLAC:** Writes to the standard Vorbis Comment field `LYRICS`.
* **MP3:** Writes to the ID3v2 frame `USLT` (*Unsynchronized lyrics/text transcription*) using **UTF-8** (`encoding=3`).

Modern players and media servers (e.g., Navidrome, Jellyfin, Symfonium, Feishin, Foobar2000, Clementine) automatically read these fields and synchronize playback if timestamps are present.

---

## License

MIT License. Free for private and commercial use, modification, and redistribution.
