#!/usr/bin/env python3
"""
Exports all FBF cycle guide .txt files to formatted PDFs on the Desktop.
Output: ~/Desktop/FBF_Guides/
Includes: @CycleDesignGuide, @ForgedByFreedom, @PrecisionBloodwork
Excludes: master_transcript files
"""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Preformatted
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ── Brand ─────────────────────────────────────────────────────────────────────
FBF_ORANGE   = colors.HexColor("#FF6A00")
FBF_DARK     = colors.HexColor("#0a0a0a")
FBF_CHARCOAL = colors.HexColor("#1c1c1c")
FBF_GRAY     = colors.HexColor("#2a2a2a")
FBF_LGRAY    = colors.HexColor("#888888")
FBF_WHITE    = colors.HexColor("#FFFFFF")

CHANNELS_DIR = Path(__file__).parent / "channels"
DESKTOP_OUT  = Path.home() / "Desktop" / "FBF_Guides"
DESKTOP_OUT.mkdir(parents=True, exist_ok=True)

SOURCE_CHANNELS = ["@CycleDesignGuide", "@ForgedByFreedom", "@PrecisionBloodwork"]

STYLES = {
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18,
        textColor=FBF_ORANGE, spaceAfter=6, leading=22),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13,
        textColor=FBF_ORANGE, spaceBefore=14, spaceAfter=4, leading=16),
    "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11,
        textColor=FBF_WHITE, spaceBefore=10, spaceAfter=3, leading=14),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10,
        textColor=FBF_WHITE, leading=15, spaceAfter=4),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=10,
        textColor=FBF_WHITE, leading=15, leftIndent=16, spaceAfter=2,
        bulletIndent=6, bulletText="•"),
    "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8,
        textColor=FBF_LGRAY, leading=11, spaceAfter=2),
    "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=9,
        textColor=FBF_LGRAY, leading=12),
}


def dark_background(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFillColor(FBF_DARK)
    canvas_obj.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
    canvas_obj.setFillColor(FBF_ORANGE)
    canvas_obj.rect(0, letter[1] - 5, letter[0], 5, fill=1, stroke=0)
    canvas_obj.setFillColor(FBF_CHARCOAL)
    canvas_obj.rect(0, 0, letter[0], 32, fill=1, stroke=0)
    canvas_obj.setFillColor(FBF_LGRAY)
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.drawCentredString(letter[0] / 2, 12,
        "FORGED BY FREEDOM  |  forgedbyfreedom.com  |  Educational Use Only — Not Medical Advice")
    canvas_obj.restoreState()


def safe_para(text, style_key="body"):
    """Sanitize text for ReportLab — escape XML special chars."""
    text = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    return Paragraph(text, STYLES[style_key])


def parse_txt_to_story(raw_text: str, title: str, source_channel: str) -> list:
    """Convert plain-text guide content into styled ReportLab flowables."""
    lines = raw_text.splitlines()
    story = []

    # Strip the header block (Source/Speaker/URL/=== lines)
    content_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("=" * 20):
            content_start = i + 1
            break
    lines = lines[content_start:]

    # Title block
    story.append(Spacer(1, 8))
    story.append(safe_para("FORGED BY FREEDOM", "meta"))
    story.append(safe_para(title, "h1"))
    story.append(safe_para(source_channel, "meta"))
    story.append(HRFlowable(width="100%", thickness=2, color=FBF_ORANGE, spaceAfter=10))

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 4))
            i += 1
            continue

        # Detect heading levels by ALL CAPS sections or markdown-style headers
        if stripped.startswith("## "):
            story.append(safe_para(stripped[3:], "h2"))
            story.append(HRFlowable(width="100%", thickness=1, color=FBF_GRAY, spaceAfter=4))
        elif stripped.startswith("# "):
            story.append(safe_para(stripped[2:], "h1"))
            story.append(HRFlowable(width="100%", thickness=2, color=FBF_ORANGE, spaceAfter=6))
        elif stripped.startswith("### "):
            story.append(safe_para(stripped[4:], "h3"))
        elif stripped.startswith("- ") or stripped.startswith("• "):
            story.append(safe_para(stripped[2:], "bullet"))
        elif stripped.startswith("* "):
            story.append(safe_para(stripped[2:], "bullet"))
        elif (stripped.isupper() and len(stripped) > 6 and len(stripped) < 80
              and not stripped.startswith("HTTP")):
            # ALL CAPS line = treat as section header
            story.append(Spacer(1, 6))
            story.append(safe_para(stripped, "h2"))
            story.append(HRFlowable(width="100%", thickness=1, color=FBF_GRAY, spaceAfter=4))
        elif stripped.startswith("---") or stripped.startswith("==="):
            story.append(HRFlowable(width="100%", thickness=1, color=FBF_GRAY,
                                    spaceAfter=4, spaceBefore=4))
        else:
            story.append(safe_para(stripped, "body"))

        i += 1

    return story


