from pathlib import Path

BASE = Path(__file__).parent
SOURCE = BASE / "medical_textbook_manifest.txt"
OUT = BASE / "medical_textbook_expanded.txt"

EXPANSIONS = {
    "cell_biology": [
        "Satellite_Cell_Activation",
        "Myonuclear_Addition",
        "Muscle_Fiber_Types",
        "Actin_Myosin_Crossbridge",
        "Autophagy_in_Muscle",
        "Cellular_Mechanosensing",
        "Hippo_YAP_TAZ_Pathway"
    ],
    "bioenergetics": [
        "ATP_Resynthesis_Rates",
        "Creatine_Kinase_System",
        "Lactate_Shuttle",
        "Mitochondrial_Biogenesis",
        "Fuel_Utilization_Exercise",
        "Fatty_Acid_Oxidation"
    ],
    "endocrinology": [
        "Hypothalamic_Pituitary_Gonadal_Axis",
        "Hypothalamic_Pituitary_Thyroid_Axis",
        "Insulin_Signaling_Pathway",
        "Cortisol_and_Stress_Response",
        "Sex_Hormone_Binding_Globulin",
        "Aromatase_Activity",
        "IGF1_MTOR_Crosstalk"
    ],
    "longevity": [
        "Sarcopenic_Obesity",
        "Inflammatory_Cytokines",
        "NAD_Plus_Metabolism",
        "Telomere_Dynamics",
        "Cellular_Senescence",
        "Mitophagy",
        "Hormonal_Aging"
    ],
    "ped_mechanisms": [
        "Androgen_Receptor_Translocation",
        "Myostatin_Inhibition",
        "Erythropoietin_Response",
        "Collagen_Synthesis",
        "Neural_Drive_Enhancement",
        "Protein_Synthesis_Rates",
        "Recovery_Modulation"
    ]
}

with SOURCE.open() as f:
    sections = [line.strip() for line in f if line.strip()]

out = []

current = None
for line in sections:
    if line.startswith("["):
        current = line.strip("[]")
        out.append(f"\n[{current}]")
    else:
        out.append(line)
        for extra in EXPANSIONS.get(current, []):
            out.append(extra)

OUT.write_text("\n".join(out))
print(f"✅ Expanded manifest written to {OUT}")

