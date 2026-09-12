"""Regression tests for the issues found in the 2.x review."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetchlyrics import config, editor, providers, tagging, text  # noqa: E402
from fetchlyrics.app import natural_key  # noqa: E402


# --- config merging ----------------------------------------------------------
def test_partial_user_config_keeps_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"settings": {"preview_lines": 40}}', encoding="utf-8")
    merged, warnings = config.load_config(path)
    assert warnings == []
    assert merged["settings"]["preview_lines"] == 40
    # Sections omitted by the user must survive the merge.
    assert "non_latin_ratio_threshold" in merged["settings"]
    assert "ignore_words_artist_match" in merged["cleaning"]


def test_invalid_config_falls_back_with_warning(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    merged, warnings = config.load_config(path)
    assert warnings
    assert merged["api"]["lrclib_url"].startswith("https://")


def test_defaults_are_not_mutated_by_merge(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"aliases": [["foo"]]}', encoding="utf-8")
    config.load_config(path)
    assert config.DEFAULT_CONFIG["aliases"][0][0] == "tomorrow x together"


# --- artist matching ---------------------------------------------------------
def test_alias_lookup_respects_word_boundaries():
    # "Liu Yifei" used to match the IU alias group via a naive substring test.
    assert text.get_artist_aliases("Liu Yifei") == []
    assert "이지은" in text.get_artist_aliases("IU")
    assert "tomorrow x together" in text.get_artist_aliases("TXT")


def test_matches_artist_rejects_substring_false_positives():
    assert not text.matches_artist("IU", "Liu Yifei")
    assert text.matches_artist("IU", "아이유 (IU)")
    assert text.matches_artist("Tomorrow X Together", "TXT")
    assert not text.matches_artist("Red Velvet", "The Velvet Underground")


# --- timestamps and script detection -----------------------------------------
@pytest.mark.parametrize("line", ["[0:12.34]hello", "[00:12.34]hello", "[00:12]hello", "[000:12:34]hello"])
def test_single_digit_and_variant_timestamps(line):
    assert text.has_timestamps(line)


def test_lrc_metadata_is_not_a_timestamp():
    assert not text.has_timestamps("[ar:Some Artist]\n[ti:Song]\nplain line")


def test_non_latin_detection():
    assert text.is_non_latin("사랑해 사랑해 사랑해")
    assert not text.is_non_latin("[00:10.00]I love you so")
    assert not text.is_non_latin("Café naïve résumé")


def test_detect_script():
    assert text.detect_script("사랑해") == "ko"
    assert text.detect_script("ありがとう 世界") == "ja"
    assert text.detect_script("我爱你") == "zh"
    assert text.detect_script("Just English") is None


def test_romanization_preserves_timestamps():
    lyrics = "[00:10.00]사랑해\n[00:12.50]hello"
    out = text.romanize_lyrics(lyrics, "ko")
    assert out.splitlines()[0].startswith("[00:10.00]")
    assert out.splitlines()[1] == "[00:12.50]hello"


# --- editor ------------------------------------------------------------------
def test_editor_command_splits_arguments(monkeypatch):
    monkeypatch.setenv("EDITOR", "code --wait")
    assert editor.editor_command() == ["code", "--wait"]


def test_editor_roundtrip(monkeypatch, tmp_path):
    script = tmp_path / "fake_editor.py"
    script.write_text(
        "import sys\nopen(sys.argv[1], 'w', encoding='utf-8').write('edited')\nsys.exit(1)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EDITOR", f"{sys.executable} {script}")
    # A non-zero exit code must not abort the session.
    assert editor.open_editor("original") == "edited"


def test_missing_editor_raises_editor_error(monkeypatch):
    monkeypatch.setenv("EDITOR", "definitely-not-an-editor-binary")
    with pytest.raises(editor.EditorError):
        editor.open_editor("x")


# --- ranking -----------------------------------------------------------------
def _cand(**kwargs):
    base = dict(provider="LRCLIB", artist="A", title="T", album="X", text="[00:01.00]la")
    base.update(kwargs)
    return providers.Candidate(**base)


def test_unknown_duration_does_not_outrank_verified_match():
    verified = _cand(synced=True, latin=True, has_duration=True, diff=2)
    unknown = _cand(synced=True, latin=True, has_duration=False, diff=0)
    ranked = sorted([unknown, verified], key=providers.rank_key)
    assert ranked[0] is verified


def test_exact_match_wins():
    exact = _cand(synced=False, exact=True, has_duration=True)
    fuzzy = _cand(synced=True, exact=False, has_duration=True)
    assert sorted([fuzzy, exact], key=providers.rank_key)[0] is exact


def test_prefer_latin_is_configurable():
    original = _cand(synced=True, latin=False, has_duration=True)
    romanized = _cand(synced=True, latin=True, has_duration=True)

    config.CONFIG["settings"]["prefer_latin"] = True
    assert sorted([original, romanized], key=providers.rank_key)[0] is romanized

    config.CONFIG["settings"]["prefer_latin"] = False
    assert sorted([romanized, original], key=providers.rank_key)[0] is original
    config.CONFIG["settings"]["prefer_latin"] = True


def test_lrclib_queries_are_deduplicated():
    queries = providers._lrclib_queries("Song", "IU", "Album", 200)
    assert len(queries) == len(set((e, tuple(sorted(p.items()))) for e, p in queries))
    assert any(endpoint == "get" for endpoint, _ in queries)


# --- sorting -----------------------------------------------------------------
def test_natural_sort_orders_numbers_numerically():
    names = ["Track 10.flac", "Track 2.flac", "Track 1.flac"]
    paths = [Path("/music") / n for n in names]
    ordered = [p.name for p in sorted(paths, key=natural_key)]
    assert ordered == ["Track 1.flac", "Track 2.flac", "Track 10.flac"]


# --- tagging -----------------------------------------------------------------
def test_id3_text_avoids_nul_join():
    from mutagen.id3 import ID3, TPE1

    tags = ID3()
    tags.add(TPE1(encoding=3, text=["Artist A", "Artist B"]))
    assert tagging._id3_text(tags, "TPE1") == "Artist A"
    assert "\x00" not in tagging._id3_text(tags, "TPE1")


def test_parse_number_handles_slash_form():
    assert tagging._parse_number("5/12") == 5
    assert tagging._parse_number([(3, 10)]) == 3
    assert tagging._parse_number("") == 0


def test_embed_and_delete_roundtrip_flac(tmp_path):
    from mutagen.flac import FLAC

    src = _make_flac(tmp_path / "song.flac")
    audio = FLAC(src)
    audio["UNSYNCEDLYRICS"] = "stale text"
    audio.save()

    tagging.embed_lyrics(src, "[00:01.00]fresh")
    audio = FLAC(src)
    assert audio["LYRICS"][0] == "[00:01.00]fresh"
    # The competing field must be gone, not merely shadowed.
    assert "unsyncedlyrics" not in {k.lower() for k in audio.keys()}

    tagging.delete_lyrics(src)
    assert "lyrics" not in {k.lower() for k in FLAC(src).keys()}


def test_embed_raises_tagging_error_on_readonly(tmp_path):
    if os.name == "nt" or os.geteuid() == 0:
        pytest.skip("permission semantics differ for root/Windows")
    src = _make_flac(tmp_path / "ro.flac")
    src.chmod(0o444)
    with pytest.raises(tagging.TaggingError):
        tagging.embed_lyrics(src, "text")


def test_metadata_cache_reuses_until_mtime_changes(tmp_path, monkeypatch):
    src = _make_flac(tmp_path / "cached.flac")
    cache = tagging.MetadataCache()

    calls = {"n": 0}
    original = tagging.read_metadata

    def counting(path):
        calls["n"] += 1
        return original(path)

    monkeypatch.setattr(tagging, "read_metadata", counting)
    cache.get(src)
    cache.get(src)
    assert calls["n"] == 1

    tagging.embed_lyrics(src, "new")
    cache.get(src)
    assert calls["n"] == 2


def test_unreadable_file_is_reported_not_swallowed(tmp_path):
    broken = tmp_path / "broken.flac"
    broken.write_bytes(b"not a flac file at all")
    meta = tagging.read_metadata(broken)
    assert meta.error
    assert not meta.is_taggable


# A minimal but valid FLAC stream: "fLaC" plus a single STREAMINFO block
# (44100 Hz, stereo, 16 bit, 10 s). Enough for mutagen to read and tag.
MINIMAL_FLAC_B64 = "ZkxhQ4AAACIQABAAAAAAAAAACsRC8AAGuqgAAAAAAAAAAAAAAAAAAAAA"


def _make_flac(path: Path) -> Path:
    import base64

    path.write_bytes(base64.b64decode(MINIMAL_FLAC_B64))
    return path
