#!/usr/bin/env python3
"""
Compile ``.po`` catalogues to ``.mo`` without the GNU gettext binaries.

``manage.py compilemessages`` shells out to ``msgfmt``, and ``makemessages``
shells out to ``xgettext``. Neither is installed on every machine (and neither is
available in some CI images), which would otherwise make translated API
responses undeployable. This script replaces ``msgfmt`` only -- *extraction*
still needs gettext, so run ``manage.py makemessages`` on a machine that has it
when you add new source strings.

Usage:
    python scripts/compile_messages.py [locale_dir]
"""

from __future__ import annotations

import array
import struct
import sys
from pathlib import Path

MAGIC = 0x950412DE


def _unescape(value: str) -> str:
    """Decode a .po quoted-string body."""
    return (
        value.replace(r"\\n", "\n")
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
        .replace(r"\"", '"')
        .replace(r"\\", "\\")
    )


def _strip_quotes(line: str) -> str:
    line = line.strip()
    if len(line) >= 2 and line[0] == '"' and line[-1] == '"':
        return line[1:-1]
    return line


def parse_po(path: Path) -> dict[str, str]:
    """Parse a .po file into {msgid: msgstr}. Fuzzy and empty entries are skipped."""
    catalog: dict[str, str] = {}

    msgid: list[str] = []
    msgstr: list[str] = []
    msgctxt: list[str] = []
    section: str | None = None
    fuzzy = False
    pending_fuzzy = False

    def flush() -> None:
        nonlocal msgid, msgstr, msgctxt, fuzzy
        if section is not None:
            key = "".join(msgid)
            value = "".join(msgstr)
            if msgctxt:
                # gettext keys a context entry as ctxt + EOT + msgid.
                key = "".join(msgctxt) + "\x04" + key
            # An empty translation means "untranslated" -- omit it so gettext
            # falls back to the msgid instead of returning "".
            if not fuzzy and (value or key == ""):
                catalog[_unescape(key)] = _unescape(value)
        msgid, msgstr, msgctxt = [], [], []
        fuzzy = False

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if line.startswith("#,"):
            pending_fuzzy = "fuzzy" in line
            continue
        if line.startswith("#") or not line:
            if not line:
                pass
            continue

        if line.startswith("msgctxt "):
            flush()
            fuzzy = pending_fuzzy
            pending_fuzzy = False
            section = "msgctxt"
            msgctxt = [_strip_quotes(line[len("msgctxt ") :])]
        elif line.startswith("msgid_plural "):
            # Plural forms are not used by this project's catalogues; keep the
            # singular translation and ignore the plural variants.
            section = "msgid_plural"
        elif line.startswith("msgid "):
            if section in {"msgstr", "msgid_plural"}:
                flush()
                section = None
            if section is None:
                fuzzy = pending_fuzzy
                pending_fuzzy = False
            section = "msgid"
            msgid = [_strip_quotes(line[len("msgid ") :])]
        elif line.startswith("msgstr["):
            index = line[line.index("[") + 1 : line.index("]")]
            section = "msgstr" if index == "0" else "ignore"
            if section == "msgstr":
                msgstr = [_strip_quotes(line[line.index("]") + 1 :])]
        elif line.startswith("msgstr "):
            section = "msgstr"
            msgstr = [_strip_quotes(line[len("msgstr ") :])]
        elif line.startswith('"'):
            fragment = _strip_quotes(line)
            if section == "msgid":
                msgid.append(fragment)
            elif section == "msgstr":
                msgstr.append(fragment)
            elif section == "msgctxt":
                msgctxt.append(fragment)

    flush()
    return catalog


def write_mo(catalog: dict[str, str], destination: Path) -> int:
    """Serialise a catalogue in GNU .mo binary format."""
    items = sorted(catalog.items())
    ids = b""
    strs = b""
    offsets: list[tuple[int, int, int, int]] = []

    for msgid, msgstr in items:
        encoded_id = msgid.encode("utf-8")
        encoded_str = msgstr.encode("utf-8")
        offsets.append((len(ids), len(encoded_id), len(strs), len(encoded_str)))
        ids += encoded_id + b"\x00"
        strs += encoded_str + b"\x00"

    count = len(items)
    key_start = 7 * 4 + 16 * count
    value_start = key_start + len(ids)

    key_offsets: list[int] = []
    value_offsets: list[int] = []
    for id_offset, id_length, str_offset, str_length in offsets:
        key_offsets += [id_length, id_offset + key_start]
        value_offsets += [str_length, str_offset + value_start]

    output = struct.pack(
        "Iiiiiii",
        MAGIC,
        0,  # revision
        count,
        7 * 4,  # offset of the original-strings table
        7 * 4 + count * 8,  # offset of the translated-strings table
        0,  # hash table size
        0,  # hash table offset
    )
    output += array.array("i", key_offsets + value_offsets).tobytes()
    output += ids
    output += strs

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    return count


def main(argv: list[str]) -> int:
    locale_dir = Path(argv[1]) if len(argv) > 1 else Path(__file__).parent.parent / "locale"
    if not locale_dir.is_dir():
        print(f"No locale directory at {locale_dir}", file=sys.stderr)
        return 1

    po_files = sorted(locale_dir.glob("*/LC_MESSAGES/*.po"))
    if not po_files:
        print(f"No .po files found under {locale_dir}", file=sys.stderr)
        return 1

    for po_file in po_files:
        catalog = parse_po(po_file)
        mo_file = po_file.with_suffix(".mo")
        # Drop the metadata-only entry from the reported count.
        count = write_mo(catalog, mo_file)
        translated = count - (1 if "" in catalog else 0)
        print(f"{po_file.relative_to(locale_dir)} -> {mo_file.name} ({translated} strings)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
