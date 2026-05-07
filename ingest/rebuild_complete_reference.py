#!/usr/bin/env python3
"""
Rebuilds FBF_Complete_Peptide_Reference.pdf with ALL compounds from batch 1 + batch 2.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from generate_flyers import (
    PEPTIDES, S, make_doc, sp, para, bullet, section, hr, orange_hr,
    dose_table, dark_background
)
from generate_flyers_batch2 import COMPOUNDS as BATCH2

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)

FBF_ORANGE   = colors.HexColor("#FF6A00")
FBF_DARK     = colors.HexColor("#0a0a0a")
FBF_CHARCOAL = colors.HexColor("#1c1c1c")
FBF_GRAY     = colors.HexColor("#2a2a2a")
FBF_LGRAY    = colors.HexColor("#888888")
FBF_WHITE    = colors.HexColor("#FFFFFF")


def all_compounds():
    """Merge batch1 + batch2 into uniform dicts."""
    merged = []
    for p in PEPTIDES:
        merged.append({
            "name":   p["name"],
            "full":   p["full_name"],
            "class":  p["class"],
            "tag0":   p["tags"][0],
            "what":   p["what"],
            "benefits": p["benefits"],
            "how":    p["how_it_works"],
            "doses":  p["doses"],
            "protocols": p["protocols"],
            "side_effects": p["side_effects"],
            "warning": p["warning"],
        })
    for c in BATCH2:
        merged.append({
            "name":   c["name"],
            "full":   c["full_name"],
            "class":  c["tags"][0],
            "tag0":   c["tags"][0],
            "what":   c["what"],
            "benefits": c["benefits"],
            "how":    c["how_it_works"],
            "doses":  c["doses"],
            "protocols": c["protocols"],
            "side_effects": c["side_effects"],
            "warning": c["warning"],
        })
    return merged


def build():
    all_c = all_compounds()
    doc, path = make_doc("FBF_Complete_Peptide_Reference.pdf")
    story = []

    # ── Cover ──────────────────────────────────────────────────────────────────
    story.append(sp(16))
    story.append(para("FORGED BY FREEDOM", "small"))
    story.append(para("COMPLETE PEPTIDE REFERENCE", "h1_big"))
    story.append(para(f"2025–2026 Edition  |  {len(all_c)} Compounds", "subtitle"))
    story.append(sp(6))
    story.append(orange_hr())
    story.append(para(
        "A comprehensive reference covering healing peptides, GH secretagogues, weight loss compounds, "
        "sexual health peptides, cognitive enhancers, mitochondrial agents, and next-generation metabolic "
        "research compounds. Dosing, protocols, mechanisms, side effects, and stacking strategies.",
        "body"))
    story.append(sp(10))

    # ── Quick Reference Table ──────────────────────────────────────────────────
    headers = [
        Paragraph("<b>Compound</b>", S["section"]),
        Paragraph("<b>Class / Primary Use</b>", S["section"]),
        Paragraph("<b>Key Benefit</b>", S["section"]),
    ]
    rows = [headers]
    for c in all_c:
        rows.append([
            Paragraph(c["name"], S["body"]),
            Paragraph(c["class"], S["small"]),
            Paragraph(c["benefits"][0][:80] if c["benefits"] else "", S["small"]),
        ])
    ref_t = Table(rows, colWidths=[1.5*inch, 2.0*inch, 3.7*inch])
    ref_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), FBF_ORANGE),
        ("TEXTCOLOR", (0,0), (-1,0), FBF_DARK),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [FBF_CHARCOAL, FBF_GRAY]),
        ("GRID", (0,0), (-1,-1), 0.5, FBF_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,1), (-1,-1), FBF_WHITE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(ref_t)
    story.append(sp(14))

    # ── Popular Stacks ─────────────────────────────────────────────────────────
    story.append(para("POPULAR STACKS", "h2"))
    story.append(orange_hr())
    stacks = [
        ("Injury Healing (Gold Standard)", "BPC-157 500 mcg SC + TB-500 2 mg SC — 2x/week for 4–6 weeks"),
        ("GH Optimization (Clean)", "CJC-1295 100 mcg + Ipamorelin 200 mcg SC before bed daily"),
        ("Maximum GH Pulse", "CJC-1295 100 mcg + Hexarelin 100 mcg — fasted 2x daily (6-week cycle max)"),
        ("Oral GH Stack", "MK-677 25 mg/night + CJC-1295/Ipamorelin on injection days"),
        ("Anti-Aging / Longevity", "Sermorelin 300 mcg bedtime + GHK-Cu 1 mg SC daily + MOTS-c 10 mg weekly"),
        ("Elite Body Recomp", "CJC-1295 + Ipamorelin + IGF-1 LR3 40–60 mcg post-workout + GH 2–3 IU"),
        ("Metabolic / Fat Loss", "5-Amino-1MQ 150 mg + MOTS-c 10 mg/wk + Tirzepatide or Retatrutide weekly"),
        ("Maximum Weight Loss", "CagriSema: Cagrilintide 2.4 mg/wk + Semaglutide 2.4 mg/wk"),
        ("Sexual Performance (Men)", "Tadalafil 5 mg daily + PT-141 1 mg SC 90 min before activity"),
        ("Sexual Performance (Women)", "PT-141 1.75 mg SC 45 min before + Testosterone cream 1 mg/day + Oxytocin 20 IU SC"),
        ("Cognitive / Nootropic", "Semax 400 mcg SC (AM) + Selank 250 mcg SC (PM) + MK-677 25 mg bedtime"),
        ("Mitochondrial / Endurance", "MOTS-c 10 mg/wk + SLU-PP-332 (research dose) + 5-Amino-1MQ 150 mg/day"),
        ("Tanning + Libido (MT-II)", "Melanotan II 0.5 mg SC 3x/wk + PT-141 0.5 mg SC for sexual function"),
        ("Anxiety + Focus Stack", "Selank 250 mcg (AM) + Semax 300 mcg (midday) + Tesofensine 0.5 mg (weight loss)"),
    ]
    for sname, sdesc in stacks:
        story.append(KeepTogether([
            para(f"<b>{sname}</b>", "body"),
            para(sdesc, "small"),
            sp(4),
        ]))
    story.append(sp(12))

    # ── Each Compound ──────────────────────────────────────────────────────────
    for c in all_c:
        story.append(KeepTogether([
            para(c["name"], "h1_big"),
            para(c["full"], "subtitle"),
            orange_hr(),
            para(c["what"]),
            sp(4),
        ]))

        story += section("KEY BENEFITS")
        for b in c["benefits"][:7]:
            story.append(bullet(b))

        story += section("HOW IT WORKS")
        story.append(para(c["how"]))
        story.append(sp(4))

        story += section("DOSING")
        story.append(dose_table(c["doses"]))
        story.append(sp(6))

        story += section("PROTOCOLS")
        for pr in c["protocols"][:4]:
            story.append(para(pr, "bullet"))

        story += section("SIDE EFFECTS")
        for se in c["side_effects"][:4]:
            story.append(bullet(se))

        story.append(sp(6))
        story.append(para(f"⚠  {c['warning']}", "warning"))
        story.append(sp(8))
        story.append(hr())
        story.append(sp(6))

    # ── Disclaimer ─────────────────────────────────────────────────────────────
    story.append(para(
        "MEDICAL DISCLAIMER: This guide is for educational purposes only. None of this constitutes "
        "medical advice. Peptides and research compounds described may not be FDA approved for the "
        "uses described. Always consult a qualified physician before using any compound. Verify supplier "
        "quality via third-party HPLC testing. Do not use any compound without understanding its full "
        "risk profile. forgedbyfreedom.com", "small"))

    doc.build(story, onFirstPage=dark_background, onLaterPages=dark_background)
    print(f"  ✅  {path.name}  ({len(all_c)} compounds)")


if __name__ == "__main__":
    print("Rebuilding complete peptide reference...")
    build()