def safe_filename(name: str) -> str:
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '[', ']']:
        name = name.replace(ch, '_')
    return name.strip()


def extract_title(txt_file: Path, raw: str) -> str:
    """Extract title from file header or filename."""
    for line in raw.splitlines()[:10]:
        for prefix in ("Title:", "Compound:"):
            if line.startswith(prefix):
                return line[len(prefix):].strip()
    # Fall back to filename without the [ID] suffix
    name = txt_file.stem
    import re
    name = re.sub(r'\s*\[.*?\]\s*$', '', name).strip()
    return name


def convert_file(txt_path: Path, channel_name: str) -> Path:
    raw = txt_path.read_text(encoding="utf-8", errors="replace")
    title = extract_title(txt_path, raw)
    out_name = safe_filename(title) + ".pdf"
    # Prefix with channel subfolder
    out_dir = DESKTOP_OUT / channel_name.lstrip("@")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name

    story = parse_txt_to_story(raw, title, channel_name)

    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.65*inch, bottomMargin=0.5*inch)
    doc.build(story, onFirstPage=dark_background, onLaterPages=dark_background)
    return out_path


def main():
    print("=" * 60)
    print("  FBF GUIDE → PDF EXPORTER")
    print(f"  Output: {DESKTOP_OUT}")
    print("=" * 60)

    total_ok = total_fail = 0

    for channel in SOURCE_CHANNELS:
        ch_dir = CHANNELS_DIR / channel
        if not ch_dir.exists():
            print(f"\n⚠  Channel dir not found: {ch_dir}")
            continue

        txt_files = [
            f for f in sorted(ch_dir.glob("*.txt"))
            if not f.name.startswith("master_transcript")
            and not f.name.startswith(".")
        ]

        print(f"\n📂 {channel}  ({len(txt_files)} files)")
        for f in txt_files:
            try:
                out = convert_file(f, channel)
                print(f"  ✅  {out.name}")
                total_ok += 1
            except Exception as e:
                print(f"  ❌  {f.name} — {e}")
                total_fail += 1

    # Also copy the peptide flyers and women's health guide
    flyers_dir = Path(__file__).parent.parent / "flyers"
    if flyers_dir.exists():
        import shutil
        dest_flyers = DESKTOP_OUT / "Peptide_Flyers"
        dest_flyers.mkdir(parents=True, exist_ok=True)
        for pdf in sorted(flyers_dir.glob("*.pdf")):
            shutil.copy2(pdf, dest_flyers / pdf.name)
            print(f"  📋  Copied flyer: {pdf.name}")
        print(f"\n📄 Peptide flyers copied to {dest_flyers}")

    print(f"\n{'='*60}")
    print(f"✅ Done — {total_ok} PDFs exported, {total_fail} failed")
    print(f"   {DESKTOP_OUT}")


if __name__ == "__main__":
    main()
