#!/usr/bin/env python3
"""
FBF Branded PDF Flyer Generator
Produces individual peptide flyers + all-in-one + women's health guide.
Output: /Users/bryanantonelli/forged-by-freedom/flyers/
"""

import os
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

# ── FBF Brand Colors ─────────────────────────────────────────────────────────
FBF_ORANGE   = colors.HexColor("#FF6A00")
FBF_DARK     = colors.HexColor("#0a0a0a")
FBF_CHARCOAL = colors.HexColor("#1c1c1c")
FBF_GRAY     = colors.HexColor("#2a2a2a")
FBF_LGRAY    = colors.HexColor("#888888")
FBF_WHITE    = colors.HexColor("#FFFFFF")
FBF_GREEN    = colors.HexColor("#22c55e")
FBF_GOLD     = colors.HexColor("#f59e0b")

OUTPUT_DIR = Path(__file__).parent.parent / "flyers"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Styles ───────────────────────────────────────────────────────────────────
def make_styles():
    return {
        "title": ParagraphStyle("title",
            fontName="Helvetica-Bold", fontSize=28, textColor=FBF_ORANGE,
            spaceAfter=4, leading=32, alignment=TA_LEFT),
        "subtitle": ParagraphStyle("subtitle",
            fontName="Helvetica", fontSize=13, textColor=FBF_LGRAY,
            spaceAfter=12, leading=16, alignment=TA_LEFT),
        "section": ParagraphStyle("section",
            fontName="Helvetica-Bold", fontSize=13, textColor=FBF_ORANGE,
            spaceBefore=14, spaceAfter=4, leading=16),
        "body": ParagraphStyle("body",
            fontName="Helvetica", fontSize=10, textColor=FBF_WHITE,
            leading=15, spaceAfter=4),
        "bullet": ParagraphStyle("bullet",
            fontName="Helvetica", fontSize=10, textColor=FBF_WHITE,
            leading=15, leftIndent=14, spaceAfter=3,
            bulletIndent=4, bulletText="•"),
        "warning": ParagraphStyle("warning",
            fontName="Helvetica-BoldOblique", fontSize=9, textColor=FBF_GOLD,
            leading=13, spaceBefore=6),
        "footer_txt": ParagraphStyle("footer_txt",
            fontName="Helvetica", fontSize=8, textColor=FBF_LGRAY,
            alignment=TA_CENTER),
        "tag": ParagraphStyle("tag",
            fontName="Helvetica-Bold", fontSize=9, textColor=FBF_DARK,
            alignment=TA_CENTER),
        "h1_big": ParagraphStyle("h1_big",
            fontName="Helvetica-Bold", fontSize=22, textColor=FBF_ORANGE,
            spaceBefore=18, spaceAfter=4, leading=26, alignment=TA_LEFT),
        "h2": ParagraphStyle("h2",
            fontName="Helvetica-Bold", fontSize=16, textColor=FBF_WHITE,
            spaceBefore=14, spaceAfter=6, leading=20),
        "small": ParagraphStyle("small",
            fontName="Helvetica", fontSize=9, textColor=FBF_LGRAY, leading=12),
        "dose_val": ParagraphStyle("dose_val",
            fontName="Helvetica-Bold", fontSize=11, textColor=FBF_GREEN,
            leading=14, alignment=TA_CENTER),
        "dose_lbl": ParagraphStyle("dose_lbl",
            fontName="Helvetica", fontSize=8, textColor=FBF_LGRAY,
            leading=11, alignment=TA_CENTER),
    }

S = make_styles()

# ── Page Background ──────────────────────────────────────────────────────────
def dark_background(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFillColor(FBF_DARK)
    canvas_obj.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
    # Orange accent bar at top
    canvas_obj.setFillColor(FBF_ORANGE)
    canvas_obj.rect(0, letter[1] - 6, letter[0], 6, fill=1, stroke=0)
    # Footer bar
    canvas_obj.setFillColor(FBF_CHARCOAL)
    canvas_obj.rect(0, 0, letter[0], 36, fill=1, stroke=0)
    canvas_obj.setFillColor(FBF_LGRAY)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawCentredString(letter[0]/2, 14,
        "FORGED BY FREEDOM  |  FBF AI Coach  |  forgedbyfreedom.com  |  Educational Use Only — Not Medical Advice")
    canvas_obj.restoreState()

def make_doc(filename):
    path = OUTPUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path), pagesize=letter,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.7*inch, bottomMargin=0.6*inch,
    )
    return doc, path

# ── Helper Flowables ─────────────────────────────────────────────────────────
def hr():
    return HRFlowable(width="100%", thickness=1, color=FBF_GRAY, spaceAfter=6, spaceBefore=6)

def orange_hr():
    return HRFlowable(width="100%", thickness=2, color=FBF_ORANGE, spaceAfter=8, spaceBefore=2)

def sp(h=6):
    return Spacer(1, h)

def para(text, style="body"):
    return Paragraph(text, S[style])

def bullet(text):
    return Paragraph(text, S["bullet"])

def section(text):
    return [para(text, "section"), HRFlowable(width="100%", thickness=1, color=FBF_GRAY, spaceAfter=5)]

