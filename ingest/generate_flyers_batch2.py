#!/usr/bin/env python3
"""
FBF Branded PDF Flyer Generator — Batch 2
MOTS-c, MK-677, Tesofensine, 5-Amino-1MQ, GH, Semax, Selank,
Oxytocin, SLU-PP-332, BAM-15, CAG (Cycloalanylglycine)
"""

import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ── Brand ─────────────────────────────────────────────────────────────────────
FBF_ORANGE   = colors.HexColor("#FF6A00")
FBF_DARK     = colors.HexColor("#0a0a0a")
FBF_CHARCOAL = colors.HexColor("#1c1c1c")
FBF_GRAY     = colors.HexColor("#2a2a2a")
FBF_LGRAY    = colors.HexColor("#888888")
FBF_WHITE    = colors.HexColor("#FFFFFF")
FBF_GREEN    = colors.HexColor("#22c55e")
FBF_GOLD     = colors.HexColor("#f59e0b")
FBF_BLUE     = colors.HexColor("#3b82f6")
FBF_PURPLE   = colors.HexColor("#8b5cf6")
FBF_RED      = colors.HexColor("#ef4444")

OUTPUT_DIR = Path(__file__).parent.parent / "flyers"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def make_styles():
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=28,
            textColor=FBF_ORANGE, spaceAfter=4, leading=32),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=13,
            textColor=FBF_LGRAY, spaceAfter=12, leading=16),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=13,
            textColor=FBF_ORANGE, spaceBefore=14, spaceAfter=4, leading=16),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10,
            textColor=FBF_WHITE, leading=15, spaceAfter=4),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=10,
            textColor=FBF_WHITE, leading=15, leftIndent=14, spaceAfter=3,
            bulletIndent=4, bulletText="•"),
        "warning": ParagraphStyle("warning", fontName="Helvetica-BoldOblique",
            fontSize=9, textColor=FBF_GOLD, leading=13, spaceBefore=6),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=9,
            textColor=FBF_LGRAY, leading=12),
        "dose_val": ParagraphStyle("dose_val", fontName="Helvetica-Bold",
            fontSize=11, textColor=FBF_GREEN, leading=14, alignment=TA_CENTER),
        "dose_lbl": ParagraphStyle("dose_lbl", fontName="Helvetica", fontSize=8,
            textColor=FBF_LGRAY, leading=11, alignment=TA_CENTER),
        "tag": ParagraphStyle("tag", fontName="Helvetica-Bold", fontSize=9,
            textColor=FBF_DARK, alignment=TA_CENTER),
        "class_badge": ParagraphStyle("class_badge", fontName="Helvetica-Bold",
            fontSize=10, textColor=FBF_DARK, alignment=TA_CENTER),
    }

S = make_styles()


