# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.1] — 2026-09-13

Romanization of songs that mix several writing systems. Every fix below was
reproduced against real lyrics before and after the change.

### Added

* **Change directory from the tree overview.** `c` opens a path prompt with Tab
  completion; an empty answer keeps the current folder. The overview now shows
  which folder it is listing.
* **Mixed-script romanization.** A new *Mixed scripts* entry in the `r` menu
  converts Korean, Japanese and Chinese in a single pass. It is preselected
  only when two different Asian scripts actually share the text.
* **Choice of reading for ambiguous Han runs.** When starting a mixed
  conversion you decide whether characters that both writing systems share are
  read as Chinese or as Japanese.

### Fixed

* **A second romanization pass destroyed the first one.** Tone marks are not
  ASCII, so pykakasi split them into separate tokens and `wǒ ài nǐ` came back
  as `w  w  a i n  i n`. Romanization now works on script runs and never
  touches text that is already Latin, so passes can be combined freely.
* **Kanji lost the context of its Kana.** Splitting a line by script handed
  pykakasi a bare `見`, which reads *ken*, instead of `見つけた`, which reads
  *mitsu*. Adjacent runs with the same target language are merged before
  conversion. `見つけたよ ココロが安らぐ` was `ken tsuketayo kokoro ga an ragu`
  and is now `mitsuketayo kokoro ga yasuragu`.
* **Okurigana was broken apart by spaces.** pykakasi cuts `見つけた` into
  `見つ` + `けたよ`; joining every token with a space produced `itoshi teru` for
  `愛してる`. Verb and adjective endings are now glued back on while real word
  boundaries keep their space. Known trade-off: a particle after a Kana-ending
  compound may be glued too, so `ずっと一緒にいたい` yields `zutto isshoniitai`.
* **pykakasi silently deleted text it could not read.** Running the Japanese
  romanizer over Chinese lyrics returned an empty string — `东车书长门` simply
  vanished, and the loss only surfaced after saving. A romanizer that would
  produce nothing now returns the original text.
* **NetEase credit headers were treated as lyrics.** Files from that provider
  start with `作词 : …`, `作曲 : …` and `编曲 : …`. Being Chinese metadata, they
  made every Korean and Japanese song from NetEase look like mixed-script text.
  Credit lines are recognised by a whitelist of known labels and ignored during
  detection; a lyric line that merely contains a colon is unaffected.
* **Typographic punctuation counted as a foreign script.** `…`, em dashes and
  curly quotes are not ASCII, so a purely Korean line containing one was
  reported as mixed. Character classification now tests for letters rather
  than for ASCII.
* **Chinese next to Japanese was absorbed into Japanese.** Kana anywhere on a
  line marked every Han run on it as Kanji. Script detection now uses the same
  per-run evidence as the converter, so `我爱你 ありがとう` is reported as mixed.
* **Kana separated by a space no longer breaks Kanji detection.** `東京 の 夜`
  fell through to the fallback. Spaced Kana counts as context when nothing else
  on the line points to another language — which keeps Chinese runs on a
  language-switching line from being captured.
* **HTTP errors dumped full request URLs** into the batch output, making every
  line unreadable. They are reported as `HTTP 403 (Forbidden)` instead.

### Changed

* Distinguishing Hanzi from Kanji no longer relies on a hand-curated character
  list. A Han run is fed to pykakasi and the share of characters it has a
  reading for is measured; since its dictionary contains no simplified forms,
  incomplete coverage proves the run is not Japanese. This probes the whole
  dictionary rather than 55 selected characters, and raised the share of runs
  resolved without asking from 5/14 to 11/14 on a sample of typical lyric
  lines.
* Text written purely in characters both systems share — `月光下的思念`,
  `東京物語` — remains undecidable and follows the choice made at conversion
  time. Traditional Chinese resolves less often than simplified for this
  reason.

## [1.0.0] — 2026-09-13

First packaged release, replacing the earlier single-file script.

See the README for the full feature set. Highlights: concurrent queries against
LRCLIB, NetEase and `syncedlyrics`; confidence-aware ranking; batch mode with
`--auto` and `--dry-run`; recursive configuration merging; and a pytest suite.

[1.0.1]: https://github.com/<username>/fetch-lyrics/releases/tag/v1.0.1
[1.0.0]: https://github.com/<username>/fetch-lyrics/releases/tag/v1.0.0
