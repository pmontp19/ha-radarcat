"""Translation parity and shape tests.

Catalan is the reference language (``AGENTS.md`` "Language"): every
user-facing string lives under a key in ``translations/{ca,es,en}.json``, and
``strings.json`` is the canonical schema HA tools (hassfest, the
translations builder) read first. A missing key in any of the three
languages shows up in the UI as a raw ``component.radarcat...`` path, so
these tests pin the contract before hassfest ever runs in CI:

1. **Schema parity**: ``strings.json`` and the three translation files share
   the exact same set of deep keys.
2. **Placeholder parity**: any ``{placeholder}`` in one language must appear
   in every language, or HA's string formatter raises at render time.
3. **Coverage**: every translation key the code actually references
   (``_attr_translation_key``, ``step_id=``, ``errors[...]=``) is present in
   the schema, plus the one key HA's own default machinery requires
   (``config.abort.already_configured``, see the note on
   ``_abort_if_unique_id_configured`` below) but which never appears as a
   literal string in this codebase.

Pattern mirrored from ``../ha-avisoscat/tests/test_translations.py`` (T4's
brief pointed at ``../ha-cecat``'s copy, but that repo is mid-implementation
and does not have this file yet - see ``AGENTS.md`` "Sibling repositories").
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

import pytest

COMPONENT_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "radarcat"
STRINGS_PATH = COMPONENT_DIR / "strings.json"
TRANSLATION_PATHS = {
    "ca": COMPONENT_DIR / "translations" / "ca.json",
    "es": COMPONENT_DIR / "translations" / "es.json",
    "en": COMPONENT_DIR / "translations" / "en.json",
}

# Every Python module that can reference a translation key. Restricting the
# glob keeps the coverage check fast and avoids dragging in test fixtures.
_CODE_MODULES = tuple(COMPONENT_DIR.glob("*.py"))


def _load_json(path: Path) -> dict:
    """Parse a translation file, failing with the file name on a JSON error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        pytest.fail(f"{path.relative_to(Path.cwd())} is not valid JSON: {err}")


def _deep_keys(obj: object, prefix: str = "") -> set[str]:
    """Flatten a nested dict into a set of dotted paths to its leaves.

    Only dict nesting counts: a leaf is any value that is not a dict, so a
    block missing in one language but not another is caught as a parity
    violation rather than papered over.
    """
    keys: set[str] = set()
    if isinstance(obj, dict):
        for name, value in obj.items():
            qualified = f"{prefix}.{name}" if prefix else name
            if isinstance(value, dict):
                keys |= _deep_keys(value, qualified)
            else:
                keys.add(qualified)
    return keys


@pytest.fixture(scope="module")
def strings_schema() -> set[str]:
    """The deep keys of ``strings.json``, the canonical schema."""
    return _deep_keys(_load_json(STRINGS_PATH))


@pytest.fixture(scope="module")
def translations() -> dict[str, set[str]]:
    """Deep keys of each ``translations/*.json`` file."""
    return {
        lang: _deep_keys(_load_json(path)) for lang, path in TRANSLATION_PATHS.items()
    }


@pytest.mark.parametrize("lang", sorted(TRANSLATION_PATHS))
def test_translation_file_matches_strings_schema(
    strings_schema: set[str],
    translations: dict[str, set[str]],
    lang: str,
) -> None:
    """Each translation file has exactly the keys ``strings.json`` declares.

    hassfest checks the same thing implicitly when it builds the
    translations cache, but it does not say *which* key is extra or missing.
    This assertion does, and it keeps ``strings.json`` honest as the schema
    source of truth.
    """
    extras = translations[lang] - strings_schema
    missing = strings_schema - translations[lang]
    assert not extras, f"{lang}: keys not in strings.json: {sorted(extras)}"
    assert not missing, f"{lang}: keys missing from {lang}.json: {sorted(missing)}"


def test_all_translation_files_share_the_same_key_set(
    translations: dict[str, set[str]],
) -> None:
    """ca, es and en expose the exact same set of keys: not one more, not one less.

    Catalan is the reference language (``AGENTS.md``), so every other file is
    compared against it independently rather than pairwise, which would hide
    a single-language regression behind whichever pair happened to match.
    """
    reference = translations["ca"]
    for lang, keys in translations.items():
        assert keys == reference, (
            f"{lang} diverges from the Catalan reference:\n"
            f"  only in {lang}: {sorted(keys - reference)}\n"
            f"  missing in {lang}: {sorted(reference - keys)}"
        )


_PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


def _placeholders(value: object) -> frozenset[str]:
    """Collect every ``{placeholder}`` name from a translation value.

    Walks dicts and lists so a future nested structure is covered without
    rewriting the test.
    """
    found: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            found |= _placeholders(child)
    elif isinstance(value, list):
        for child in value:
            found |= _placeholders(child)
    elif isinstance(value, str):
        found.update(_PLACEHOLDER_RE.findall(value))
    return frozenset(found)


