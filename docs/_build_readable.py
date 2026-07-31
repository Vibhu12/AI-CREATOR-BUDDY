"""Generate readable, downloadable documentation in multiple formats.

Outputs:
  /app/docs/CreatorOS_Design_Docs.html   Single self-contained HTML — viewable in any browser
  /app/docs/CreatorOS_Design_Docs.md     Single consolidated markdown file
  /app/docs/CreatorOS_Design_Docs.txt    Plain-text fallback

The HTML file has all CSS inlined, works offline, prints to PDF cleanly.
"""
from __future__ import annotations

import re
from pathlib import Path

import markdown

DOCS_DIR = Path("/app/docs")

FILES = [
    ("01_HLD.md",            "Part I — High-Level Design"),
    ("02_LLD.md",            "Part II — Low-Level Design"),
    ("03_USER_JOURNEY.md",   "Part III — End-to-End User Journey"),
    ("04_METRICS_AND_AB.md", "Part IV — Evaluation Metrics & A/B Testing"),
]

# --- Consolidated Markdown ----------------------------------------------
def build_markdown():
    parts = [
        "# CreatorOS — Complete Engineering Design Documentation\n",
        "> **Version 1.0 · June 2026 · Confidential**\n",
        "> HLD · LLD · User Journeys · Evaluation Metrics · A/B Framework\n",
        "\n---\n\n",
        "## Table of Contents\n",
    ]
    for i, (_, title) in enumerate(FILES, 1):
        parts.append(f"{i}. **{title}**\n")
    parts.append("\n---\n\n")

    for filename, part_title in FILES:
        md = (DOCS_DIR / filename).read_text(encoding="utf-8")
        parts.append(f"\n\n# {part_title}\n\n")
        parts.append(md)
        parts.append("\n\n---\n\n")

    out = DOCS_DIR / "CreatorOS_Design_Docs.md"
    out.write_text("".join(parts), encoding="utf-8")
    print(f"Wrote: {out}  ({out.stat().st_size / 1024:.1f} KB)")


# --- HTML with inline CSS ------------------------------------------------
HTML_STYLES = """
:root {
  --gold: #C9941D;
  --gold-soft: rgba(201,148,29,0.08);
  --ink: #1a1a1a;
  --mute: #666;
  --border: #e5e5e5;
  --code-bg: #f6f6f6;
  --code-fg: #8E2238;
  --header-bg: #1A1A1A;
  --row-alt: #fafafa;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #fff; color: var(--ink); }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 15px;
  line-height: 1.65;
  max-width: 980px;
  margin: 0 auto;
  padding: 48px 56px 96px;
}
@media (max-width: 800px) { body { padding: 24px 20px 64px; font-size: 14px; } }

/* Cover */
.cover {
  text-align: center;
  padding: 96px 0 32px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 40px;
}
.cover h1 { font-size: 56px; margin: 0; color: var(--gold); letter-spacing: -2px; font-weight: 800; }
.cover .subtitle { font-size: 22px; color: var(--ink); margin-top: 10px; }
.cover .kicker { font-size: 13px; color: var(--mute); margin-top: 8px; letter-spacing: 1.5px; text-transform: uppercase; }
.cover .meta { font-size: 12px; color: var(--mute); margin-top: 32px; }

.part-title {
  text-align: center;
  padding: 64px 0 16px;
  border-top: 1px solid var(--border);
  margin-top: 64px;
}
.part-title h1 {
  font-size: 32px;
  color: var(--gold);
  margin: 0;
}

/* Content */
h1 { font-size: 28px; color: var(--gold); border-bottom: 2px solid var(--gold); padding-bottom: 6px; margin-top: 40px; }
h2 { font-size: 22px; margin-top: 34px; color: var(--ink); border-bottom: 1px solid var(--border); padding-bottom: 4px; }
h3 { font-size: 17px; margin-top: 24px; color: var(--ink); }
h4 { font-size: 15px; margin-top: 18px; color: var(--ink); text-transform: uppercase; letter-spacing: 0.6px; }
p  { margin: 10px 0; }
strong { color: var(--ink); }

/* Lists */
ul, ol { padding-left: 24px; margin: 8px 0; }
li { margin: 4px 0; }
ul ul, ol ol, ul ol, ol ul { margin: 4px 0; }

/* Inline code + code blocks */
code {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.88em;
  color: var(--code-fg);
  background: var(--code-bg);
  padding: 2px 5px;
  border-radius: 4px;
}
pre {
  background: var(--code-bg);
  border-radius: 6px;
  padding: 12px 16px;
  overflow-x: auto;
  font-size: 12.5px;
  border: 1px solid #e0e0e0;
  line-height: 1.5;
}
pre code {
  background: transparent;
  padding: 0;
  color: #333;
  font-size: 12.5px;
}

/* Tables */
table {
  border-collapse: collapse;
  width: 100%;
  margin: 14px 0;
  font-size: 13px;
  overflow-x: auto;
  display: block;
}
@media (min-width: 900px) { table { display: table; } }
thead { background: var(--header-bg); color: #fff; }
th, td {
  padding: 8px 10px;
  border: 1px solid #ddd;
  text-align: left;
  vertical-align: top;
}
th { font-weight: 600; }
tbody tr:nth-child(even) { background: var(--row-alt); }

/* Horizontal rule */
hr { border: 0; border-top: 1px solid var(--border); margin: 24px 0; }

/* Blockquote */
blockquote {
  border-left: 3px solid var(--gold);
  padding: 4px 14px;
  margin: 12px 0;
  color: var(--mute);
  background: var(--gold-soft);
  border-radius: 0 6px 6px 0;
}

/* Links */
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }

/* Print */
@media print {
  body { padding: 0 24px; max-width: 100%; }
  .cover { page-break-after: always; }
  .part-title { page-break-before: always; }
  h1, h2, h3, h4 { page-break-after: avoid; }
  pre, table { page-break-inside: avoid; }
  a { color: inherit; text-decoration: none; }
}

/* TOC */
.toc { background: #fafafa; border: 1px solid var(--border); border-radius: 6px; padding: 16px 22px; margin: 24px 0; }
.toc h2 { border: 0; margin: 0 0 8px; font-size: 16px; color: var(--gold); }
.toc ol { margin: 8px 0 0; }

/* Note */
.doc-note {
  background: var(--gold-soft);
  border-left: 3px solid var(--gold);
  padding: 12px 16px;
  border-radius: 0 6px 6px 0;
  margin: 20px 0;
  font-size: 13px;
  color: var(--ink);
}
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CreatorOS — Complete Engineering Design Documentation</title>
<style>{styles}</style>
</head>
<body>

<div class="cover">
  <h1>CreatorOS</h1>
  <div class="subtitle">Complete Engineering Design Documentation</div>
  <div class="kicker">HLD · LLD · User Journeys · Evaluation Metrics · A/B Framework</div>
  <div class="meta">
    Version 1.0 &nbsp;·&nbsp; June 2026 &nbsp;·&nbsp; Confidential<br>
    Owner: Engineering
  </div>
</div>

<div class="toc">
  <h2>Table of Contents</h2>
  <ol>
    {toc_items}
  </ol>
</div>

<div class="doc-note">
  <strong>💡 Tip:</strong> To save this as a PDF, use your browser's <em>Print → Save as PDF</em> feature.
  The layout is print-optimised.
</div>

{content}

<hr>
<p style="text-align:center; color: var(--mute); font-size: 11px; margin-top: 48px;">
  CreatorOS · Engineering Design Documentation · Confidential<br>
  Generated {date}
</p>

</body>
</html>
"""


