"""Payload obfuscation (planning.md 3.2).

This is the likeliest place for a silent cross-language bug, so the tests are
deliberately unkind: multibyte UTF-8, bytes that XOR into control characters,
and a fixture the TypeScript suite must decode byte-identically.
"""

from __future__ import annotations

import base64
import json

import pytest

from linkage_engine.data.codec import decode, encode, write_fixture, xor_bytes


def test_xor_is_its_own_inverse():
    payload, key = b"linkage", b"key"
    assert xor_bytes(xor_bytes(payload, key), key) == payload


def test_xor_rejects_an_empty_key():
    with pytest.raises(ValueError, match="must not be empty"):
        xor_bytes(b"data", b"")


def test_roundtrip_preserves_the_object():
    obj = {"id": 1, "solution": ["a", "b", "c", "d"]}
    assert decode(encode(obj, "2026-10-01"), "2026-10-01") == obj


@pytest.mark.parametrize(
    "text",
    [
        "café",
        "naïve",
        "日本語",
        "🎯 emoji",
        "mixed — em dash • bullet",
        " control chars",
    ],
)
def test_roundtrip_survives_multibyte_and_awkward_characters(text):
    """A codec that only works on plain ASCII passes a naive test and then
    fails on the first real puzzle."""
    assert decode(encode({"t": text}, "2026-10-01"), "2026-10-01") == {"t": text}


def test_output_is_pure_ascii_base64():
    """It has to survive JSON, HTTP and a file on disk untouched."""
    blob = encode({"t": "日本語 🎯"}, "2026-10-01")
    assert blob.isascii()
    base64.b64decode(blob)  # must not raise


def test_wrong_key_does_not_decode():
    blob = encode({"secret": "answer"}, "2026-10-01")
    with pytest.raises((UnicodeDecodeError, json.JSONDecodeError, ValueError)):
        decode(blob, "2026-10-02")


def test_encoding_is_byte_stable():
    """Regenerating the archive must diff cleanly (planning.md 7.8)."""
    obj = {"b": 2, "a": 1, "solution": ["x", "y"]}
    assert encode(obj, "2026-10-01") == encode(obj, "2026-10-01")


def test_key_order_does_not_change_the_payload():
    """sort_keys means two spellings of the same object encode identically."""
    assert encode({"a": 1, "b": 2}, "k") == encode({"b": 2, "a": 1}, "k")


def test_different_dates_produce_different_ciphertext():
    """True for any realistic puzzle payload, which is what actually ships."""
    obj = {
        "schemaVersion": 1,
        "id": 142,
        "start": "apple",
        "end": "ocean",
        "solution": ["newton", "gravity", "moon", "tide"],
        "bank": ["pie", "salt", "orbit", "wave", "cider", "comet", "physics"],
    }
    assert encode(obj, "2026-10-01") != encode(obj, "2026-10-02")


def test_short_payloads_can_alias_across_adjacent_dates():
    """A documented property of the scheme, not a bug to be surprised by.

    ISO dates for two adjacent days share their first 9 characters, so a
    payload shorter than 10 bytes never reaches the byte that differs and
    two days encode identically.

    This changes nothing about the threat model: planning.md 3.2 declares
    this obfuscation, not encryption, and the decoder ships in the client
    bundle regardless. Real payloads run to hundreds of bytes and use the
    whole key. The test exists so nobody rediscovers this later and mistakes
    it for a defect.
    """
    assert encode({"id": 1}, "2026-10-01") == encode({"id": 1}, "2026-10-02")
    assert encode({"id": 1}, "2026-10-01") != encode({"id": 1}, "2026-11-01")


def test_obfuscation_hides_the_plaintext():
    """Not encryption -- but it must at least defeat a DevTools glance."""
    blob = encode({"solution": ["newton", "gravity", "moon", "tide"]}, "2026-10-01")
    for word in ("newton", "gravity", "moon", "tide", "solution"):
        assert word not in blob


# --------------------------------------------------------------------------
# The cross-language fixture
# --------------------------------------------------------------------------


def test_write_fixture_is_self_consistent(tmp_path):
    """The contract handed to `web/tests/codec.test.ts`.

    If this drifts, the client silently cannot read a single puzzle -- which
    is why it is generated from the same code the exporter uses.
    """
    path = tmp_path / "codec-fixture.json"
    fixture = write_fixture(path)

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == fixture
    assert decode(fixture["encoded"], fixture["key"]) == fixture["expected"]
    assert fixture["key"] == fixture["expected"]["date"]


def test_fixture_includes_a_multibyte_probe(tmp_path):
    """Guards the exact bug this fixture exists to catch: a JS decoder that
    treats `atob` output as text rather than bytes."""
    fixture = write_fixture(tmp_path / "codec-fixture.json")
    probe = fixture["expected"]["_utf8Probe"]
    assert not probe.isascii()
    assert decode(fixture["encoded"], fixture["key"])["_utf8Probe"] == probe


def test_committed_fixture_matches_the_current_encoder():
    """The committed fixture is what the TypeScript suite actually decodes.

    Every other test here writes to `tmp_path`, so the encoder could change
    while the file on disk -- the one the TS test reads -- quietly keeps
    describing the old contract. TS would then pass against a stale fixture
    and fail on the first real puzzle, which is exactly the failure this
    fixture exists to prevent (Risk #3).

    Regenerate with `linkage emit-codec-fixture`.
    """
    from linkage_engine.config import DEFAULT

    path = DEFAULT.codec_fixture_path
    assert path.exists(), f"{path} is missing -- run `linkage emit-codec-fixture`"

    committed = json.loads(path.read_text(encoding="utf-8"))
    assert committed == write_fixture(path), (
        "codec-fixture.json is stale -- run `linkage emit-codec-fixture`"
    )