@pytest.mark.parametrize("lang", sorted(TRANSLATION_PATHS))
def test_placeholders_match_strings_json(lang: str) -> None:
    """Every ``{placeholder}`` in ``strings.json`` is reproduced in each language.

    None of v0.1.0's strings actually carry a placeholder (docs/03-feature-
    spec.md §3: zero config fields), so this currently passes trivially -
    kept so a future placeholder (e.g. a frame count) is caught immediately
    if a translation drops or mistypes it.
    """
    strings_data = _load_json(STRINGS_PATH)
    translation_data = _load_json(TRANSLATION_PATHS[lang])

    def _dig(obj: object, parts: list[str]) -> object | None:
        cur: object = obj
        for part in parts:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        return cur

    mismatches: list[str] = []
    for dotted in _deep_keys(strings_data):
        parts = dotted.split(".")
        ref = _dig(strings_data, parts)
        if not isinstance(ref, str):
            continue  # Structural key; parity is checked by the schema test.
        other = _dig(translation_data, parts)
        if not isinstance(other, str):
            continue  # Shape parity is enforced elsewhere; do not double-report.
        ref_ph = _placeholders(ref)
        other_ph = _placeholders(other)
        if ref_ph != other_ph:
            mismatches.append(
                f"{dotted}: strings.json has {sorted(ref_ph)}, "
                f"{lang} has {sorted(other_ph)}"
            )
    assert not mismatches, "\n".join(mismatches)


# ---------------------------------------------------------------------------
# Coverage: every translation key the code references must exist in the schema.
#
# hassfest validates this at release time by introspecting the integration;
# this test fails earlier and points at the source line.
# ---------------------------------------------------------------------------


def _code_text() -> str:
    """Concatenate every Python module so a single regex pass covers them all."""
    chunks: list[str] = []
    for path in sorted(_CODE_MODULES):
        chunks.append(f"# file: {path.name}\n{path.read_text(encoding='utf-8')}")
    return "\n".join(chunks)


def _regex_keys(pattern: str, text: str, group: int = 1) -> Iterable[str]:
    yield from (m.group(group) for m in re.finditer(pattern, text, re.MULTILINE))


@pytest.fixture(scope="module")
def code_translation_references() -> dict[str, set[str]]:
    """Translation keys the code references, grouped by schema section.

    The patterns match the literal forms this codebase uses:
    ``_attr_translation_key = "..."`` for the entity, ``step_id="..."`` for
    the config-flow step and ``errors[...] = "..."`` for the form error.
    ``config.abort.already_configured`` is deliberately not covered here -
    see ``test_already_configured_abort_key_exists`` below.
    """
    text = _code_text()
    return {
        "entity": set(_regex_keys(r'_attr_translation_key\s*=\s*"([a-z0-9_]+)"', text)),
        "step": set(_regex_keys(r'step_id="([a-z0-9_]+)"', text)),
        "error": set(_regex_keys(r'errors\[[^\]]+\]\s*=\s*"([a-z0-9_]+)"', text)),
    }


def test_every_code_referenced_translation_key_exists(
    code_translation_references: dict[str, set[str]],
) -> None:
    """Every translation key named in code has a matching entry in the schema."""
    strings = _load_json(STRINGS_PATH)
    image_keys = set(strings["entity"]["image"])
    config_steps = set(strings["config"]["step"])
    errors = set(strings["config"]["error"])

    missing: dict[str, set[str]] = {}
    if code_translation_references["entity"] - image_keys:
        missing["entity.image"] = code_translation_references["entity"] - image_keys
    if code_translation_references["step"] - config_steps:
        missing["config.step"] = code_translation_references["step"] - config_steps
    if code_translation_references["error"] - errors:
        missing["config.error"] = code_translation_references["error"] - errors

    assert not missing, (
        "code references translation keys that do not exist in strings.json:\n"
        + "\n".join(f"  {k}: {sorted(v)}" for k, v in missing.items())
    )


def test_already_configured_abort_key_exists() -> None:
    """``config.abort.already_configured`` exists even though no code literal names it.

    ``config_flow.py`` calls ``self._abort_if_unique_id_configured()``, whose
    default ``error`` parameter is the literal string ``"already_configured"``
    (read live in ``homeassistant/config_entries.py``, ``_abort_if_unique_id_
    configured``) - the regex-based coverage test above cannot see a key that
    is never written out in this codebase's own source, so it is asserted
    directly here instead.
    """
    strings = _load_json(STRINGS_PATH)
    assert "already_configured" in strings["config"]["abort"]
