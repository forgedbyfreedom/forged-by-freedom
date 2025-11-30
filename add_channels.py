#!/usr/bin/env python3
import os

"""
📦 add_channels.py
This script creates folders for new YouTube channels you want the transcript system to track.
Simply add channel handles (e.g., @JayCutlerTV) to the list below.
Your rebuild pipeline will automatically detect and process them.
"""

# === Add new channels here ===
channels = [
    # 🏋️ Classic Bodybuilding & Coaching
    "@JayCutlerTV",
    "@ChrisCormierTheRealDeal",
    "@DennisJamesTV",
    "@MuscularDevelopment",
    "@FouadAbiadMedia",
    "@JohnMeadows",
    "@BenPakulskiMI40",
    "@GregDoucetteIFBBPro",
    "@NickTrigiliBodybuildingandBS",
    "@BodybuildingCom",

    # 💉 PEDs, Peptides, and Hormone Education
    "@LeoAndLongevity",
    "@MorePlatesMoreDates",
    "@TeamEvilGSP",
    "@AnabolicDoc",
    "@VictorBlackMasterClass",
    "@DrTonyHuge",
    "@CoachTrevor",
    "@TheMuscleMentors",

    # 🧠 Sports Psychology & Mindset
    "@JockoPodcast",
    "@AndrewHubermanLab",
    "@DavidGoggins",
    "@DrJoeDispenza",
    "@SimonSinek",
    "@TomBilyeu",

    # 🥩 Sports Nutrition & Performance Science
    "@HubermanLabClips",
    "@StanEfferding",
    "@LayneNorton",
    "@AlanAragon",
    "@ThomasDeLauer",
    "@DrAndyGalpin",
    "@DrStacySims",

    # 🧍‍♀️ Wellness, Recovery, Longevity
    "@RhondaPatrick",
    "@GabrielleLyon",
    "@PeterAttiaMD",
    "@FoundMyFitness",

    # 🎓 Coaching Credentials & Education
    "@NASMorgPersonalTrainer",
    "@ISSAonline",
    "@ACEfitness",
    "@PrecisionNutrition",
    "@NESTAfitness",
    "@CSCSNationalStrength",
    "@DrMikeTuchscherer",

    # ⚡ High-Value Additions
    "@SquatUniversity",
    "@HybridPerformanceMethod",
    "@JordanSyatt",
    "@JeffCavaliereATHLEANX",
    "@EvolveTrainingSystems",
]

# === Core logic ===
root = os.getcwd()
print(f"📁 Working directory: {root}")
created = 0

for ch in channels:
    path = os.path.join(root, ch)
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        print(f"✅ Created folder for {ch}")
        created += 1
    else:
        print(f"⚙️ Already exists: {ch}")

print(f"\n🎯 Done. {created} new channel folders created successfully.")
print("Next: run → python auto_rebuild_all_v2.py to include them in your transcript sync.")