def dark_background(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFillColor(FBF_DARK)
    canvas_obj.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
    canvas_obj.setFillColor(FBF_ORANGE)
    canvas_obj.rect(0, letter[1] - 6, letter[0], 6, fill=1, stroke=0)
    canvas_obj.setFillColor(FBF_CHARCOAL)
    canvas_obj.rect(0, 0, letter[0], 36, fill=1, stroke=0)
    canvas_obj.setFillColor(FBF_LGRAY)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawCentredString(letter[0] / 2, 14,
        "FORGED BY FREEDOM  |  FBF AI Coach  |  forgedbyfreedom.com  |  Educational Use Only — Not Medical Advice")
    canvas_obj.restoreState()


def make_doc(filename):
    path = OUTPUT_DIR / filename
    doc = SimpleDocTemplate(str(path), pagesize=letter,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.7*inch, bottomMargin=0.6*inch)
    doc.build = lambda story, **kw: SimpleDocTemplate.build(
        doc, story, onFirstPage=dark_background, onLaterPages=dark_background)
    return doc, path


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
    return [para(text, "section"),
            HRFlowable(width="100%", thickness=1, color=FBF_GRAY, spaceAfter=5)]

def dose_table(rows):
    data = [[Paragraph(v, S["dose_val"]) for _, v in rows],
            [Paragraph(l, S["dose_lbl"]) for l, _ in rows]]
    col_w = (7.2 * inch) / len(rows)
    t = Table(data, colWidths=[col_w] * len(rows))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FBF_CHARCOAL),
        ("BOX", (0, 0), (-1, -1), 1, FBF_ORANGE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, FBF_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t

def tag_table(tags, tag_colors=None):
    if tag_colors is None:
        tag_colors = [FBF_ORANGE] * len(tags)
    data = [[Paragraph(f"<b>{t}</b>", S["tag"]) for t in tags]]
    col_w = (7.2 * inch) / len(tags)
    t = Table(data, colWidths=[col_w] * len(tags))
    cmds = [
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]
    for i, c in enumerate(tag_colors):
        cmds.append(("BACKGROUND", (i, 0), (i, 0), c))
    t.setStyle(TableStyle(cmds))
    return t


def build_flyer(p):
    safe = p["name"].replace("-", "").replace("/", "_").replace("+", "plus").replace(" ", "_")
    filename = f"FBF_Peptide_{safe}.pdf"
    path = OUTPUT_DIR / filename
    doc = SimpleDocTemplate(str(path), pagesize=letter,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.7*inch, bottomMargin=0.6*inch)

    story = []
    story.append(para("FORGED BY FREEDOM", "small"))
    story.append(para(p["name"], "title"))
    story.append(para(p["full_name"], "subtitle"))
    story.append(tag_table(p["tags"]))
    story.append(sp(10))
    story.append(orange_hr())

    story += section("WHAT IS IT?")
    story.append(para(p["what"]))
    story.append(sp(4))

    story += section("DOSING AT A GLANCE")
    story.append(dose_table(p["doses"]))
    story.append(sp(8))

    story += section("KEY BENEFITS")
    for b in p["benefits"]:
        story.append(bullet(b))
    story.append(sp(4))

    story += section("HOW IT WORKS")
    story.append(para(p["how_it_works"]))
    story.append(sp(4))

    story += section("PROTOCOLS")
    for pr in p["protocols"]:
        story.append(para(pr, "bullet"))
    story.append(sp(4))

    story += section("SIDE EFFECTS")
    for se in p["side_effects"]:
        story.append(bullet(se))
    story.append(sp(4))

    story += section("STORAGE")
    story.append(para(p["storage"]))
    story.append(sp(4))

    story.append(hr())
    story.append(para(f"⚠  {p['warning']}", "warning"))
    story.append(para(
        "Educational use only. Not medical advice. Consult a qualified physician before "
        "using any compound. forgedbyfreedom.com", "small"))

    doc.build(story, onFirstPage=dark_background, onLaterPages=dark_background)
    print(f"  ✅  {filename}")


# ══════════════════════════════════════════════════════════════════════════════
# COMPOUND DATA
# ══════════════════════════════════════════════════════════════════════════════
COMPOUNDS = [
    {
        "name": "MOTS-c",
        "full_name": "Mitochondrial Open Reading Frame of the 12S rRNA-c",
        "tags": ["MITOCHONDRIAL", "FAT LOSS", "INSULIN SENSITIVITY", "LONGEVITY", "EXERCISE MIMETIC"],
        "what": (
            "MOTS-c is a mitochondrial-derived peptide (MDP) encoded within the 12S ribosomal RNA "
            "gene of mitochondrial DNA. First identified in 2015 by Lee et al. at USC, it functions "
            "as a systemic metabolic regulator — improving insulin sensitivity, promoting fat utilization, "
            "enhancing mitochondrial function, and extending lifespan in animal models. It declines "
            "significantly with age, making it a compelling longevity and metabolic compound."
        ),
        "benefits": [
            "Activates AMPK — the master metabolic switch governing energy utilization",
            "Improves insulin sensitivity — reduces insulin resistance in skeletal muscle",
            "Promotes fat oxidation and lipolysis — shifts fuel use toward stored fat",
            "Enhances mitochondrial biogenesis and function",
            "Exercise mimetic — replicates some benefits of aerobic exercise without movement",
            "Extends healthy lifespan in mouse models",
            "Anti-inflammatory — reduces oxidative stress systemically",
            "Improves skeletal muscle function and endurance capacity",
            "Cognitive protection — crosses blood-brain barrier; neuroprotective effects",
            "Reduces age-related muscle loss (sarcopenia) in aging models",
        ],
        "how_it_works": (
            "MOTS-c acts in a AMPK-dependent manner to activate the folate cycle and one-carbon "
            "metabolism, leading to AICAR accumulation — a natural AMPK activator. This mirrors "
            "the metabolic effects of exercise and caloric restriction. It also translocates to the "
            "nucleus under stress, regulating nuclear gene expression and the adaptive response to "
            "metabolic challenge."
        ),
        "doses": [
            ("5–15 mg", "Weekly SC dose"),
            ("1–5 mg", "Daily SC (alt. protocol)"),
            ("Morning", "Optimal timing"),
            ("8–12 weeks", "Cycle"),
        ],
        "protocols": [
            "<b>Weekly Protocol:</b> 10 mg SC once weekly, morning fasted.",
            "<b>Daily Protocol:</b> 2–5 mg SC daily, cycle 8 weeks on / 4 weeks off.",
            "<b>Exercise Stack:</b> Dose pre-training — synergistic with aerobic exercise for metabolic adaptation.",
            "<b>Longevity Stack:</b> MOTS-c + Semax + NMN/NR for comprehensive mitochondrial and cognitive support.",
        ],
        "side_effects": [
            "Generally well tolerated — no significant adverse effects in current human use",
            "Injection site reactions (mild, transient)",
            "Mild fatigue or lightheadedness at higher doses (AMPK activation effect)",
            "Hypoglycemia possible if combined with insulin or diabetes medications",
        ],
        "warning": "Research peptide — no human clinical trials completed. Source from reputable suppliers with HPLC certification.",
        "storage": "Lyophilized: refrigerate or -20°C freezer. Reconstituted: refrigerate, use within 30 days.",
    },
    {
        "name": "MK-677",
        "full_name": "Ibutamoren (MK-677) — Oral GH Secretagogue",
        "tags": ["ORAL GH RELEASE", "MUSCLE GROWTH", "SLEEP", "HUNGER", "LONG-ACTING"],
        "what": (
            "MK-677 (Ibutamoren) is a non-peptide oral ghrelin mimetic and GH secretagogue. It "
            "stimulates GH and IGF-1 release by acting on GHSR-1a receptors — and crucially, "
            "it is orally bioavailable with a 24-hour half-life, requiring just one dose per day. "
            "The only oral compound that significantly and sustainably raises GH and IGF-1 long-term "
            "without injections. Extensively studied in clinical trials."
        ),
        "benefits": [
            "Significantly increases GH and IGF-1 (sustained, 24-hour elevation)",
            "Oral — no injections required (major compliance advantage)",
            "Accelerates muscle growth and recovery via IGF-1 upregulation",
            "Dramatically improves sleep — increases REM and deep sleep stages",
            "Improves bone density — shown in multiple clinical trials",
            "Reduces body fat while preserving lean mass in caloric deficits",
            "Anti-catabolic — preserves muscle during periods of restriction",
            "Improves skin quality, collagen, and wound healing",
            "Cognitive benefits — IGF-1 is neuroprotective and neurogenic",
            "Shown to reverse catabolic state in hip fracture patients (clinical trial)",
        ],
        "how_it_works": (
            "MK-677 mimics the action of ghrelin at the GHSR-1a receptor in the hypothalamus and "
            "pituitary, amplifying natural GH pulse amplitude without disrupting pulsatility. "
            "Unlike injectable GHRPs, the 24-hour half-life provides sustained IGF-1 elevation "
            "rather than discrete pulses. It does not suppress natural GH axis or affect cortisol "
            "at therapeutic doses."
        ),
        "doses": [
            ("10–25 mg", "Daily oral dose"),
            ("Before bed", "Optimal timing"),
            ("Once daily", "Frequency"),
            ("16–24 weeks+", "Cycle (long)"),
        ],
        "protocols": [
            "<b>Standard:</b> 25 mg orally before bed (food optional) — maximizes GH pulse during sleep.",
            "<b>Sensitive start:</b> Begin at 10 mg/day for 2 weeks, then increase to 25 mg.",
            "<b>Cutting:</b> 10–15 mg to balance IGF-1 benefits against water retention and hunger.",
            "<b>Stack:</b> MK-677 + CJC-1295/Ipamorelin on injection days = dual GH stimulation.",
            "<b>Long-term:</b> Can run continuously — some protocols run 6–12+ months with bloodwork monitoring.",
        ],
        "side_effects": [
            "Significant appetite increase (ghrelin mimetic effect — plan calories accordingly)",
            "Water retention, especially first 2–4 weeks",
            "Temporary insulin resistance / blood glucose elevation — monitor fasting glucose",
            "Fatigue or lethargy (GH effect — take at bedtime to minimize)",
            "Tingling, numbness (carpal tunnel-like at 25 mg+)",
            "Potential prolactin elevation (monitor on extended cycles)",
        ],
        "warning": "Monitor fasting glucose and HbA1c every 8–12 weeks on extended cycles. Water retention may cause temporary weight gain unrelated to fat.",
        "storage": "Oral liquid or capsule — room temperature, away from heat and light. 2-year shelf life if sealed.",
    },
    {
        "name": "Tesofensine",
        "full_name": "Tesofensine — Triple Monoamine Reuptake Inhibitor",
        "tags": ["WEIGHT LOSS", "APPETITE SUPPRESSION", "DOPAMINE", "NOREPINEPHRINE", "SEROTONIN"],
        "what": (
            "Tesofensine is a novel triple reuptake inhibitor of dopamine, norepinephrine, and serotonin "
            "(similar mechanism to phentermine but more selective). Originally developed for Parkinson's "
            "and Alzheimer's disease, Phase 2 weight loss trials showed 10.6% body weight reduction "
            "at 0.5 mg/day over 24 weeks — outperforming most approved anti-obesity drugs of its era. "
            "It reduces appetite through multiple central pathways simultaneously."
        ),
        "benefits": [
            "10.6% body weight reduction at 0.5 mg/day (Phase 2 TIPO-1 trial, 24 weeks)",
            "Significant reduction in appetite and food cravings",
            "Increases basal metabolic rate (norepinephrine effect)",
            "Improved energy and motivation (dopamine + norepinephrine)",
            "Mood enhancement (serotonin component)",
            "Superior to most single-mechanism appetite suppressants",
            "Synergistic with GLP-1 agonists for combined central + peripheral appetite control",
            "Shown to reduce caloric intake by 15–20% in studies",
        ],
        "how_it_works": (
            "Tesofensine blocks the reuptake transporters for dopamine (DAT), norepinephrine (NET), "
            "and serotonin (SERT) — increasing synaptic levels of all three monoamines. "
            "Norepinephrine increases energy expenditure and reduces appetite via beta-adrenergic "
            "receptors. Dopamine reduces reward-driven eating. Serotonin signals satiety centrally. "
            "The triple mechanism prevents receptor adaptation that limits single-mechanism drugs."
        ),
        "doses": [
            ("0.25 mg/day", "Starting dose"),
            ("0.5 mg/day", "Standard dose"),
            ("1.0 mg/day", "Max dose (caution)"),
            ("Morning", "Timing"),
        ],
        "protocols": [
            "<b>Start low:</b> 0.25 mg orally daily x4 weeks, then titrate to 0.5 mg.",
            "<b>Standard protocol:</b> 0.5 mg/day morning, assess at 8 weeks for response.",
            "<b>Cycling:</b> 12–16 weeks on, 4–8 weeks off to prevent monoamine depletion.",
            "<b>Stack:</b> Tesofensine + GLP-1 agonist (semaglutide/tirzepatide) for additive weight loss.",
            "<b>Do not stack with:</b> MAOIs, SSRIs, SNRIs (serotonin syndrome risk).",
        ],
        "side_effects": [
            "Dry mouth (very common — most frequently reported side effect)",
            "Nausea (common early, diminishes)",
            "Increased heart rate (norepinephrine effect — monitor cardiovascular status)",
            "Insomnia if taken late in day",
            "Constipation",
            "Elevated blood pressure (monitor BP weekly during titration)",
            "Psychological dependence risk with long-term use (dopamine mechanism)",
        ],
        "warning": "Cardiovascular risk — contraindicated in uncontrolled hypertension, arrhythmia, or structural heart disease. Not for use with other serotonergic drugs.",
        "storage": "Oral capsules/powder — room temperature, away from moisture and light. Stable 2+ years sealed.",
    },
    {
        "name": "5-Amino-1MQ",
        "full_name": "5-Amino-1-Methylquinolinium — NNMT Inhibitor",
        "tags": ["FAT LOSS", "NNMT INHIBITOR", "METABOLIC", "LONGEVITY", "EMERGING"],
        "what": (
            "5-Amino-1MQ is a small molecule inhibitor of NNMT (nicotinamide N-methyltransferase) — "
            "an enzyme overexpressed in fat tissue that suppresses fat cell metabolism. By blocking "
            "NNMT, 5-Amino-1MQ raises cellular NAD+ and SAM levels, reactivates metabolically dormant "
            "fat cells, and causes adipocytes to shrink without requiring caloric restriction. "
            "Preclinical research shows significant fat loss with preservation of lean mass."
        ),
        "benefits": [
            "Reduces fat cell size by reactivating metabolically dormant adipocytes",
            "Increases intracellular NAD+ — mimics caloric restriction at the cellular level",
            "Raises SAM (S-adenosylmethionine) levels — enhances methylation and epigenetic health",
            "Reduces adipogenesis — inhibits formation of new fat cells",
            "Preserves or increases lean muscle mass during fat loss",
            "Anti-aging properties via NAD+/sirtuin pathway activation",
            "Improved insulin sensitivity in fat tissue",
            "Shown to prevent diet-induced obesity in mouse models",
            "Synergistic with NMN/NR supplementation for NAD+ optimization",
        ],
        "how_it_works": (
            "NNMT consumes NAD+ precursors (specifically 1-methylnicotinamide from NAM) in fat tissue, "
            "keeping adipocytes in a metabolically suppressed state. 5-Amino-1MQ blocks this enzyme, "
            "freeing NAD+ precursors to restore cellular NAD+ levels. Higher NAD+ activates sirtuins "
            "and AMPK — triggering fat oxidation, mitochondrial biogenesis, and metabolic reactivation "
            "of adipose tissue."
        ),
        "doses": [
            ("50–200 mg", "Daily oral dose"),
            ("Morning", "Timing"),
            ("Daily", "Frequency"),
            ("8–12 weeks", "Cycle"),
        ],
        "protocols": [
            "<b>Starting dose:</b> 50–100 mg orally daily, assess response at 4 weeks.",
            "<b>Full dose:</b> 150–200 mg/day in split doses (AM + midday).",
            "<b>NAD+ Stack:</b> 5-Amino-1MQ + NMN 500 mg + Resveratrol 500 mg = synergistic NAD+ pathway.",
            "<b>Metabolic Stack:</b> 5-Amino-1MQ + MOTS-c + Berberine for multi-pathway fat loss.",
            "<b>Cycle:</b> 8–12 weeks on, 4–8 weeks off.",
        ],
        "side_effects": [
            "Limited human data — primarily preclinical (rodent) research",
            "GI discomfort reported by some users at higher doses",
            "Mild headache during initial adjustment period",
            "Generally well tolerated in current anecdotal human use",
            "Long-term safety data not yet available",
        ],
        "warning": "Very early-stage research compound. No completed human clinical trials. Use with appropriate caution and bloodwork monitoring.",
        "storage": "Oral powder or capsule — room temperature, dry, away from light. Hygroscopic — keep sealed.",
    },
    {
        "name": "GH",
        "full_name": "Human Growth Hormone (Somatropin / rHGH)",
        "tags": ["GROWTH HORMONE", "BODY RECOMP", "FAT LOSS", "ANTI-AGING", "RECOVERY"],
        "what": (
            "Human Growth Hormone (HGH/somatropin) is a 191-amino-acid peptide hormone secreted "
            "by the anterior pituitary. Pharmaceutical GH (recombinant human growth hormone / rHGH) "
            "is identical in structure to endogenous GH. It is used clinically for GH deficiency, "
            "short stature, HIV wasting, and Turner syndrome. In performance and anti-aging medicine, "
            "it is used for body recomposition, fat loss, recovery, and longevity."
        ),
        "benefits": [
            "Powerful lipolysis — promotes fat mobilization, especially visceral and abdominal fat",
            "Increases IGF-1 — drives muscle protein synthesis and recovery",
            "Significantly improves body composition (fat loss + lean mass over 3–6+ months)",
            "Enhanced recovery — reduces muscle soreness, accelerates tissue repair",
            "Improved sleep quality (endogenous GH is primarily released during deep sleep)",
            "Anti-aging: improved skin elasticity, collagen, hair quality",
            "Increased bone density with long-term use",
            "Improved insulin sensitivity at low doses (reversed at high doses)",
            "Enhanced cognitive function and energy",
            "Joint and connective tissue repair and maintenance",
        ],
        "how_it_works": (
            "GH acts on GH receptors in the liver to stimulate IGF-1 production, which drives anabolic "
            "effects in muscle and bone. Directly, GH activates lipolysis via hormone-sensitive lipase "
            "in adipocytes and counteracts insulin's actions in fat tissue. GH also upregulates protein "
            "synthesis independently of IGF-1 via JAK2-STAT5 signaling in muscle."
        ),
        "doses": [
            ("1–2 IU/day", "Anti-aging / TRT"),
            ("2–4 IU/day", "Body recomp"),
            ("4–6 IU/day", "Performance"),
            ("2–3x/day", "Advanced split"),
        ],
        "protocols": [
            "<b>Anti-Aging / Wellness:</b> 1–2 IU SC daily before bed. Monitor IGF-1 every 3 months.",
            "<b>Body Recomp:</b> 2–3 IU SC daily (morning fasted or split AM/PM).",
            "<b>Performance:</b> 4–6 IU/day split into 2 injections (pre-training + before bed).",
            "<b>Cycle length:</b> Minimum 3 months for meaningful body composition changes; 6+ months optimal.",
            "<b>Stack:</b> GH + testosterone + insulin (advanced) = elite muscle-building protocol.",
            "<b>Peptide alternative:</b> CJC-1295 + Ipamorelin stimulates endogenous GH at lower cost.",
        ],
        "side_effects": [
            "Water retention and edema (dose dependent — reduces over weeks)",
            "Carpal tunnel syndrome (tingling/numbness in hands — reduce dose if severe)",
            "Joint pain (arthralgias) — common early, usually transient",
            "Insulin resistance at higher doses — monitor fasting glucose",
            "Headache (intracranial pressure — rare at therapeutic doses)",
            "Potential organ growth (gut distension) at high sustained doses",
            "Theoretical cancer promotion risk (IGF-1 is mitogenic) — avoid in active cancer",
        ],
        "warning": "Pharmaceutical GH is expensive ($300–800+/month). Verify product via HPLC — counterfeit and underdosed GH is extremely common. Monitor IGF-1, fasting glucose, HbA1c every 3 months.",
        "storage": "Lyophilized vials: refrigerate 2–8°C. Reconstituted: refrigerate, use within 21–28 days. Never freeze reconstituted GH.",
    },
    {
        "name": "Semax",
        "full_name": "Semax — ACTH(4-7)PGP Neuropeptide",
        "tags": ["NOOTROPIC", "NEUROPROTECTIVE", "BDNF", "FOCUS", "COGNITIVE ENHANCEMENT"],
        "what": (
            "Semax is a synthetic heptapeptide analogue of ACTH(4-7), developed by the Institute of "
            "Molecular Genetics (Russian Academy of Sciences) in the 1980s–90s. It is approved in "
            "Russia for stroke, TBI, cognitive decline, ADHD, and nervous system disorders. "
            "It dramatically increases BDNF (brain-derived neurotrophic factor) and NGF (nerve growth "
            "factor) — two of the brain's most important neuroplasticity molecules. Legal and "
            "widely used internationally as a research nootropic."
        ),
        "benefits": [
            "Rapidly elevates BDNF and NGF — promotes neurogenesis and synaptic plasticity",
            "Enhances working memory, focus, and information processing speed",
            "Neuroprotective — shown effective in stroke, TBI, and ischemia recovery",
            "Reduces anxiety without sedation (anxiolytic without impairing cognition)",
            "Improves executive function, learning capacity, and attention",
            "Anti-fatigue — improves mental endurance and stamina under cognitive load",
            "Shown to improve ADHD symptoms without stimulant side effects",
            "Mood enhancement — BDNF is central to antidepressant mechanisms",
            "Potential neurological disease application: Parkinson's, Alzheimer's (early research)",
        ],
        "how_it_works": (
            "Semax is a melanocortin receptor (MCR) agonist that also directly stimulates BDNF and "
            "NGF gene expression in the brain. Its proline-glycine-proline (PGP) C-terminal extension "
            "makes it resistant to enzymatic degradation compared to native ACTH(4-7). It modulates "
            "the dopaminergic and serotonergic systems, and upregulates genes involved in synaptic "
            "transmission, neuroplasticity, and immune regulation in the CNS."
        ),
        "doses": [
            ("200–600 mcg", "SC injection"),
            ("100–200 mcg", "Starting dose"),
            ("1–2x daily", "Frequency"),
            ("5–10 days on/off", "Cycle pattern"),
        ],
        "protocols": [
            "<b>SC injection (standard):</b> 200–600 mcg SC, 1–2x daily. Inject abdomen or thigh.",
            "<b>Cycle protocol:</b> 5–10 days on, 5 days off to prevent receptor downregulation.",
            "<b>Cognitive enhancement:</b> 200 mcg SC 30 min before demanding work.",
            "<b>Recovery (TBI/stroke):</b> 600–900 mcg/day SC for 10–14 days under physician guidance.",
            "<b>Stack:</b> Semax (AM) + Selank (PM) — cognitive sharpness + anxiety control without stimulants.",
        ],
        "side_effects": [
            "Mild injection site irritation (transient)",
            "Mild headache at higher doses",
            "Transient fatigue after dose wears off (BDNF normalization)",
            "Rarely: mild mood elevation that can overshoot to slight agitation",
            "No known significant toxicity at therapeutic doses",
        ],
        "warning": "N-acetyl Semax (NA-Semax) and NA-Semax Amidate are more potent variants — start at lower doses. Refrigeration required — peptide degrades rapidly at room temperature.",
        "storage": "Reconstituted solution: refrigerate 2–8°C, use within 30 days. Lyophilized: -20°C freezer. Protect from light.",
    },
    {
        "name": "Selank",
        "full_name": "Selank — Tuftsin Analogue Anxiolytic Peptide",
        "tags": ["ANXIOLYTIC", "NOOTROPIC", "GABA-A", "ANTI-STRESS", "MOOD"],
        "what": (
            "Selank is a synthetic hexapeptide analogue of Tuftsin (a natural immunomodulatory "
            "tetrapeptide) developed by the Institute of Molecular Genetics, Russia. Approved in "
            "Russia for anxiety, depression, PTSD, and cognitive disorders. It produces anxiolytic "
            "effects comparable to benzodiazepines but without sedation, addiction potential, or "
            "cognitive impairment. Used clinically as a non-addictive anti-anxiety treatment."
        ),
        "benefits": [
            "Potent anxiolytic — reduces anxiety equivalent to low-dose benzodiazepines",
            "Zero addiction potential — no GABA receptor downregulation",
            "No sedation — anxiety reduction without cognitive blunting",
            "Antidepressant effects — shown to reduce symptoms of generalized anxiety and depression",
            "Improves memory consolidation and learning speed",
            "Immunomodulatory — enhances immune function (Tuftsin mechanism)",
            "Reduces stress-induced cognitive dysfunction",
            "Improves focus and productivity under stressful conditions",
            "Reduces alcohol withdrawal symptoms (GABA modulation)",
        ],
        "how_it_works": (
            "Selank modulates GABA-A receptor sensitivity (without direct binding), reducing anxiety "
            "via the GABAergic system. It also increases BDNF, boosts serotonin uptake regulation, "
            "and modulates enkephalins (endorphin-like peptides). Unlike benzodiazepines, it does not "
            "bind GABA-A receptors directly — explaining the lack of sedation, tolerance, and "
            "dependence. It also upregulates IL-6 and immune regulatory genes."
        ),
        "doses": [
            ("250–500 mcg", "SC injection"),
            ("100–200 mcg", "Starting dose"),
            ("1–3x daily", "Frequency"),
            ("2–4 weeks", "Typical cycle"),
        ],
        "protocols": [
            "<b>Anxiety / Acute stress:</b> 250 mcg SC, 2x daily (AM + PM). Inject abdomen or thigh.",
            "<b>Daily nootropic:</b> 250–500 mcg SC morning.",
            "<b>Semax + Selank stack:</b> Semax (morning, cognitive drive) + Selank (evening, wind-down).",
            "<b>Cycle:</b> 14–21 days on, 7 days off — prevents adaptation.",
            "<b>Clinical protocol:</b> 200 mcg SC daily for 10 days.",
        ],
        "side_effects": [
            "Mild injection site irritation (transient)",
            "Very mild sedation possible at high doses (rare)",
            "No addiction, withdrawal, or physical dependence reported",
            "Mild headache (rare)",
            "Generally considered one of the safest nootropic peptides available",
        ],
        "warning": "N-acetyl Selank (NA-Selank) is more potent — reduce dose by 30–50%. Keep reconstituted solution refrigerated — degrades at room temperature within days.",
        "storage": "Reconstituted solution: 2–8°C refrigerated, use within 30 days. Lyophilized powder: -20°C freezer long-term.",
    },
    {
        "name": "Oxytocin",
        "full_name": "Oxytocin — Neuropeptide Hormone",
        "tags": ["BONDING", "SEXUAL FUNCTION", "ORGASM", "SOCIAL", "ANTI-ANXIETY"],
        "what": (
            "Oxytocin is a 9-amino-acid neuropeptide produced in the hypothalamus and released "
            "by the posterior pituitary. Known as the 'bonding hormone' or 'love hormone,' it is "
            "released during physical touch, orgasm, childbirth, and breastfeeding. In performance "
            "and wellness contexts, exogenous oxytocin is used to enhance sexual experience, "
            "improve emotional connection, reduce social anxiety, accelerate orgasm, and support "
            "post-workout recovery via anti-inflammatory pathways."
        ),
        "benefits": [
            "Intensifies orgasm — facilitates and amplifies climax in men and women",
            "Increases emotional bonding and intimacy between partners",
            "Reduces social anxiety — improves confidence in social situations",
            "Enhances sexual arousal and physical sensitivity",
            "Anti-inflammatory — reduces cortisol and systemic inflammation post-exercise",
            "Accelerates wound healing (promotes myofibroblast activity)",
            "Improves trust, prosocial behavior, and relationship satisfaction",
            "Reduces compulsive eating and addictive behaviors (emerging data)",
            "Potential role in PTSD and social anxiety treatment",
        ],
        "how_it_works": (
            "Oxytocin binds oxytocin receptors (OTR) throughout the brain and body. In the limbic "
            "system, it activates reward circuits (dopamine release) and reduces amygdala reactivity "
            "to threatening stimuli — explaining its anxiolytic and bonding effects. In sexual function, "
            "it amplifies genital sensation and facilitates spinal ejaculatory/orgasm reflexes. "
            "Peripherally, it reduces inflammation via NF-κB pathway inhibition."
        ),
        "doses": [
            ("10–40 IU", "SC injection"),
            ("20 IU", "Standard dose"),
            ("20–30 min prior", "Timing"),
            ("As needed", "Frequency"),
        ],
        "protocols": [
            "<b>Sexual enhancement:</b> 20–40 IU SC injection 20–30 min before intimacy.",
            "<b>Social anxiety:</b> 20 IU SC 30–45 min before social event.",
            "<b>Post-workout recovery:</b> 20 IU SC post-training for anti-inflammatory effect.",
            "<b>Orgasm enhancement:</b> 20 IU for women 30 min pre-activity; pair with PT-141 for enhanced desire + intensity.",
            "<b>Note:</b> Take with a partner — pair-bonding effects work bidirectionally.",
        ],
        "side_effects": [
            "Mild injection site irritation (transient)",
            "Mild nausea at higher doses (>40 IU)",
            "Possible oxytocin 'crash' — emotional low after peak (dose dependent)",
            "In social contexts: can amplify negative emotions as well as positive (caution in contentious situations)",
            "Headache (rare)",
            "Uterine contractions at high doses — contraindicated in pregnancy",
        ],
        "warning": "Contraindicated during pregnancy — causes uterine contractions. Effects are bidirectional on emotion — may amplify negative social experiences as well as positive ones.",
        "storage": "Reconstituted solution: refrigerate 2–8°C, use within 30 days. Lyophilized: -20°C. Protect from light.",
    },
    {
        "name": "SLU-PP-332",
        "full_name": "SLU-PP-332 — ERRα/γ Agonist (Exercise Mimetic)",
        "tags": ["EXERCISE MIMETIC", "MITOCHONDRIAL", "ENDURANCE", "FAT LOSS", "EMERGING"],
        "what": (
            "SLU-PP-332 is a synthetic agonist of estrogen-related receptors alpha and gamma "
            "(ERRα and ERRγ) — nuclear receptors that regulate the expression of genes controlling "
            "mitochondrial biogenesis, oxidative metabolism, and energy expenditure. Published in "
            "the Journal of Medicinal Chemistry (2023), SLU-PP-332 increased endurance in mice by "
            "70% and promoted significant fat loss independent of diet or exercise. "
            "Among the most compelling emerging exercise mimetics in preclinical research."
        ),
        "benefits": [
            "70% increase in treadmill endurance capacity in preclinical studies (without training)",
            "Significant fat loss — promotes oxidative fat metabolism in skeletal muscle",
            "Mitochondrial biogenesis — increases mitochondrial density in muscle tissue",
            "Shifts muscle fiber type toward slow-twitch / oxidative (endurance-type)",
            "Reduces cardiac hypertrophy and improves heart failure markers in animal models",
            "Exercise mimetic — produces aerobic training adaptations without exercise",
            "Potential application in obesity, type 2 diabetes, heart failure, sarcopenia",
            "Synergistic with actual exercise training",
        ],
        "how_it_works": (
            "SLU-PP-332 activates ERRα and ERRγ — orphan nuclear receptors that normally respond "
            "to energy stress signals (like those generated by exercise). Activation of these receptors "
            "triggers expression of PGC-1α target genes — the master regulator of mitochondrial "
            "biogenesis. This results in increased mitochondrial number, enhanced fatty acid oxidation, "
            "muscle fiber type shifting, and improved cardiac function, all mimicking the cellular "
            "adaptations of sustained aerobic training."
        ),
        "doses": [
            ("N/A (human)", "No human trials yet"),
            ("Mouse: 30 mg/kg", "Preclinical dose"),
            ("~20–50 mg?", "Extrapolated human"),
            ("Daily SC/oral", "Route (unclear)"),
        ],
        "protocols": [
            "<b>IMPORTANT:</b> No established human protocol — all current use is self-experimentation.",
            "<b>Extrapolated from mice:</b> ~20–50 mg daily oral or SC (highly uncertain).",
            "<b>Stack context:</b> Often grouped with MOTS-c, BAM-15, 5-Amino-1MQ for metabolic/exercise mimetic protocols.",
            "<b>Monitoring:</b> Track cardiovascular markers, liver enzymes, and body composition changes.",
        ],
        "side_effects": [
            "Unknown in humans — no human clinical trial data available",
            "Preclinical: no significant toxicity observed at study doses",
            "Theoretical: ERR activation in cancer cells could promote proliferation (monitor)",
            "Unknown cardiovascular, renal, and hepatic effects in humans long-term",
        ],
        "warning": "Extreme caution — zero human clinical trial data. Among the most experimental compounds on this list. Use only with thorough understanding of the risk profile.",
        "storage": "Powder: room temperature, sealed, away from moisture and light. Long-term: -20°C freezer.",
    },
    {
        "name": "BAM-15",
        "full_name": "BAM-15 — Mitochondrial Protonophore Uncoupler",
        "tags": ["FAT LOSS", "MITOCHONDRIAL", "UNCOUPLER", "THERMOGENIC", "EMERGING"],
        "what": (
            "BAM-15 is a next-generation mitochondrial protonophore — a mitochondrial uncoupling "
            "agent that 'short-circuits' the electron transport chain, causing energy (calories) "
            "to be released as heat instead of being stored as ATP. Unlike DNP (2,4-dinitrophenol), "
            "BAM-15 acts only on the inner mitochondrial membrane and does not dissipate the plasma "
            "membrane electrochemical gradient — making it substantially safer in preclinical models. "
            "Published in Nature Communications (2020) — significant fat loss without diet change in mice."
        ),
        "benefits": [
            "Significant fat loss by converting stored energy to heat (thermogenesis)",
            "Preserves lean muscle mass during fat loss — unlike most caloric-restriction approaches",
            "Improves insulin sensitivity — reduces insulin resistance in obese mouse models",
            "Reduces liver fat (hepatic steatosis) and systemic inflammation",
            "No suppression of appetite — mechanism is purely thermogenic",
            "Improved mitochondrial efficiency markers",
            "Synergistic with exercise — enhances the uncoupling that occurs naturally during training",
            "Unlike DNP: does not raise core body temperature excessively (safer thermodynamic profile)",
        ],
        "how_it_works": (
            "BAM-15 is a proton carrier — it shuttles protons (H+) across the inner mitochondrial "
            "membrane down the electrochemical gradient, bypassing ATP synthase. This 'uncouples' "
            "oxidative phosphorylation from ATP production, so the energy from fuel oxidation is "
            "released as heat. The cell compensates by burning more fuel — creating a caloric deficit "
            "at rest. BAM-15 specificity for the mitochondrial membrane prevents the dangerous plasma "
            "membrane depolarization that makes DNP lethal at higher doses."
        ),
        "doses": [
            ("Unknown (human)", "No human trials"),
            ("Mouse: 50 mg/kg", "Preclinical dose"),
            ("Oral", "Likely route"),
            ("Research only", "Status"),
        ],
        "protocols": [
            "<b>CRITICAL:</b> No human dose established — BAM-15 is pure preclinical research compound.",
            "<b>Animal studies:</b> 50 mg/kg/day oral in mice — human equivalent roughly 4 mg/kg (HED).",
            "<b>Current status:</b> Not available from mainstream peptide vendors; strictly research compound.",
            "<b>If experimenting:</b> Cardiovascular monitoring (body temp, heart rate, blood pressure) is essential.",
            "<b>DNP comparison:</b> BAM-15 appears safer in animals but do NOT extrapolate DNP dosing.",
        ],
        "side_effects": [
            "Unknown in humans — no human safety data exists",
            "Preclinical: no significant body temperature elevation at study doses (unlike DNP)",
            "Theoretical: hyperthermia, tachycardia, sweating at high doses (uncoupler class effect)",
            "Theoretical: mitochondrial dysfunction if mechanism is overwhelmed",
            "DNP class risk: uncouplers at toxic doses cause fatal hyperthermia — extreme caution required",
        ],
        "warning": "⚠ EXTREME CAUTION — Research compound with zero human safety data. DNP, a related uncoupler, has caused multiple deaths. Do not extrapolate DNP experience to BAM-15. For research monitoring only.",
        "storage": "Research chemical — store per supplier instructions. Typically -20°C freezer, sealed.",
    },
    {
        "name": "Cagrilintide",
        "full_name": "Cagrilintide (CAG) — Long-Acting Amylin Analogue",
        "tags": ["WEIGHT LOSS", "AMYLIN", "APPETITE", "GLP-1 SYNERGY", "PHASE 3"],
        "what": (
            "Cagrilintide is a long-acting synthetic analogue of amylin — a pancreatic hormone "
            "co-secreted with insulin that signals satiety and slows gastric emptying. Developed by "
            "Novo Nordisk, it has a ~7-day half-life (once-weekly dosing) and is being studied in "
            "Phase 3 trials as CagriSema (cagrilintide 2.4 mg + semaglutide 2.4 mg). REDEFINE 1 "
            "trial data showed ~25% body weight reduction — potentially surpassing every approved "
            "weight loss drug on the market. Acts via a completely different receptor than GLP-1 agonists."
        ),
        "benefits": [
            "~25% body weight reduction in REDEFINE 1 trial (CagriSema combination at 68 weeks)",
            "Amylin receptor activation — entirely different pathway from GLP-1 agonists",
            "Powerful satiety signaling — reduces meal size and caloric intake",
            "Slows gastric emptying independently of GLP-1 mechanism",
            "Synergistic with semaglutide/tirzepatide — additive weight loss when combined",
            "Reduces postprandial glucose excursions",
            "Improves metabolic markers: lipids, blood pressure, HbA1c",
            "Once-weekly injection — excellent compliance profile",
            "May offer superior weight loss vs. GLP-1 monotherapy alone",
        ],
        "how_it_works": (
            "Cagrilintide is an amylin analogue — it binds amylin receptors (which are calcitonin "
            "receptor/RAMP complexes) in the area postrema and NTS (nucleus tractus solitarius) in "
            "the brainstem, as well as in the hypothalamus. This produces satiety signals "
            "independent of GLP-1R activation. The combination with semaglutide provides dual "
            "central + peripheral satiety and gastric slowing — explaining the additive weight loss "
            "seen in CagriSema trials that exceeds either drug alone."
        ),
        "doses": [
            ("0.16 mg/wk", "Starting dose"),
            ("2.4 mg/wk", "Target dose"),
            ("Once weekly", "Frequency"),
            ("16-week titration", "Ramp-up"),
        ],
        "protocols": [
            "<b>CagriSema titration:</b> 0.16 mg x4 wks → 0.35 mg x4 → 0.7 mg x4 → 1.4 mg x4 → 2.4 mg.",
            "<b>Monotherapy:</b> Same titration schedule — studied as standalone in Phase 2.",
            "<b>Combination:</b> Pair with semaglutide 2.4 mg/week for maximum fat loss (CagriSema protocol).",
            "<b>Protein/exercise:</b> 1g/lb protein + resistance training mandatory to preserve lean mass.",
            "<b>Compounded:</b> Available from select compounding pharmacies — verify HPLC purity.",
        ],
        "side_effects": [
            "Nausea (common, GI class effect — diminishes with titration)",
            "Injection site reactions (mild erythema, nodules at injection site more common than with GLP-1 alone)",
            "Constipation, diarrhea",
            "Hypoglycemia (in combination with insulin or sulfonylureas)",
            "Muscle mass loss during rapid weight loss phase (mitigate with training + protein)",
            "Fatigue during initial titration (common)",
        ],
        "warning": "Not yet FDA approved as of 2025 — NDA submission expected 2025–2026. Injection site nodules are more common than with semaglutide alone — rotate sites consistently.",
        "storage": "Refrigerate 2–8°C. Do not freeze. After first use: refrigerate, use within 28 days.",
    },
]


if __name__ == "__main__":
    print("=" * 60)
    print("  FBF PEPTIDE FLYER GENERATOR — BATCH 2")
    print(f"  {len(COMPOUNDS)} compounds — output: {OUTPUT_DIR}")
    print("=" * 60)
    for c in COMPOUNDS:
        build_flyer(c)
    print(f"\n✅ Done — {len(COMPOUNDS)} PDFs generated")
