#!/usr/bin/env python3
"""Inline site documents into index.html.

The page reads payloads from ``#tarifsPdfInline`` and ``#inscriptionMdInline``
and never fetches the source files at runtime. Re-run after replacing the
PDF or the inscription markdown:

    uv run inline-documents
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_PDF = ROOT / "tarifs_plaisir_de_danser_2026_2027.pdf"
DEFAULT_MARKDOWN = ROOT / "inscription.md"
DEFAULT_HTML = ROOT / "index.html"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Encode the tarifs PDF as base64 and copy the inscription "
            "markdown into their placeholder script tags in index.html."
        )
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF,
        help=f"Source PDF (default: {DEFAULT_PDF.name})",
    )
    parser.add_argument(
        "--markdown",
        "--md",
        dest="markdown",
        type=Path,
        default=DEFAULT_MARKDOWN,
        help=f"Source markdown (default: {DEFAULT_MARKDOWN.name})",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=DEFAULT_HTML,
        help=f"Target HTML file (default: {DEFAULT_HTML.name})",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Do not update the inlined tarifs PDF.",
    )
    parser.add_argument(
        "--skip-markdown",
        action="store_true",
        help="Do not update the inlined inscription markdown.",
    )
    return parser.parse_args(argv)


def encode_pdf(pdf_path: Path) -> str:
    data = pdf_path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"Not a PDF file: {pdf_path}")
    return base64.b64encode(data).decode("ascii")


def encode_markdown(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError(f"Markdown file is empty: {md_path}")
    if re.search(r"</script", text, flags=re.IGNORECASE):
        raise ValueError(
            f"Markdown contains a </script sequence that cannot be inlined: {md_path}"
        )
    return text.replace("\r\n", "\n").replace("\r", "\n").strip("\n") + "\n"


def replace_script_content(html: str, script_id: str, payload: str) -> str:
    pattern = re.compile(
        rf'(<script\b[^>]*\bid=["\']{re.escape(script_id)}["\'][^>]*>)(.*?)(</script>)',
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(html)
    if not match:
        raise ValueError(
            f'Could not find <script id="{script_id}"> in the HTML file. '
            "Add that placeholder tag before running this script."
        )

    def repl(found: re.Match[str]) -> str:
        return f"{found.group(1)}\n{payload}\n{found.group(3)}"

    return pattern.sub(repl, html, count=1)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    html_path = args.html.resolve()
    pdf_path = args.pdf.resolve()
    md_path = args.markdown.resolve()

    if args.skip_pdf and args.skip_markdown:
        print("error: nothing to inline (--skip-pdf and --skip-markdown).", file=sys.stderr)
        return 1
    if not html_path.is_file():
        print(f"error: HTML not found: {html_path}", file=sys.stderr)
        return 1
    if not args.skip_pdf and not pdf_path.is_file():
        print(f"error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1
    if not args.skip_markdown and not md_path.is_file():
        print(f"error: markdown not found: {md_path}", file=sys.stderr)
        return 1

    try:
        raw = html_path.read_bytes()
        newline = "\r\n" if b"\r\n" in raw else "\n"
        html = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        messages: list[str] = []

        if not args.skip_pdf:
            pdf_payload = encode_pdf(pdf_path)
            html = replace_script_content(html, "tarifsPdfInline", pdf_payload)
            messages.append(
                f"Inlined {pdf_path.name} ({pdf_path.stat().st_size} bytes) "
                f"as {len(pdf_payload)} base64 characters"
            )

        if not args.skip_markdown:
            md_payload = encode_markdown(md_path)
            html = replace_script_content(html, "inscriptionMdInline", md_payload)
            messages.append(
                f"Inlined {md_path.name} ({md_path.stat().st_size} bytes, "
                f"{len(md_payload)} characters)"
            )

        html_path.write_bytes(html.replace("\n", newline).encode("utf-8"))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    joined = " and ".join(messages)
    print(f"{joined} into {html_path.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