def dose_table(rows):
    """rows = list of (label, value) tuples"""
    data = [[Paragraph(v, S["dose_val"]) for _,v in rows],
            [Paragraph(l, S["dose_lbl"]) for l,_ in rows]]
    col_w = (7.2*inch) / len(rows)
    t = Table(data, colWidths=[col_w]*len(rows))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), FBF_CHARCOAL),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [FBF_CHARCOAL, FBF_GRAY]),
        ("BOX", (0,0), (-1,-1), 1, FBF_ORANGE),
        ("INNERGRID", (0,0), (-1,-1), 0.5, FBF_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t

def tag_table(tags, colors_list=None):
    """Renders colored tag pills in a row."""
    if colors_list is None:
        colors_list = [FBF_ORANGE] * len(tags)
    data = [[Paragraph(f"<b>{t}</b>", S["tag"]) for t in tags]]
    col_w = (7.2*inch) / len(tags)
    t = Table(data, colWidths=[col_w]*len(tags))
    style_cmds = [
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
    ]
    for i, c in enumerate(colors_list):
        style_cmds.append(("BACKGROUND", (i,0), (i,0), c))
    t.setStyle(TableStyle(style_cmds))
    return t

# ══════════════════════════════════════════════════════════════════════════════
# PEPTIDE DATA
# ══════════════════════════════════════════════════════════════════════════════
PEPTIDES = [
    {
        "name": "BPC-157",
        "full_name": "Body Protection Compound 157",
        "class": "Healing Peptide",
        "tags": ["HEALING", "GUT HEALTH", "TENDONS", "JOINTS", "ANTI-INFLAMMATORY"],
        "what": (
            "BPC-157 is a synthetic pentadecapeptide (15 amino acids) derived from a protective "
            "protein found in human gastric juice. It has profound tissue-healing properties across "
            "multiple organ systems — from tendons and ligaments to gut mucosa and brain."
        ),
        "benefits": [
            "Accelerates healing of tendons, ligaments, and muscle tears",
            "Heals leaky gut, IBS, ulcers, and intestinal damage (including NSAID-induced)",
            "Reduces systemic inflammation — protective for joints and connective tissue",
            "Promotes angiogenesis (new blood vessel formation) to injured areas",
            "Neuroprotective — improves recovery from traumatic brain injury",
            "Counteracts corticosteroid-related tendon damage",
            "Reduces pain and swelling at injury sites within days",
            "Supports dopamine and serotonin systems — mood stabilizing effects",
            "Protects against alcohol and NSAID-induced stomach damage",
        ],
        "how_it_works": (
            "BPC-157 upregulates growth hormone receptor expression in injured tissue, "
            "promotes VEGF (vascular endothelial growth factor) synthesis, and modulates the "
            "nitric oxide system. It activates the FAK-paxillin pathway for tendon healing and "
            "influences the gut-brain axis via vagus nerve interaction."
        ),
        "doses": [
            ("250–500 mcg", "Injection (SC/IM)"),
            ("500 mcg–1 mg", "Oral (gut focus)"),
            ("1–2x/day", "Frequency"),
            ("4–12 weeks", "Cycle Length"),
        ],
        "protocols": [
            "<b>Injury Healing:</b> 500 mcg SC/IM near injury site, 1–2x daily for 4–8 weeks.",
            "<b>Gut Healing:</b> 500 mcg–1 mg oral (capsule or dissolve in water), taken fasted, 2x daily.",
            "<b>Systemic:</b> 250–500 mcg SC abdomen, 1x daily maintenance.",
            "<b>Stack Option:</b> BPC-157 + TB-500 for systemic + local healing synergy.",
        ],
        "side_effects": [
            "Generally very well tolerated — minimal reported side effects",
            "Injection site irritation (mild, transient)",
            "Fatigue or drowsiness at high doses (rare)",
            "No significant endocrine disruption",
        ],
        "warning": "Not FDA approved. Research use only. Source from reputable peptide suppliers and verify purity via HPLC testing.",
        "storage": "Lyophilized powder: room temp. Reconstituted: refrigerate, use within 30 days.",
    },
    {
        "name": "TB-500",
        "full_name": "Thymosin Beta-4 Fragment",
        "class": "Healing / Recovery Peptide",
        "tags": ["SYSTEMIC HEALING", "INFLAMMATION", "FLEXIBILITY", "ENDURANCE", "RECOVERY"],
        "what": (
            "TB-500 is a synthetic fragment of Thymosin Beta-4 (Tβ4), a naturally occurring "
            "44-amino-acid peptide found in virtually every cell in the body. It promotes systemic "
            "healing, reduces inflammation, and improves mobility — particularly in connective tissue."
        ),
        "benefits": [
            "Systemic healing — works on muscles, tendons, ligaments, skin, eyes",
            "Significant reduction in inflammation and pain",
            "Improves flexibility and range of motion in injured tissue",
            "Promotes cardiomyocyte migration and cardiac repair after injury",
            "Accelerates wound healing and promotes skin repair",
            "Stimulates stem cell differentiation and migration",
            "Reported improvements in hair growth and re-pigmentation",
            "Neuroprotective effects — recovery from stroke or TBI",
            "Reduces adhesions and scar tissue formation",
        ],
        "how_it_works": (
            "TB-500 works primarily by binding to actin — a protein critical for cell structure "
            "and movement. This binding promotes cell migration and proliferation in injured tissue. "
            "It upregulates actin genes in healing cells and modulates inflammatory cytokines, "
            "reducing TNF-alpha and IL-6 while promoting anti-inflammatory pathways."
        ),
        "doses": [
            ("2–2.5 mg", "Loading (2x/wk)"),
            ("1–1.5 mg", "Maintenance (1x/wk)"),
            ("4–6 weeks", "Loading Phase"),
            ("Monthly", "Ongoing Maintenance"),
        ],
        "protocols": [
            "<b>Loading Phase:</b> 2–2.5 mg SC/IM 2x per week for 4–6 weeks.",
            "<b>Maintenance:</b> 1–1.5 mg once weekly ongoing, or monthly once healed.",
            "<b>Acute Injury:</b> 2.5 mg 2x/week for 2–3 weeks, then reassess.",
            "<b>Stack:</b> TB-500 + BPC-157 = the gold standard injury healing stack.",
        ],
        "side_effects": [
            "Generally very well tolerated at therapeutic doses",
            "Fatigue or lethargy (common early, usually transient)",
            "Injection site reactions (mild)",
            "Theoretical concern: may promote cancer cell migration (not shown clinically at peptide doses)",
            "Headache (rare)",
        ],
        "warning": "Not FDA approved. Banned by WADA for competitive athletes. Research use only.",
        "storage": "Lyophilized: room temp/refrigerator. Reconstituted: refrigerate, use within 30 days.",
    },
    {
        "name": "CJC-1295 + Ipamorelin",
        "full_name": "CJC-1295 / Ipamorelin Stack",
        "class": "GH Secretagogue Stack",
        "tags": ["GH RELEASE", "FAT LOSS", "MUSCLE GAIN", "SLEEP", "ANTI-AGING"],
        "what": (
            "CJC-1295 (a GHRH analogue) + Ipamorelin (a GHRP/ghrelin mimetic) is the most "
            "popular GH secretagogue stack in use today. Together they produce synergistic "
            "GH pulse amplification that closely mimics the body's natural pulsatile GH release — "
            "without the cortisol and prolactin spikes of older GHRPs."
        ),
        "benefits": [
            "Significantly increased GH and IGF-1 levels",
            "Accelerated fat loss — especially visceral and subcutaneous",
            "Improved muscle recovery, body composition, and lean mass over time",
            "Dramatically improved deep sleep quality (GH-wave amplification during sleep)",
            "Anti-aging effects: improved skin elasticity, collagen production",
            "Increased bone density over long-term use",
            "Joint and connective tissue support via IGF-1 upregulation",
            "Improved metabolic rate and insulin sensitivity",
            "Very clean — Ipamorelin does not spike cortisol or prolactin like GHRP-6/Hexarelin",
        ],
        "how_it_works": (
            "CJC-1295 (DAC version) has a half-life of ~8 days, providing sustained GHRH signal. "
            "Ipamorelin acts on ghrelin receptors to create GH pulses. Together, they simultaneously "
            "amplify GH pulse amplitude (CJC) and frequency (Ipamorelin), mimicking youth-level "
            "GH secretion without suppressing the natural HPG axis."
        ),
        "doses": [
            ("100 mcg", "CJC-1295 (no DAC)"),
            ("100–200 mcg", "Ipamorelin"),
            ("Bedtime", "Timing (optimal)"),
            ("3–6 months", "Cycle Length"),
        ],
        "protocols": [
            "<b>Standard:</b> CJC-1295 100 mcg + Ipamorelin 100–200 mcg SC, before bed (fasted 2 hrs).",
            "<b>CJC-DAC version:</b> 1–2 mg CJC-DAC 1–2x/week + daily Ipamorelin 100–200 mcg.",
            "<b>2x Daily:</b> Add a morning dose pre-workout for accelerated body recomp.",
            "<b>Anti-Aging:</b> 5 days on / 2 days off cycling prevents receptor desensitization.",
        ],
        "side_effects": [
            "Water retention (mild) — especially first few weeks",
            "Tingling or numbness in hands (carpal tunnel-like, dose dependent)",
            "Temporary insulin sensitivity reduction (monitor glucose)",
            "Mild fatigue within 30–60 min post-injection (expected GH effect)",
            "Ipamorelin: slight hunger increase (much less than GHRP-6)",
        ],
        "warning": "Long-term use may cause pituitary desensitization. Cycle with breaks. Monitor IGF-1 levels.",
        "storage": "Lyophilized: room temp. Reconstituted in BW: refrigerate, use within 30 days.",
    },
    {
        "name": "Sermorelin",
        "full_name": "Sermorelin Acetate (GHRH 1-29)",
        "class": "GH Secretagogue",
        "tags": ["GH RELEASE", "ANTI-AGING", "SLEEP", "TRT COMPLEMENT", "LOW RISK"],
        "what": (
            "Sermorelin is a synthetic analogue of the first 29 amino acids of endogenous "
            "GHRH (growth hormone releasing hormone). It stimulates the pituitary to produce "
            "and release natural GH — making it the most conservative and 'natural' approach "
            "to GH optimization. Popular in TRT clinics and anti-aging medicine."
        ),
        "benefits": [
            "Stimulates pituitary GH release without suppressing natural axis",
            "Improves body composition over 3–6 months (fat loss, lean mass increase)",
            "Significantly improves sleep quality and deep sleep architecture",
            "Increases energy, vitality, and sense of well-being",
            "Improves skin quality and collagen density",
            "Supports bone density long-term",
            "Complementary to TRT — does not affect LH/FSH like exogenous GH",
            "Less risk of GH-related side effects vs. exogenous HGH",
            "Relatively affordable compared to pharmaceutical HGH",
        ],
        "how_it_works": (
            "Sermorelin binds to GHRH receptors on somatotroph cells in the anterior pituitary, "
            "stimulating natural GH synthesis and pulsatile secretion. Unlike exogenous GH, "
            "pituitary output is still regulated by somatostatin feedback — maintaining physiologic "
            "balance and reducing risks of excess GH."
        ),
        "doses": [
            ("200–500 mcg", "Dose per injection"),
            ("Bedtime", "Timing"),
            ("Daily", "Frequency"),
            ("3–6 months", "Cycle"),
        ],
        "protocols": [
            "<b>Standard:</b> 200–500 mcg SC before bed, fasted, daily.",
            "<b>Anti-Aging Clinic Protocol:</b> Often prescribed at 300 mcg/day with annual IGF-1 monitoring.",
            "<b>Stack:</b> Sermorelin + Ipamorelin for GHRH + GHRP dual stimulation.",
            "<b>Cycling:</b> 5 days on / 2 days off to maintain receptor sensitivity.",
        ],
        "side_effects": [
            "Injection site reactions (transient, mild)",
            "Flushing, headache (rare at therapeutic doses)",
            "Water retention (less than exogenous HGH)",
            "Tingling (carpal tunnel-like at higher doses)",
        ],
        "warning": "Available via prescription through anti-aging/TRT clinics. Compounded versions vary in quality.",
        "storage": "Refrigerate reconstituted solution. Use within 30 days. Protect from light.",
    },
    {
        "name": "GHRP-6",
        "full_name": "Growth Hormone Releasing Peptide 6",
        "class": "GH Secretagogue (GHRP)",
        "tags": ["GH RELEASE", "APPETITE", "MUSCLE GROWTH", "HEALING", "CORTISOL CAUTION"],
        "what": (
            "GHRP-6 is a synthetic hexapeptide that stimulates GH release by acting on the ghrelin "
            "receptor. It produces large GH pulses and is known for its powerful appetite-stimulating "
            "effect — making it particularly useful in bulking or recovery phases where high caloric "
            "intake is needed. One of the original GHRPs."
        ),
        "benefits": [
            "Potent GH pulse stimulation — one of the strongest GHRPs",
            "Massive appetite increase (pro for bulking, con for cutting)",
            "Accelerated muscle growth when combined with caloric surplus",
            "Improved recovery — tissue healing and reduced DOMS",
            "Cardioprotective effects at therapeutic doses",
            "Anti-inflammatory via GH-mediated IGF-1 upregulation",
            "Improved sleep depth at bedtime dosing",
        ],
        "how_it_works": (
            "GHRP-6 acts as a synthetic ghrelin agonist, binding to GH secretagogue receptor (GHSR-1a) "
            "in the hypothalamus and pituitary. This triggers somatotroph cells to release stored GH in "
            "pulses. It also amplifies GHRH-mediated GH release when stacked with CJC-1295."
        ),
        "doses": [
            ("100–300 mcg", "Dose"),
            ("2–3x/day", "Frequency"),
            ("Fasted", "Timing"),
            ("4–12 weeks", "Cycle"),
        ],
        "protocols": [
            "<b>Bulking:</b> 200–300 mcg 3x daily (morning, pre-workout, bedtime) — embrace the hunger.",
            "<b>GH Optimization:</b> 100–200 mcg with CJC-1295 2x daily.",
            "<b>Bedtime Protocol:</b> 200 mcg before bed for sleep + GH pulse.",
            "<b>Note:</b> Eat 15–20 min after injection to maximize GH pulse before insulin rise.",
        ],
        "side_effects": [
            "Significant appetite increase (ghrelin effect — can be extreme)",
            "Cortisol and prolactin increase (unlike Ipamorelin) — monitor on long cycles",
            "Water retention",
            "Fatigue post-injection (expected GH pulse effect)",
            "Tingling, numbness (carpal tunnel-like at high doses)",
        ],
        "warning": "Cortisol and prolactin elevation with frequent dosing — prefer Ipamorelin for cutting or long-term use.",
        "storage": "Lyophilized: room temp. Reconstituted: refrigerate, use within 30 days.",
    },
    {
        "name": "Hexarelin",
        "full_name": "Hexarelin (Examorelin)",
        "class": "GH Secretagogue (GHRP)",
        "tags": ["GH RELEASE", "CARDIOPROTECTIVE", "STRENGTH", "POTENT", "DESENSITIZATION"],
        "what": (
            "Hexarelin is among the most potent synthetic GHRPs available, producing the largest "
            "GH pulses of all peptides in its class. It has unique cardioprotective properties "
            "independent of GH release, acting directly on cardiac GHS-R receptors. Requires "
            "careful cycling to prevent receptor desensitization."
        ),
        "benefits": [
            "Strongest GH pulse stimulation of all GHRPs",
            "Cardioprotective — directly improves myocardial function and reduces ischemia",
            "Accelerated fat loss via potent GH stimulation",
            "Muscle growth and enhanced recovery",
            "Increases IGF-1 significantly",
            "Neuroprotective properties",
            "May improve cardiac output in compromised hearts",
        ],
        "how_it_works": (
            "Hexarelin is a synthetic GHRP-6 analogue with modifications that increase receptor "
            "affinity. It stimulates GH release via GHSR-1a and also acts directly on cardiac "
            "receptors (CD36) — explaining its GH-independent cardioprotective effects. Somatostatin "
            "is the primary limiting factor on its GH pulse size."
        ),
        "doses": [
            ("100–200 mcg", "Dose"),
            ("2–3x/day", "Frequency"),
            ("Fasted", "Timing"),
            ("4–6 weeks max", "Cycle"),
        ],
        "protocols": [
            "<b>Standard:</b> 100–200 mcg SC 2–3x daily, fasted.",
            "<b>Cardiac Focus:</b> 1–2 mcg/kg 2x daily.",
            "<b>Cycle:</b> Max 6 weeks, then 4–6 week break to restore receptor sensitivity.",
            "<b>Stack:</b> Hexarelin + CJC-1295 for maximum GH amplification.",
        ],
        "side_effects": [
            "Rapid desensitization of GH release receptors (limits cycle length)",
            "Cortisol and prolactin elevation",
            "Water retention",
            "Increased hunger (less than GHRP-6)",
            "Fatigue post-injection",
        ],
        "warning": "Most potent GHRP — shorter cycles mandatory. Cortisol and prolactin monitoring recommended on extended use.",
        "storage": "Lyophilized: room temp. Reconstituted: refrigerate, use within 30 days.",
    },
    {
        "name": "IGF-1 LR3",
        "full_name": "Insulin-Like Growth Factor 1 Long Arg3",
        "class": "Growth Factor",
        "tags": ["MUSCLE GROWTH", "FAT LOSS", "NUTRIENT PARTITIONING", "ADVANCED", "HYPOGLYCEMIA RISK"],
        "what": (
            "IGF-1 LR3 is a modified form of Insulin-Like Growth Factor 1 with a 13-amino-acid "
            "extension that reduces binding to IGFBPs — increasing its half-life from minutes "
            "(native IGF-1) to approximately 20–30 hours. It promotes muscle cell hyperplasia "
            "(new cell formation), not just hypertrophy — making it uniquely anabolic."
        ),
        "benefits": [
            "Muscle hyperplasia — stimulates satellite cell proliferation and new muscle fiber formation",
            "Powerful nutrient partitioning — shuttles nutrients into muscle, away from fat",
            "Significant fat loss via IGF-1's lipolytic action",
            "Enhanced recovery and protein synthesis",
            "Synergistic with androgens and GH peptides",
            "Improved glucose uptake into muscle tissue",
            "Cognitive benefits — neuroprotective and neurogenic effects",
        ],
        "how_it_works": (
            "IGF-1 LR3 binds IGF-1 receptors (IGF-1R) on muscle cells, activating PI3K/Akt/mTOR "
            "pathways for protein synthesis and satellite cell activation. The LR3 modification "
            "reduces IGF-BP binding by ~1000x, dramatically extending activity. It acts both "
            "systemically and locally at injection sites."
        ),
        "doses": [
            ("20–100 mcg", "Daily Dose"),
            ("Post-workout", "Timing"),
            ("Daily or ED", "Frequency"),
            ("4–6 weeks", "Cycle Max"),
        ],
        "protocols": [
            "<b>Beginner:</b> 20–40 mcg IM post-workout, target worked muscles.",
            "<b>Intermediate:</b> 60–80 mcg post-workout, rotate injection sites.",
            "<b>Advanced:</b> 80–100 mcg/day split into 2 injections.",
            "<b>Cycle:</b> 4–6 weeks max — receptor downregulation occurs with extended use.",
            "<b>Stack:</b> IGF-1 LR3 + GH peptides + androgens for elite body recomp.",
        ],
        "side_effects": [
            "Hypoglycemia — most common risk; eat within 15–20 min of injection",
            "Jaw and organ growth concerns at sustained supraphysiologic doses",
            "Theoretical long-term cancer promotion risk (IGF-1 is mitogenic)",
            "Muscle cramps (electrolyte shift)",
            "Tingling, numbness (dose dependent)",
        ],
        "warning": "Advanced compound. Hypoglycemia is a real risk — always have fast carbs on hand post-injection.",
        "storage": "Lyophilized: refrigerate. Reconstituted in AA: refrigerate, use within 21 days.",
    },
    {
        "name": "PT-141",
        "full_name": "Bremelanotide (PT-141)",
        "class": "Sexual Function Peptide",
        "tags": ["LIBIDO", "SEXUAL FUNCTION", "ERECTION", "FEMALE DESIRE", "FDA APPROVED (VYLEESI)"],
        "what": (
            "PT-141 (Bremelanotide) is a synthetic melanocortin peptide that activates MC3R and MC4R "
            "receptors in the brain to drive sexual desire and arousal at the neurological level — "
            "independent of the vascular mechanism targeted by ED drugs like Viagra. FDA approved "
            "(as Vyleesi) for hypoactive sexual desire disorder (HSDD) in women. Highly effective "
            "in men and women with low libido regardless of cause."
        ),
        "benefits": [
            "Dramatically increases sexual desire, motivation, and libido in men and women",
            "Promotes erections in men via central nervous system pathways",
            "Effective when PDE5 inhibitors fail or are insufficient alone",
            "Enhances arousal, sensitivity, and sexual satisfaction in women",
            "Works centrally — addresses psychological/neurological drivers of low libido",
            "Shown effective for HSDD, post-menopause low desire, hormone-related low libido",
            "Spontaneous — no need to time use around sexual activity (unlike PDE5i)",
        ],
        "how_it_works": (
            "PT-141 acts on melanocortin receptors (MC3R, MC4R) in the hypothalamus, directly "
            "activating the brain's sexual arousal circuits. Unlike PDE5 inhibitors which work "
            "peripherally on blood vessels, PT-141 works at the CNS level — increasing desire "
            "and arousal rather than just facilitating erection mechanics."
        ),
        "doses": [
            ("0.5–2 mg", "Men (SC)"),
            ("1.75 mg", "Women (FDA dose)"),
            ("1–2 hrs prior", "Timing"),
            ("As needed", "Frequency"),
        ],
        "protocols": [
            "<b>Men:</b> Start at 0.5–1 mg SC 1–2 hrs before activity. Increase to 2 mg if needed.",
            "<b>Women:</b> 1.75 mg SC 45 min before activity (FDA-approved Vyleesi dose).",
            "<b>Stack (Men):</b> PT-141 + low-dose Tadalafil (5 mg daily) for central + peripheral coverage.",
            "<b>Max use:</b> No more than 8 uses per month to avoid receptor desensitization.",
        ],
        "side_effects": [
            "Nausea (most common — take with anti-nausea OTC if needed)",
            "Flushing and transient blood pressure changes",
            "Spontaneous erections in men (dose dependent)",
            "Headache",
            "Hyperpigmentation with frequent long-term use (melanocortin effect)",
        ],
        "warning": "May cause transient blood pressure elevation. Use with caution if cardiovascular disease present.",
        "storage": "Refrigerate reconstituted solution. Use within 30 days. Vyleesi autoinjector: room temp.",
    },
    {
        "name": "Melanotan II",
        "full_name": "Melanotan II (MT-II)",
        "class": "Melanocortin Peptide",
        "tags": ["TANNING", "LIBIDO", "FAT LOSS", "APPETITE SUPPRESSION", "SPONTANEOUS ERECTIONS"],
        "what": (
            "Melanotan II is a synthetic cyclic analogue of alpha-MSH (melanocyte-stimulating hormone). "
            "It activates multiple melanocortin receptors: MC1R (skin pigmentation), MC3R/MC4R "
            "(libido, appetite, erection), and MC5R (exocrine glands). Originally developed as a "
            "sunless tanning drug, it became popular for its libido-enhancing and appetite-suppressing "
            "side effects."
        ),
        "benefits": [
            "Accelerated skin tanning — deeper tan with less UV exposure required",
            "Significantly increased libido and sexual arousal in men and women",
            "Spontaneous erections in men (even without sexual stimulation at higher doses)",
            "Appetite suppression — meaningful fat loss aid",
            "Stimulates lipolysis via MC4R activation",
            "Enhanced sensitivity and arousal in women",
            "UV-protective pigmentation reduces sunburn risk",
        ],
        "how_it_works": (
            "MT-II is a cyclic peptide analogue that binds MC1R, MC3R, MC4R, and MC5R with high "
            "affinity. MC1R activation on melanocytes stimulates eumelanin (dark pigment) production. "
            "MC4R activation in the hypothalamus drives sexual arousal, appetite suppression, "
            "and erection via neurological pathways."
        ),
        "doses": [
            ("0.25–0.5 mg", "Starting Dose"),
            ("0.5–1 mg", "Maintenance"),
            ("Before sun/bed", "Timing"),
            ("Load then taper", "Protocol"),
        ],
        "protocols": [
            "<b>Loading:</b> 0.25 mg SC daily, gradually increase by 0.25 mg every 2–3 days to 0.5–1 mg.",
            "<b>Tanning maintenance:</b> 0.5 mg 2–3x/week with UV exposure.",
            "<b>Libido:</b> 0.5–1 mg SC 1–2 hrs before sexual activity.",
            "<b>Tip:</b> Start low — nausea is common at higher doses and diminishes with frequency.",
        ],
        "side_effects": [
            "Nausea and facial flushing (very common, especially on loading doses)",
            "Spontaneous erections (unwanted in inappropriate situations)",
            "Darkening of existing moles — monitor carefully",
            "Appetite suppression (can be profound)",
            "Fatigue within 30–60 min post-injection",
            "Pigmentation of skin (irreversible — lightens slowly when stopped)",
        ],
        "warning": "Mole darkening and new nevus formation reported — dermatologist monitoring recommended with regular use. Not FDA approved.",
        "storage": "Lyophilized: room temp. Reconstituted: refrigerate, use within 30 days. Light sensitive.",
    },
    {
        "name": "Retatrutide",
        "full_name": "Retatrutide (GLP-1/GIP/GCG Triple Agonist)",
        "class": "GLP-1 Triple Agonist",
        "tags": ["FAT LOSS", "WEIGHT LOSS", "INSULIN SENSITIVITY", "CARDIOVASCULAR", "NEXT GEN"],
        "what": (
            "Retatrutide (LY3437943) is Eli Lilly's next-generation triple receptor agonist targeting "
            "GLP-1 (glucagon-like peptide-1), GIP (glucose-dependent insulinotropic polypeptide), and "
            "GCG (glucagon) receptors simultaneously. Phase 3 trials show 24.2% body weight reduction "
            "at 48 weeks at the highest dose — surpassing all other weight loss medications ever studied. "
            "Expected FDA approval 2025–2026."
        ),
        "benefits": [
            "24.2% body weight reduction in Phase 3 (highest dose, 48 weeks) — unprecedented",
            "Dual GLP-1 + GIP action (like Tirzepatide) plus GCG receptor for metabolic boost",
            "Significant visceral and liver fat reduction",
            "Cardiovascular risk reduction — improves lipid profile, blood pressure, HbA1c",
            "Appetite suppression + improved satiety signaling",
            "Improved insulin sensitivity and glycemic control",
            "Liver fat reduction — potential NASH/MAFLD treatment",
            "Once-weekly injection for high compliance",
        ],
        "how_it_works": (
            "Retatrutide agonizes three distinct receptors: GLP-1R (appetite suppression, slow gastric "
            "emptying, insulin secretion), GIPR (enhanced insulin response, fat metabolism), and GCGR "
            "(increased energy expenditure, lipolysis, hepatic glucose regulation). The glucagon component "
            "drives thermogenesis and liver fat mobilization not seen with dual agonists."
        ),
        "doses": [
            ("2–4 mg", "Starting Dose (wkly)"),
            ("Up to 12 mg", "Max Studied Dose"),
            ("Once weekly", "Frequency"),
            ("Titrate up", "Protocol"),
        ],
        "protocols": [
            "<b>Starting:</b> 2 mg SC weekly x 4 weeks, then titrate up every 4 weeks.",
            "<b>Target dose:</b> 8–12 mg/week (per Phase 3 protocol) for maximum fat loss.",
            "<b>Maintenance:</b> Lowest effective dose that maintains weight loss.",
            "<b>Compounded:</b> Available from compounding pharmacies; verify purity before use.",
        ],
        "side_effects": [
            "Nausea, vomiting, diarrhea, constipation (GI class effects — typically transient)",
            "Hypoglycemia (especially combined with insulin secretagogues)",
            "Decreased appetite and caloric intake",
            "Muscle mass loss (mitigate with high protein + resistance training)",
            "Injection site reactions (mild)",
            "Tachycardia at higher doses (GCG effect)",
        ],
        "warning": "Contraindicated in personal/family history of medullary thyroid carcinoma or MEN2. Not approved — use compounded with verified supplier.",
        "storage": "Refrigerate (2–8°C). Do not freeze. Reconstituted: refrigerate, use within 28 days.",
    },
    {
        "name": "Semaglutide",
        "full_name": "Semaglutide (Ozempic / Wegovy)",
        "class": "GLP-1 Receptor Agonist",
        "tags": ["FAT LOSS", "DIABETES", "CARDIOVASCULAR", "APPETITE", "FDA APPROVED"],
        "what": (
            "Semaglutide is a long-acting GLP-1 receptor agonist approved by the FDA for type 2 "
            "diabetes (Ozempic) and chronic weight management (Wegovy). SELECT trial data showed a "
            "20% reduction in major cardiovascular events in non-diabetic patients. "
            "Produces 15–17% body weight reduction at maximum doses in clinical trials."
        ),
        "benefits": [
            "15–17% body weight reduction at 2.4 mg/week (Wegovy) in SURMOUNT trials",
            "20% reduction in cardiovascular events (SELECT trial, 2023)",
            "Significant HbA1c reduction in T2DM",
            "Reduced liver fat and improvement in NASH markers",
            "Blood pressure reduction (systolic -4–5 mmHg)",
            "Improved lipid profile (LDL, triglycerides)",
            "Appetite suppression and reduced food cravings",
            "Addictive behavior reduction (alcohol, nicotine — emerging data)",
        ],
        "how_it_works": (
            "Semaglutide binds GLP-1 receptors in the gut (slowing gastric emptying, increasing satiety), "
            "pancreas (stimulating insulin, inhibiting glucagon), brain (appetite centers in hypothalamus "
            "and brainstem), and cardiovascular system. Its fatty acid side chain extends half-life to "
            "~1 week via albumin binding."
        ),
        "doses": [
            ("0.25 mg/wk", "Starting Dose"),
            ("2.4 mg/wk", "Max (Wegovy)"),
            ("Once weekly", "Frequency"),
            ("4-week titration", "Protocol"),
        ],
        "protocols": [
            "<b>Ozempic (diabetes):</b> 0.25 mg weekly x4 → 0.5 mg x4 → 1 mg x4 → 2 mg.",
            "<b>Wegovy (obesity):</b> 0.25 mg x4 → 0.5 → 1.0 → 1.7 → 2.4 mg (each 4 weeks).",
            "<b>Compounded:</b> Slower titration to minimize GI side effects.",
            "<b>Protein:</b> 1g/lb body weight minimum to preserve lean mass during loss.",
        ],
        "side_effects": [
            "Nausea (most common — diminishes over weeks)",
            "Vomiting, diarrhea, constipation",
            "Gastroparesis risk with long-term use",
            "Muscle mass loss (offset with protein + resistance training)",
            "Pancreatitis (rare)",
            "Injection site reactions",
        ],
        "warning": "Contraindicated in personal/family history of MTC or MEN2. Pancreatitis — discontinue if severe abdominal pain develops.",
        "storage": "Refrigerate 2–8°C. Do not freeze. After first use, room temp up to 28 days (pen).",
    },
    {
        "name": "Tirzepatide",
        "full_name": "Tirzepatide (Mounjaro / Zepbound)",
        "class": "GLP-1 / GIP Dual Agonist",
        "tags": ["FAT LOSS", "INSULIN SENSITIVITY", "GIP", "CARDIOVASCULAR", "FDA APPROVED"],
        "what": (
            "Tirzepatide is a once-weekly dual GIP/GLP-1 receptor agonist approved by the FDA "
            "for type 2 diabetes (Mounjaro) and obesity (Zepbound). SURMOUNT-1 trials demonstrated "
            "22.5% body weight reduction at the highest dose — currently the most effective approved "
            "weight loss medication. Adding GIP agonism to GLP-1 produces synergistic metabolic effects."
        ),
        "benefits": [
            "22.5% body weight reduction at 15 mg/week (SURMOUNT-1) — best of any approved drug",
            "Superior HbA1c reduction vs. semaglutide (SURPASS trials)",
            "Significant visceral fat reduction",
            "Improved insulin sensitivity and beta-cell function",
            "Liver fat reduction (MAFLD/NASH improvement)",
            "Cardiovascular risk reduction (SURPASS-CVOT underway)",
            "Reduced hypertension and improved lipid profiles",
            "Better GI tolerability than semaglutide at equivalent doses",
        ],
        "how_it_works": (
            "Tirzepatide is a 'twincretin' — a single molecule that acts on both GLP-1R and GIPR with "
            "balanced potency. GIP agonism synergizes with GLP-1 to enhance insulin secretion, improve "
            "adipose tissue metabolism, and reduce glucagon. The combined receptor activation produces "
            "greater weight loss than GLP-1 alone."
        ),
        "doses": [
            ("2.5 mg/wk", "Starting Dose"),
            ("15 mg/wk", "Max Dose"),
            ("Once weekly", "Frequency"),
            ("4-week steps", "Titration"),
        ],
        "protocols": [
            "<b>Standard:</b> 2.5 mg x4 weeks → 5 mg x4 → 7.5 → 10 → 12.5 → 15 mg/week.",
            "<b>Aggressive recomp:</b> Pair with calorie deficit, 1g/lb protein, 3–4x resistance training.",
            "<b>Maintenance:</b> Lowest dose maintaining body composition goals.",
            "<b>Semaglutide switch:</b> No washout needed — titrate up from starting Tirzepatide dose.",
        ],
        "side_effects": [
            "Nausea, vomiting (less than semaglutide at comparable doses)",
            "Diarrhea, constipation",
            "Muscle mass loss (critical to offset with training + protein)",
            "Injection site erythema, bruising",
            "Hypoglycemia when combined with sulfonylureas or insulin",
        ],
        "warning": "Same thyroid tumor warnings as GLP-1 class. Not for personal/family history of MTC or MEN2.",
        "storage": "Refrigerate 2–8°C. After first use: 2–8°C or room temp up to 21 days (pen).",
    },
    {
        "name": "GHK-Cu",
        "full_name": "Copper Peptide GHK-Cu",
        "class": "Anti-Aging / Skin Peptide",
        "tags": ["SKIN REPAIR", "ANTI-AGING", "COLLAGEN", "HAIR GROWTH", "TOPICAL/INJECTABLE"],
        "what": (
            "GHK-Cu (glycyl-L-histidyl-L-lysine:copper) is a naturally occurring human plasma peptide "
            "that declines significantly with age. It acts as a master regulator of tissue repair "
            "and renewal — promoting collagen synthesis, wound healing, hair follicle regeneration, "
            "and gene expression reprogramming toward a more youthful state."
        ),
        "benefits": [
            "Stimulates collagen and elastin synthesis — improves skin firmness and elasticity",
            "Reduces fine lines and wrinkles (validated in multiple clinical studies)",
            "Promotes wound healing and scar remodeling",
            "Stimulates hair follicle proliferation — reduces hair loss, promotes regrowth",
            "Anti-inflammatory — reduces pro-inflammatory cytokines",
            "Antioxidant — chelates copper into protective pathways",
            "Reprograms aged gene expression toward younger patterns (Pickart research)",
            "Potential anti-cancer properties via tumor suppressor upregulation",
            "Neuroprotective — enhances nerve growth factor",
        ],
        "how_it_works": (
            "GHK-Cu acts as a biological 'switch' that resets aging gene expression. It upregulates "
            "over 31 genes related to tissue repair and downregulates 36 genes associated with "
            "inflammatory signaling and cancer progression. It also activates proteasomes (cellular "
            "cleanup systems) and promotes angiogenesis in damaged tissue."
        ),
        "doses": [
            ("0.5–2 mg", "SC/IM (injectable)"),
            ("Topical 1–3%", "Topical creams"),
            ("Daily", "Frequency"),
            ("Ongoing", "Duration"),
        ],
        "protocols": [
            "<b>Topical Anti-Aging:</b> 1–3% GHK-Cu serum applied 2x daily to face/scalp.",
            "<b>Injectable:</b> 0.5–2 mg SC daily or 3–5x weekly.",
            "<b>Hair Loss:</b> Scalp massage with GHK-Cu serum + topical minoxidil for synergy.",
            "<b>Stacks well with:</b> BPC-157, TB-500 for enhanced healing protocols.",
        ],
        "side_effects": [
            "Topical: mild skin redness, irritation (transient, usually at high concentrations)",
            "Injectable: injection site reactions (mild)",
            "Generally considered very safe — naturally occurring in human plasma",
            "Rare: skin discoloration at injection sites",
        ],
        "warning": "Use copper-peptide compatible skincare — avoid high-pH products (Vitamin C serums, retinoids) simultaneously as they degrade peptide.",
        "storage": "Lyophilized: room temp, away from light. Topical serums: refrigerate to extend shelf life.",
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL PEPTIDE FLYER
# ══════════════════════════════════════════════════════════════════════════════
def generate_peptide_flyer(p):
    safe = p["name"].replace("-", "").replace("/", "_").replace(" ", "_")
    doc, path = make_doc(f"FBF_Peptide_{safe}.pdf")

    story = []

    # Header block
    story.append(para("FORGED BY FREEDOM", "small"))
    story.append(para(p["name"], "title"))
    story.append(para(p["full_name"], "subtitle"))
    story.append(tag_table(p["tags"], [FBF_ORANGE]*len(p["tags"])))
    story.append(sp(10))
    story.append(orange_hr())

    # What is it
    story += section("WHAT IS IT?")
    story.append(para(p["what"]))
    story.append(sp(4))

    # Dose table
    story += section("DOSING AT A GLANCE")
    story.append(dose_table(p["doses"]))
    story.append(sp(8))

    # Benefits
    story += section("KEY BENEFITS")
    for b in p["benefits"]:
        story.append(bullet(b))
    story.append(sp(4))

    # How it works
    story += section("HOW IT WORKS")
    story.append(para(p["how_it_works"]))
    story.append(sp(4))

    # Protocols
    story += section("PROTOCOLS")
    for pr in p["protocols"]:
        story.append(para(pr, "bullet"))
    story.append(sp(4))

    # Side effects
    story += section("SIDE EFFECTS")
    for se in p["side_effects"]:
        story.append(bullet(se))
    story.append(sp(4))

    # Storage
    story += section("STORAGE")
    story.append(para(p["storage"]))
    story.append(sp(4))

    # Warning
    story.append(hr())
    story.append(para(f"⚠  {p['warning']}", "warning"))
    story.append(para(
        "This document is for educational purposes only. Not medical advice. "
        "Consult a qualified physician before using any peptide or performance compound. "
        "forgedbyfreedom.com", "small"))

    doc.build(story, onFirstPage=dark_background, onLaterPages=dark_background)
    print(f"  ✅  {path.name}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# ALL-IN-ONE PEPTIDE GUIDE
# ══════════════════════════════════════════════════════════════════════════════
def generate_all_peptides_guide():
    doc, path = make_doc("FBF_Complete_Peptide_Reference.pdf")
    story = []

    # Cover page content
    story.append(sp(20))
    story.append(para("FORGED BY FREEDOM", "subtitle"))
    story.append(para("COMPLETE PEPTIDE REFERENCE", "h1_big"))
    story.append(para("2025–2026 Edition", "subtitle"))
    story.append(sp(8))
    story.append(orange_hr())
    story.append(para(
        "A comprehensive reference guide covering healing peptides, GH secretagogues, "
        "weight loss peptides, sexual health compounds, and anti-aging peptides. "
        "Dosing, protocols, benefits, side effects, and stacking strategies for each compound.",
        "body"))
    story.append(sp(8))

    # Quick reference table
    all_tags_data = []
    headers = [
        Paragraph("<b>Peptide</b>", S["section"]),
        Paragraph("<b>Class</b>", S["section"]),
        Paragraph("<b>Primary Use</b>", S["section"]),
    ]
    all_tags_data.append(headers)
    for p in PEPTIDES:
        all_tags_data.append([
            Paragraph(p["name"], S["body"]),
            Paragraph(p["class"], S["small"]),
            Paragraph(p["tags"][0], S["small"]),
        ])
    ref_table = Table(all_tags_data, colWidths=[1.8*inch, 2.4*inch, 3.0*inch])
    ref_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), FBF_ORANGE),
        ("TEXTCOLOR", (0,0), (-1,0), FBF_DARK),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [FBF_CHARCOAL, FBF_GRAY]),
        ("GRID", (0,0), (-1,-1), 0.5, FBF_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(ref_table)
    story.append(sp(16))

    # Stacking guide
    story.append(para("POPULAR STACKS", "h2"))
    story.append(orange_hr())
    stacks = [
        ("Injury Healing (Gold Standard)", "BPC-157 500 mcg SC + TB-500 2 mg SC — 2x/week for 4–6 weeks"),
        ("GH Optimization (Clean)", "CJC-1295 100 mcg + Ipamorelin 200 mcg SC — before bed daily"),
        ("Maximum GH Pulse", "CJC-1295 100 mcg + Hexarelin 100 mcg — fasted, 2x daily (6-week cycle)"),
        ("Anti-Aging / Longevity", "Sermorelin 300 mcg bedtime + GHK-Cu 1 mg SC daily"),
        ("Elite Body Recomp", "CJC-1295 + Ipamorelin + IGF-1 LR3 40–60 mcg post-workout"),
        ("Weight Loss Protocol", "Tirzepatide or Retatrutide (weekly) + 1g/lb protein + resistance training"),
        ("Sexual Performance (Men)", "Tadalafil 5 mg daily + PT-141 1 mg SC 90 min before activity"),
        ("Sexual Performance (Women)", "PT-141 1.75 mg SC 45 min before + testosterone cream 1 mg/day"),
    ]
    for name, protocol in stacks:
        story.append(KeepTogether([
            para(f"<b>{name}</b>", "body"),
            para(protocol, "small"),
            sp(3),
        ]))
    story.append(sp(12))

    # Each peptide — compressed format
    for p in PEPTIDES:
        story.append(KeepTogether([
            para(p["name"], "h1_big"),
            para(f"{p['full_name']}  —  {p['class']}", "subtitle"),
            orange_hr(),
            para(p["what"]),
            sp(4),
        ]))

        story += section("BENEFITS")
        for b in p["benefits"][:6]:  # Top 6 in compressed view
            story.append(bullet(b))

        story += section("DOSING")
        story.append(dose_table(p["doses"]))
        story.append(sp(6))

        story += section("PROTOCOLS")
        for pr in p["protocols"][:3]:
            story.append(para(pr, "bullet"))

        story += section("SIDE EFFECTS")
        for se in p["side_effects"][:4]:
            story.append(bullet(se))

        story.append(sp(4))
        story.append(para(f"⚠  {p['warning']}", "warning"))
        story.append(sp(6))
        story.append(hr())
        story.append(sp(6))

    # Disclaimer
    story.append(para(
        "MEDICAL DISCLAIMER: This guide is for educational purposes only. None of this constitutes "
        "medical advice. All peptides described are for research purposes and may not be approved by "
        "the FDA for the uses described. Always consult a qualified physician before using any compound. "
        "Verify supplier quality via third-party HPLC testing. forgedbyfreedom.com",
        "small"))

    doc.build(story, onFirstPage=dark_background, onLaterPages=dark_background)
    print(f"  ✅  {path.name}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# WOMEN'S HEALTH & HRT GUIDE
# ══════════════════════════════════════════════════════════════════════════════
def generate_womens_health_guide():
    doc, path = make_doc("FBF_Womens_Health_HRT_Sexual_Wellness.pdf")
    story = []

    # Cover
    story.append(sp(10))
    story.append(para("FORGED BY FREEDOM", "subtitle"))
    story.append(para("WOMEN'S HEALTH, HRT & SEXUAL WELLNESS", "h1_big"))
    story.append(para("Hormone Optimization · Sexual Health · Performance · Recovery", "subtitle"))
    story.append(orange_hr())
    story.append(para(
        "A science-backed reference guide covering female hormone replacement therapy, "
        "sexual health optimization, libido, arousal, menopause management, and evidence-based "
        "recommendations for women at every stage of life. Written for health-conscious women "
        "who want real answers based on data, not dismissal.", "body"))
    story.append(sp(12))

    # === SECTION 1: FEMALE HORMONES ===
    story.append(para("SECTION 1: FEMALE HORMONES — THE FOUNDATION", "h2"))
    story.append(orange_hr())

    story += section("THE BIG FOUR: ESTROGEN, PROGESTERONE, TESTOSTERONE, DHEA")
    hormone_data = [
        ["Hormone", "Normal Range", "Function", "Deficiency Signs"],
        ["Estradiol (E2)", "Premenopause: 30–400 pg/mL\nPostmenopause: <30 pg/mL",
         "Bone density, cardiovascular, vaginal health, mood, cognition",
         "Hot flashes, vaginal dryness, brain fog, osteoporosis, low libido"],
        ["Progesterone", "Luteal: 5–20 ng/mL\nPostmenopause: <1 ng/mL",
         "Uterine health, sleep quality, anxiety regulation, fluid balance",
         "Insomnia, anxiety, irregular cycles, estrogen dominance symptoms"],
        ["Testosterone (Total)", "15–70 ng/dL (women)\nOptimal: 30–70 ng/dL",
         "Libido, muscle mass, energy, clitoral sensitivity, mood",
         "Low libido, fatigue, muscle loss, reduced orgasm intensity, depression"],
        ["DHEA-S", "35–430 mcg/dL (age-dependent)",
         "Precursor to estrogens and androgens, energy, immune function",
         "Low energy, low libido, poor mood, accelerated aging"],
    ]
    ht = Table(hormone_data, colWidths=[1.2*inch, 1.9*inch, 2.1*inch, 2.0*inch])
    ht.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), FBF_ORANGE),
        ("TEXTCOLOR", (0,0), (-1,0), FBF_DARK),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [FBF_CHARCOAL, FBF_GRAY]),
        ("GRID", (0,0), (-1,-1), 0.5, FBF_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,1), (-1,-1), FBF_WHITE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(ht)
    story.append(sp(10))

    # === SECTION 2: HRT ===
    story.append(para("SECTION 2: HORMONE REPLACEMENT THERAPY (HRT)", "h2"))
    story.append(orange_hr())

    story += section("THE EVIDENCE ON HRT — SETTING THE RECORD STRAIGHT")
    story.append(para(
        "The 2002 WHI study caused decades of unnecessary HRT avoidance by overstating risks. "
        "Modern re-analysis shows that <b>bioidentical HRT started within 10 years of menopause "
        "(the 'timing hypothesis') significantly reduces cardiovascular disease, all-cause mortality, "
        "osteoporosis, and cognitive decline</b>. The risks of NOT treating menopause are now "
        "understood to be substantial.", "body"))
    story.append(sp(4))

    benefits_hrt = [
        "Eliminates hot flashes and night sweats (90%+ relief)",
        "Restores vaginal moisture, elasticity, and pH — eliminates painful intercourse",
        "Improves sleep architecture and sleep quality significantly",
        "Reduces cardiovascular disease risk when started early (timing hypothesis)",
        "Preserves bone density — prevents osteoporosis fractures",
        "Reduces risk of type 2 diabetes and metabolic syndrome",
        "Improves mood, reduces depression and anxiety",
        "Cognitive protection — reduces Alzheimer's and dementia risk",
        "Restores libido and sexual function",
        "Improves skin collagen, moisture, and elasticity",
    ]
    story += section("BENEFITS OF TIMELY HRT")
    for b in benefits_hrt:
        story.append(bullet(b))
    story.append(sp(6))

    # HRT types table
    story += section("HRT OPTIONS — ROUTES AND FORMULATIONS")
    hrt_data = [
        ["Hormone", "Route", "Typical Dose", "Notes"],
        ["Estradiol", "Transdermal patch", "0.025–0.1 mg/day", "Preferred route — avoids first-pass liver metabolism. Lower clot risk vs. oral."],
        ["Estradiol", "Gel/cream (topical)", "0.5–1.5 mg/day", "Flexible dosing. Apply to inner arm or thigh daily."],
        ["Estradiol", "Oral (Estrace)", "0.5–2 mg/day", "Convenient but first-pass metabolism — higher VTE risk vs. transdermal."],
        ["Progesterone", "Oral (Prometrium)", "100–200 mg at bedtime", "Bioidentical. Improves sleep. Essential for uterine protection with estrogen."],
        ["Progesterone", "Vaginal (Crinone)", "4–8% gel", "For uterine protection without systemic side effects."],
        ["Testosterone", "Cream/gel (compounded)", "0.5–2 mg/day", "Applied to clitoris, labia, or inner thigh. Improves libido, orgasm."],
        ["Testosterone", "Injection (IM/SC)", "5–10 mg/week", "More precise dosing for women with significant deficiency."],
        ["DHEA", "Oral", "25–50 mg/day", "Precursor to both estrogen and testosterone. Monitor levels at 3 months."],
        ["DHEA (Intrarosa)", "Vaginal suppository", "6.5 mg/day", "FDA approved for vaginal atrophy. Converts locally to estrogen + testosterone."],
    ]
    hrtt = Table(hrt_data, colWidths=[1.0*inch, 1.4*inch, 1.4*inch, 3.4*inch])
    hrtt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), FBF_ORANGE),
        ("TEXTCOLOR", (0,0), (-1,0), FBF_DARK),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [FBF_CHARCOAL, FBF_GRAY]),
        ("GRID", (0,0), (-1,-1), 0.5, FBF_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,1), (-1,-1), FBF_WHITE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(hrtt)
    story.append(sp(10))

    # Testosterone for women
    story += section("TESTOSTERONE THERAPY FOR WOMEN — THE MISSING PIECE")
    story.append(para(
        "Female testosterone deficiency is dramatically underdiagnosed and undertreated. "
        "Women produce 3–4x more testosterone than estrogen — and its decline drives many of "
        "the symptoms women suffer silently: low libido, fatigue, muscle loss, depression, "
        "reduced orgasm intensity, and blunted motivation.", "body"))
    story.append(sp(4))
    t_benefits = [
        "Restores sexual desire and libido — most consistent evidence of any HRT modality",
        "Increases orgasm intensity and frequency",
        "Improves clitoral and vaginal sensitivity",
        "Increases lean muscle mass and reduces body fat",
        "Improves energy, motivation, and drive",
        "Reduces depression and anxiety independent of estrogen therapy",
        "Improves cognitive sharpness and working memory",
        "Maintains bone density (synergistic with estrogen)",
    ]
    for b in t_benefits:
        story.append(bullet(b))
    story.append(sp(4))
    story.append(dose_table([
        ("Target Total T", "30–70 ng/dL"),
        ("Target Free T", "1–5 pg/mL"),
        ("Cream dose", "0.5–2 mg/day"),
        ("Injection", "5–10 mg/wk"),
    ]))
    story.append(sp(6))
    story.append(para(
        "<b>Application sites for testosterone cream:</b> Clitoris, inner labia, inner arm, or upper thigh. "
        "Clitoral application maximizes local effect on sexual sensitivity.", "body"))
    story.append(sp(10))

    # === SECTION 3: MENOPAUSE ===
    story.append(para("SECTION 3: MENOPAUSE — STAGES AND MANAGEMENT", "h2"))
    story.append(orange_hr())

    story += section("PERIMENOPAUSE vs. MENOPAUSE vs. POSTMENOPAUSE")
    meno_data = [
        ["Stage", "Definition", "Key Symptoms", "HRT Approach"],
        ["Perimenopause", "Variable cycles, 2–10 yrs before menopause (avg 40–51)",
         "Irregular periods, hot flashes, mood swings, sleep disruption",
         "Low-dose transdermal estradiol + progesterone. Monitor every 3–6 months."],
        ["Menopause", "12 consecutive months without period",
         "Hot flashes, vaginal atrophy, sleep disruption, cognitive fog",
         "Standard HRT initiation — transdermal E2 + oral progesterone nightly."],
        ["Postmenopause", ">12 months post-last period",
         "Ongoing atrophy, bone loss, cardiovascular risk, sexual dysfunction",
         "Continue HRT indefinitely if well-tolerated and no contraindications."],
        ["Surgical Menopause", "Oophorectomy at any age",
         "Abrupt, severe — all symptoms at once",
         "Immediate HRT initiation. Higher doses may be needed. Add testosterone."],
    ]
    mt = Table(meno_data, colWidths=[1.2*inch, 1.6*inch, 1.8*inch, 2.6*inch])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), FBF_ORANGE),
        ("TEXTCOLOR", (0,0), (-1,0), FBF_DARK),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [FBF_CHARCOAL, FBF_GRAY]),
        ("GRID", (0,0), (-1,-1), 0.5, FBF_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,1), (-1,-1), FBF_WHITE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(mt)
    story.append(sp(10))

    # === SECTION 4: SEXUAL HEALTH ===
    story.append(para("SECTION 4: FEMALE SEXUAL HEALTH & PERFORMANCE", "h2"))
    story.append(orange_hr())

    story += section("COMMON SEXUAL HEALTH CONDITIONS")
    conditions = [
        ("<b>HSDD (Hypoactive Sexual Desire Disorder)</b>",
         "Low or absent sexual desire causing distress. Affects 10–15% of all women and up to 40% of postmenopausal women. Most underdiagnosed sexual health condition in women."),
        ("<b>GSM (Genitourinary Syndrome of Menopause)</b>",
         "Vaginal dryness, atrophy, thinning, burning, painful intercourse (dyspareunia), urinary urgency. Affects 50–60% of postmenopausal women. Entirely preventable and treatable."),
        ("<b>Female Orgasmic Disorder</b>",
         "Difficulty achieving orgasm despite adequate arousal. Often due to inadequate stimulation, hormonal deficiency (testosterone), or clitoral hood adhesion."),
        ("<b>Vaginismus / Dyspareunia</b>",
         "Painful intercourse — may be hormonal (GSM), musculoskeletal (pelvic floor dysfunction), or psychological. Pelvic floor PT + estrogen therapy highly effective."),
    ]
    for title, desc in conditions:
        story.append(para(title, "body"))
        story.append(para(desc, "small"))
        story.append(sp(4))

    story += section("SEXUAL HEALTH TREATMENTS & COMPOUNDS")
    treatments = [
        ("Transdermal Testosterone", "0.5–2 mg/day cream", "First-line for low libido/HSDD. Strongest evidence of any agent."),
        ("PT-141 (Vyleesi)", "1.75 mg SC 45 min prior", "FDA approved for HSDD. Increases desire via brain melanocortin receptors."),
        ("Vaginal Estradiol", "10 mcg suppository 2x/wk", "GSM treatment. Minimal systemic absorption. Safe even in women with cancer history."),
        ("DHEA (Intrarosa)", "6.5 mg vaginal daily", "FDA approved for dyspareunia. Converts locally to E + T."),
        ("Ospemifene (Osphena)", "60 mg oral daily", "SERM — activates vaginal estrogen receptors without systemic estrogen."),
        ("Sildenafil (Addyi adjacent)", "Off-label", "Some benefit in postmenopausal FSAD — increases genital blood flow."),
        ("Oxytocin", "Nasal spray", "Bonding, arousal, orgasm facilitation — off-label but gaining evidence."),
        ("Bupropion", "150–300 mg/day", "Antidepressant with pro-sexual effects — counters SSRI-induced sexual dysfunction."),
    ]
    treat_table = Table(
        [[Paragraph(n, S["body"]), Paragraph(d, S["small"]), Paragraph(e, S["small"])] for n,d,e in treatments],
        colWidths=[1.6*inch, 1.8*inch, 3.8*inch]
    )
    treat_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), FBF_CHARCOAL),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [FBF_CHARCOAL, FBF_GRAY]),
        ("GRID", (0,0), (-1,-1), 0.5, FBF_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(treat_table)
    story.append(sp(10))

    # Practical techniques
    story += section("PRACTICAL SEXUAL WELLNESS — EVIDENCE-BASED TECHNIQUES")
    techniques = [
        "Arousal takes longer as estrogen declines — allow 20–30 min of non-goal-oriented stimulation before penetration.",
        "Clitoral stimulation is primary for 70–80% of women — direct clitoral focus during partnered sex dramatically improves orgasm rates.",
        "Pelvic floor exercises (Kegels): 3 sets of 10–15 contractions daily — improve orgasm intensity and urinary control.",
        "Vibrator use (clitoral) is evidence-based for orgasmic disorder — endorsed by AASECT and ACOG.",
        "Vaginal moisturizers (Replens, hyaluronic acid) used 3x/week reduce dryness independent of HRT.",
        "Lubricants during intercourse: use water-based or silicone-based; avoid glycerin-containing products.",
        "Communication: explicit discussion of preferences, speeds, and stimulation types improves sexual satisfaction more than any compound.",
        "Mindfulness-based sex therapy: 4–8 sessions significantly improve desire, arousal, and satisfaction in women with HSDD.",
        "Exercise: 150+ min/week aerobic activity improves sexual function, body image, and hormone levels.",
        "Sleep: 7–9 hours — poor sleep reduces testosterone by up to 15% in women.",
    ]
    for t in techniques:
        story.append(bullet(t))
    story.append(sp(6))

    # === SECTION 5: BLOODWORK ===
    story.append(para("SECTION 5: RECOMMENDED BLOODWORK PANEL", "h2"))
    story.append(orange_hr())

    story += section("BASELINE FEMALE HORMONE PANEL")
    bw_data = [
        ["Marker", "Optimal Range", "Frequency"],
        ["Estradiol (E2)", "Follicular: 30–100 pg/mL; Luteal: 100–300 pg/mL; Post-meno: 40–80 pg/mL (on HRT)", "Every 3 months until stable"],
        ["Total Testosterone", "30–70 ng/dL", "Every 3 months"],
        ["Free Testosterone", "1–5 pg/mL", "Every 6 months"],
        ["SHBG", "18–144 nmol/L (lower = more free T)", "Every 6 months"],
        ["Progesterone", "Luteal: 5–20 ng/mL; Post-meno: <1", "Every 3 months on HRT"],
        ["DHEA-S", "Age-appropriate (95–270 mcg/dL at 40+)", "Annually"],
        ["FSH", "Post-meno: >30 mIU/mL confirms menopause", "Once to confirm menopause"],
        ["LH", "Assists menopause confirmation", "Once"],
        ["Thyroid (TSH + Free T3/T4)", "TSH 1–2 mIU/L optimal", "Annually"],
        ["CBC + CMP", "Full metabolic baseline", "Annually"],
        ["Lipid Panel", "LDL <100, HDL >60 optimal in women", "Annually on HRT"],
        ["Bone Density (DEXA)", "T-score > -1.0", "Every 2 years postmenopause"],
    ]
    bwt = Table(bw_data, colWidths=[1.7*inch, 3.0*inch, 2.5*inch])
    bwt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), FBF_ORANGE),
        ("TEXTCOLOR", (0,0), (-1,0), FBF_DARK),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [FBF_CHARCOAL, FBF_GRAY]),
        ("GRID", (0,0), (-1,-1), 0.5, FBF_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,1), (-1,-1), FBF_WHITE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(bwt)
    story.append(sp(10))

    # === SECTION 6: STACKS ===
    story.append(para("SECTION 6: FBF RECOMMENDED FEMALE PROTOCOLS", "h2"))
    story.append(orange_hr())

    female_protocols = [
        ("Perimenopause Starter Protocol",
         "Estradiol patch 0.05 mg/day + Oral progesterone 100 mg at bedtime + Testosterone cream 1 mg/day to clitoral/labial area. Recheck in 8–12 weeks."),
        ("Menopause / Postmenopause Full Protocol",
         "Estradiol patch 0.075–0.1 mg/day + Oral progesterone 200 mg at bedtime + Testosterone cream 1–2 mg/day + Vaginal estradiol 10 mcg 2x/week if GSM present."),
        ("HSDD / Low Libido Protocol",
         "Testosterone cream 1–2 mg/day clitoris/inner thigh + PT-141 1.75 mg SC 45 min before activity (as needed) + Optimize estradiol if menopausal."),
        ("Surgical Menopause Protocol",
         "Immediate high-dose estradiol (0.1 mg patch or 2 mg gel) + Progesterone 200 mg (if uterus present) + Testosterone 2 mg/day + Monitor in 6–8 weeks."),
        ("Active / Athletic Women",
         "Testosterone cream 1–2 mg/day for performance + Estradiol for bone/recovery + DHEA 25 mg/day for energy + BPC-157 500 mcg if injury present."),
        ("Anti-Aging / Longevity Protocol",
         "Estradiol + Progesterone HRT (as above) + GHK-Cu 1 mg SC 5x/week for skin/collagen + GH peptides (Sermorelin 300 mcg bedtime) + DHEA 25 mg/day."),
    ]
    for pname, pdesc in female_protocols:
        story.append(KeepTogether([
            para(f"<b>{pname}</b>", "section"),
            para(pdesc, "body"),
            sp(6),
        ]))

    story.append(hr())
    story.append(sp(6))
    story.append(para(
        "IMPORTANT: All hormone therapies require a physician's evaluation, laboratory testing, and "
        "prescription in most countries. The protocols described here reflect current evidence-based "
        "practice but must be individualized by a qualified HRT specialist. This document is educational "
        "only and does not constitute medical advice. forgedbyfreedom.com", "small"))

    doc.build(story, onFirstPage=dark_background, onLaterPages=dark_background)
    print(f"  ✅  {path.name}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  FBF BRANDED PDF FLYER GENERATOR")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)

    print("\n📄 Individual Peptide Flyers:")
    for p in PEPTIDES:
        generate_peptide_flyer(p)

    print("\n📚 All-In-One Peptide Reference Guide:")
    generate_all_peptides_guide()

    print("\n💊 Women's Health & HRT Guide:")
    generate_womens_health_guide()

    total = len(PEPTIDES) + 2
    print(f"\n✅ Done — {total} PDFs generated in {OUTPUT_DIR}")
