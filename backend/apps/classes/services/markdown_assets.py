"""Deterministic Markdown asset (image + table) detection & reinjection.

The structuring/exam/recap LLM steps rewrite transcript text and may silently
drop Markdown images (`![caption](url)`) or GFM tables. Because the extracted
figures are real saved assets that MUST reach the student, these pure helpers
guarantee preservation without trusting the model: any image/table present in a
unit's verbatim ``source_markdown`` but missing from its rewritten
``content_markdown`` is appended back.
"""

from __future__ import annotations

import re
from typing import List

_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def image_refs(md: str) -> List[str]:
    """Return the full ``![...](...)`` image references found in ``md`` (in order)."""
    out: List[str] = []
    for m in re.finditer(r"!\[[^\]]*\]\([^)]+\)", md or ""):
        out.append(m.group(0))
    return out


def image_urls(md: str) -> List[str]:
    """Return just the URLs of the images found in ``md``."""
    return [m.group(1).strip() for m in _IMAGE_RE.finditer(md or "")]


def table_blocks(md: str) -> List[str]:
    """Return contiguous GFM table blocks (>= 2 pipe lines incl. a separator row)."""
    blocks: List[str] = []
    cur: List[str] = []

    def _flush():
        if len(cur) >= 2 and any(set(l.replace("|", "").replace(" ", "")) <= set("-:") and "-" in l for l in cur):
            blocks.append("\n".join(cur).strip())
        cur.clear()

    for line in (md or "").splitlines():
        if line.strip().startswith("|"):
            cur.append(line)
        else:
            _flush()
    _flush()
    return blocks


def reinject(source_md: str, content_md: str) -> str:
    """Append any image/table from ``source_md`` that is missing from ``content_md``.

    Comparison is by image URL and by table-body substring, so a table or image
    that the rewrite already kept is never duplicated.
    """
    source_md = source_md or ""
    content_md = content_md or ""
    additions: List[str] = []

    present_urls = set(image_urls(content_md))
    for ref, url in zip(image_refs(source_md), image_urls(source_md)):
        if url and url not in present_urls:
            additions.append(ref)
            present_urls.add(url)

    for block in table_blocks(source_md):
        # Use the first data row as a fingerprint to avoid re-adding kept tables.
        rows = [l for l in block.splitlines() if l.strip().startswith("|")]
        fingerprint = next(
            (l for l in rows if not (set(l.replace("|", "").replace(" ", "")) <= set("-:"))),
            rows[0] if rows else "",
        ).strip()
        if fingerprint and fingerprint not in content_md:
            additions.append(block)

    if not additions:
        return content_md
    return (content_md.rstrip() + "\n\n" + "\n\n".join(additions)).strip()