def build_html():
    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "attr_list",
            "def_list",
            "nl2br",
            "sane_lists",
        ]
    )

    toc_items = "\n    ".join(
        f'<li><a href="#part-{i}">{part_title}</a></li>'
        for i, (_, part_title) in enumerate(FILES, 1)
    )

    content_parts = []
    for i, (filename, part_title) in enumerate(FILES, 1):
        md_text = (DOCS_DIR / filename).read_text(encoding="utf-8")
        # Strip the leading H1 to avoid double titles
        md_text = re.sub(r"^# .+\n\n?", "", md_text, count=1)
        content_html = md.convert(md_text)
        md.reset()

        content_parts.append(
            f'<div class="part-title" id="part-{i}"><h1>{part_title}</h1></div>\n{content_html}\n'
        )

    from datetime import datetime
    html = HTML_TEMPLATE.format(
        styles=HTML_STYLES,
        toc_items=toc_items,
        content="\n\n".join(content_parts),
        date=datetime.utcnow().strftime("%B %d, %Y"),
    )

    out = DOCS_DIR / "CreatorOS_Design_Docs.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote: {out}  ({out.stat().st_size / 1024:.1f} KB)")


def build_txt():
    """Plain-text fallback — strips markdown to raw text."""
    parts = ["CreatorOS — Complete Engineering Design Documentation\n",
             "=" * 60 + "\n",
             "Version 1.0 · June 2026 · Confidential\n\n"]
    for filename, part_title in FILES:
        parts.append("\n\n" + "=" * 60 + "\n")
        parts.append(f"  {part_title}\n")
        parts.append("=" * 60 + "\n\n")
        md_text = (DOCS_DIR / filename).read_text(encoding="utf-8")
        # Strip markdown formatting for plain text
        txt = md_text
        txt = re.sub(r"^#+\s*", "", txt, flags=re.MULTILINE)  # headers
        txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt)             # bold
        txt = re.sub(r"\*(.+?)\*", r"\1", txt)                 # italic
        txt = re.sub(r"`([^`]+?)`", r"\1", txt)                # inline code
        txt = re.sub(r"```\w*\n", "", txt)                     # code fences open
        txt = re.sub(r"```\n?", "", txt)                       # code fences close
        parts.append(txt)
    out = DOCS_DIR / "CreatorOS_Design_Docs.txt"
    out.write_text("".join(parts), encoding="utf-8")
    print(f"Wrote: {out}  ({out.stat().st_size / 1024:.1f} KB)")


def build_docx_from_html():
    """Best-effort — leave existing docx alone if it works. Just report."""
    docx_path = DOCS_DIR / "CreatorOS_Design_Docs.docx"
    if docx_path.exists():
        print(f"Existing: {docx_path}  ({docx_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    build_markdown()
    build_html()
    build_txt()
    build_docx_from_html()
