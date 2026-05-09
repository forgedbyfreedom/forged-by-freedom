#!/usr/bin/env python3
"""
Forged By Freedom — Pinecone Ingest
-----------------------------------
Ingests corrected transcripts into Pinecone with rich metadata:
- channel: @handle extracted from path
- title: episode title parsed from filename
- text: actual chunk content (for retrieval)
- source: normalized source path
- video_id: YouTube video ID
"""

import os
import re
import sys
import time
import hashlib
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level up from ingest/)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

import tiktoken
from openai import OpenAI
from pinecone import Pinecone

# ---------------- CONFIG ----------------
BASE_DIR = Path(__file__).parent
CHANNELS_DIR = BASE_DIR / "channels"

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
EMBED_MODEL = "text-embedding-3-large"

CHUNK_TOKENS = 3000
EMBED_BATCH = 16
SLEEP_BETWEEN_BATCHES = 0.3

# ----------------------------------------

if not os.getenv("PINECONE_API_KEY"):
    raise RuntimeError("❌ PINECONE_API_KEY not set")

# OpenAI direct only — OpenRouter fallback was removed in phase_2B P5
# (OPENROUTER_API_KEY env was misconfigured as an sk-proj- OpenAI key).
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("❌ OPENAI_API_KEY required (OpenRouter fallback removed in phase_2B P5)")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
print("📡 Embeddings: OpenAI direct (text-embedding-3-large)")
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(INDEX_NAME)

tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))


def chunk_text(text: str):
    """Split text into chunks of CHUNK_TOKENS size."""
    tokens = tokenizer.encode(text)
    for i in range(0, len(tokens), CHUNK_TOKENS):
        yield tokenizer.decode(tokens[i:i + CHUNK_TOKENS])


def embed_batch(texts):
    """Embed a batch of texts using OpenAI."""
    res = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return [d.embedding for d in res.data]


def extract_channel(path: Path) -> str:
    """Extract @channel from file path."""
    for part in path.parts:
        if part.startswith("@"):
            return part
    return "unknown"


def extract_video_id(filename: str) -> str:
    """Extract YouTube video ID from filename like 'Title [VIDEO_ID].txt'."""
    match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', filename)
    return match.group(1) if match else ""


def extract_title(filename: str) -> str:
    """Extract episode title from filename."""
    # Remove extension
    name = filename.replace(".txt", "")
    # Remove video ID bracket
    name = re.sub(r'\s*\[[a-zA-Z0-9_-]{11}\]$', '', name)
    return name.strip()


def extract_speaker(title: str, channel: str) -> str:
    """Extract speaker name from title or channel."""
    # Common patterns: "Topic | Speaker Name" or "Speaker Name: Topic"

    # Pattern: "Title | Dr. Name" or "Title ｜ Dr. Name"
    pipe_match = re.search(r'[|｜]\s*(.+)$', title)
    if pipe_match:
        speaker = pipe_match.group(1).strip()
        # Check if it looks like a name (has Dr., PhD, etc. or capitalized words)
        if re.search(r'(Dr\.|PhD|MD|Professor|\b[A-Z][a-z]+\s+[A-Z])', speaker):
            return speaker

    # Pattern: "Dr. Name: Topic" or "Name, PhD: Topic"
    colon_match = re.match(r'^([^:]+(?:Dr\.|PhD|MD)[^:]*?):\s', title)
    if colon_match:
        return colon_match.group(1).strip()

    # Pattern: "Dr. Name on Topic" or "Name, PhD on Topic"
    on_match = re.match(r'^(.+?(?:Dr\.|PhD|MD).+?)\s+on\s+', title, re.IGNORECASE)
    if on_match:
        return on_match.group(1).strip()

    # Known channel-to-speaker mappings
    channel_speakers = {
        # Science-based fitness
        "@JeffNippard": "Jeff Nippard",
        "@RenaissancePeriodization": "Dr. Mike Israetel",
        "@BarbellMedicine": "Dr. Jordan Feigenbaum",
        "@StrongerByScience": "Greg Nuckols & Eric Trexler",
        "@HouseofHypertrophy": "House of Hypertrophy",
        "@Physionic": "Physionic",
        "@DataDrivenStrength": "Data Driven Strength",
        "@TrevorBachmeyer": "Trevor Bachmeyer",
        "@AthleanX": "Jeff Cavaliere",
        "@JeremyEthier": "Jeremy Ethier",
        "@SeanNalewanyj": "Sean Nalewanyj",
        "@ReviveStronger": "Revive Stronger",
        "@IronCulturePodcast": "Eric Helms & Omar Isuf",
        # PEDs / longevity
        "@MorePlatesMoreDates": "Derek (MPMD)",
        "@MPMD": "Derek (MPMD)",
        "@vigoroussteve": "Vigorous Steve",
        "@LeoandLongevity": "Leo Rex",
        "@anabolicbodybuilding": "Paul Barnett (Big Paul)",
        "@anabolicuniversity": "Anabolic University",
        "@CoachTrevorBlack": "Coach Trevor",
        "@TannerTatteredFAQ": "Tanner Tattered",
        "@realtattered": "Tanner Tattered",
        "@GeneticFreak": "Genetic Freak",
        # Health / longevity
        "@PeterAttiaMD": "Dr. Peter Attia",
        "@FoundMyFitness": "Dr. Rhonda Patrick",
        "@SiimLand": "Siim Land",
        "@ThomasDeLauerOfficial": "Thomas DeLauer",
        "@DrTyna": "Dr. Tyna",
        "@hubermanlab": "Dr. Andrew Huberman",
        "@DrGabrielleLyon": "Dr. Gabrielle Lyon",
        "@johnjewett3": "John Jewett",
        "@J3University": "John Jewett",
        # Female Hormone & Menopause Experts
        "@DrStacySims": "Dr. Stacy Sims",
        "@DrMindyPelz": "Dr. Mindy Pelz",
        "@melrobbins": "Mel Robbins",
        # Female Science-Based Fitness
        "@HollyBaxter": "Holly Baxter",
        "@SoheeFit": "Sohee Lee",
        "@LaurinConlin": "Laurin Conlin",
        "@megsquats": "Meg Gallagher",
        # Female Bodybuilding & Contest Prep
        "@ErinSternFitness": "Erin Stern",
        "@coachmusclenugget": "Britt Larson",
        # Women's Strength & Training
        "@CarolineGirvan": "Caroline Girvan",
        # Women's Mental Health & Nutrition
        "@LoriHarder": "Lori Harder",
        "@PickUpLimes": "Sadia Badiei",
        "@PaulSaladino": "Dr. Paul Saladino",
        "@DrEricBerg": "Dr. Eric Berg",
        "@WhatIveLearned": "What I've Learned",
        "@NutritionMadeSimple": "Nutrition Made Simple",
        "@KetoConnect": "Keto Connect",
        "@TheBioneer": "Adam Sinicki",
        "@ZDoggMD": "Dr. Zubin Damania",
        "@AliAbdaal": "Ali Abdaal",
        # Powerlifting / Strength
        "@eliteftsofficial": "EliteFTS",
        "@CalgaryBarbell": "Calgary Barbell",
        "@JuggernautTrainingSystems": "Chad Wesley Smith",
        "@AlanThrall": "Alan Thrall",
        "@OmarIsuf": "Omar Isuf",
        "@StanEfferding": "Stan Efferding",
        "@StefiCohen": "Stefi Cohen",
        # Strongman
        "@HafporJuliusBjornsson": "Hafthor Bjornsson",
        # BJJ
        "@Chewjitsu": "Nick Albin (Chewy)",
        "@JordanTeachesJiujitsu": "Jordan Preisinger",
        "@KnightJiuJitsu": "Knight Jiu Jitsu",
        # Mindset
        "@JockoPodcastOfficial": "Jocko Willink",
        # Bodybuilding
        "@GregDoucette": "Greg Doucette",
        "@ChrisBumstead": "Chris Bumstead",
        "@sam_sulek": "Sam Sulek",
        "@ThinkBIGBodybuilding": "Scott McNally, Dave Crosland & Skipp Hill",
        "@rxmuscle": "Dave Palumbo",
        "@mountainabordog1": "John Meadows",
        "@KaiGreene": "Kai Greene",
        "@BradleyMartyn": "Bradley Martyn",
        "@MattDoesFitness": "Matt Morsia",
        "@WillTennyson": "Will Tennyson",
        "@BuffDudes": "Buff Dudes",
        "@ScottHermanFitness": "Scott Herman",
        "@MikeThurston": "Mike Thurston",
        "@hanyrambod_FST7": "Hany Rambod",
        "@StephanieButtermore": "Stephanie Buttermore",
        "@RyanHumiston": "Ryan Humiston",
        "@BaldOmniMan": "Bald Omni Man",
        "@MassiveIron": "Steve Shaw",
        "@bodybuildingcom": "Bodybuilding.com",
        "@NicksStrengthandPower": "Nick Miller",
        "@HighLifeWorkout": "High Life Workout",
        "@BroScienceLife": "Dom Mazzetti",
        # Calisthenics
        "@FitnessFAQs": "FitnessFAQs",
        "@HybridCalisthenics": "Hampton Liu",
        "@THENX": "Chris Heria",
        # Movement / Rehab
        "@SquatUniversity": "Dr. Aaron Horschig",
        # Medical Education
        "@NinjaNerdOfficial": "Ninja Nerd",
        "@ArmandoHasudungan": "Armando Hasudungan",
        "@LecturioMedical": "Lecturio",
        "@MedCram": "Dr. Roger Seheult",
        "@AnatomyZone": "AnatomyZone",
        "@AnatomyBootCamp": "Anatomy Boot Camp",
        "@DrBeen": "Dr. Mobeen Syed",
        "@Kenhub": "Kenhub",
        "@muscleandmotion": "Muscle and Motion",
        "@DirtyMedicine": "Dirty Medicine",
        "@MedSimplified": "Med Simplified",
        "@MedSchoolInsiders": "Med School Insiders",
        "@SamWebster": "Sam Webster",
        "@Physeo": "Physeo",
        # Research / Journals
        "@PubMed": "PubMed Research",
        "@ClinicalTrials": "ClinicalTrials.gov",
        # Academic Institutions
        "@mitocw": "MIT OpenCourseWare",
        "@Stanford": "Stanford",
        "@StanfordMed": "Stanford Medicine",
        "@YaleCourses": "Yale",
        "@MayoClinic": "Mayo Clinic",
        "@ClevelandClinic": "Cleveland Clinic",
        "@JohnsHopkinsMedicine": "Johns Hopkins",
        "@UCLAHealth": "UCLA Health",
        "@DukeHealth": "Duke Health",
        "@PennMedicine": "Penn Medicine",
        "@MassGeneralHospital": "Mass General Hospital",
        "@VanderbiltHealth": "Vanderbilt Health",
        # Sports Science / Organizations
        "@ACEfitness": "ACE Fitness",
        "@ISSAPersonalTrainer": "ISSA",
        "@NasmOrgPersonalTrainer": "NASM",
        "@ClinicalAthlete": "Clinical Athlete",
        # Science Education
        "@3Blue1Brown": "3Blue1Brown",
        "@kurzgesagt": "Kurzgesagt",
        "@veritasium": "Veritasium",
        "@SciShow": "SciShow",
        "@Vsauce": "Vsauce",
        "@TED": "TED",
        "@TheRoyalInstitution": "Royal Institution",
        "@numberphile": "Numberphile",
        "@minutephysics": "MinutePhysics",
        "@ProfessorDaveExplains": "Professor Dave",
        # Medical Journals / Organizations
        "@ACPInternist": "ACP Internist",
        "@BMJupdates": "BMJ",
        # Sports Nutrition
        "@NutritionByKylie": "Kylie Sakaida RD",
        "@CarbonDietCoach": "Carbon Diet Coach",
        # Endocrinology
        "@DocGerryTan": "Dr. Gerry Tan",
        "@JayCampbell": "Jay Campbell",
        "@ThyroidUK": "Thyroid UK",
        # Sports Psychology
        "@PeakPerformanceSports": "Dr. Patrick Cohn",
        "@DrHaleyPerlus": "Dr. Haley Perlus",
        "@BrianCainPeak": "Brian Cain",
        # Performance Science
        "@TheReadyState": "Dr. Kelly Starrett",
        "@E3Rehab": "E3 Rehab",
        # Anti-Doping Organizations
        "@cleanprotocol": "Clean Protocol",
        # Bodybuilding Legends
        "@RonnieColeman8": "Ronnie Coleman",
        "@JayCutlerTV": "Jay Cutler",
        "@PhilHeath": "Phil Heath",
        "@ShawnRay": "Shawn Ray",
        "@LeeHaney": "Lee Haney",
        "@KaiGreene": "Kai Greene",
        # Mutant / Bodybuilding Media
        "@MutantOfficial": "Mutant",
        "@RonHarrisMuscle": "Ron Harris",
        "@GenerationIron": "Generation Iron",
        "@LondonReal": "London Real",
        # Medical Organizations
        "@NIH": "NIH",
        "@WHO": "WHO",
        "@JAMANetwork": "JAMA",
        "@ObesityMedicine": "Obesity Medicine Association",
        # TRT/Hormone Clinics
        "@TRTandHormoneOptimization": "TRT & Hormone Optimization",
        "@BalanceMyHormones": "Balance My Hormones",
        # Bodybuilding Historians
        "@NicksStrengthandPower": "Nick Miller",
        "@OldSchoolLabs": "Old School Labs",
        "@VintageGenetics": "Vintage Genetics",
        # Contest Prep Coaches
        # Bodybuilding Podcasts
        "@MuscleIntelligence": "Ben Pakulski",
        "@MarkBellsPowerProject": "Mark Bell",
        "@RealBodybuilding": "Fouad Abiad",
        "@FouadAbiad": "Fouad Abiad",
        "@BroChat": "Bro Chat",
        # Current Pro Bodybuilders
        # Supplement Science
        "@ExamineCom": "Examine.com",
        # Compound Reference Databases
        # FBF Proprietary Content
        "@ForgedByFreedom": "Forged by Freedom",
        "@PrecisionBloodwork": "Precision Bloodwork by Wendy & Bryan Antonelli",
        # Compound Reference Databases
        "@ThinkSteroids": "ThinkSteroids Reference Database",
        "@AnabolicSteroids_UK": "Anabolic Steroids UK - IPED Reference",
        # Sexual Health / HRT / Female Hormones
        "@MenopauseSociety": "The Menopause Society",
        "@SexWithDrJess": "Sex With Dr. Jess",
        "@NickPanay": "Nick Panay - HRT Specialist",
        "@SexHealthMatters": "Sex Health Matters",
        "@DrMaryClaire": "Dr. Mary Claire Haver",
        "@menopause_doctor": "The Menopause Doctor",
        "@BalanceApp": "Balance Menopause",
        "@NewsonHealth": "Newson Health - Dr. Louise Newson",
        "@intimacycoordinator": "Intimacy Coordinator",
        "@DrJenGunter": "Dr. Jen Gunter",
        "@WomensHealthMag": "Women's Health Magazine",
        "@DrSherry": "Dr. Sherry Ross - Women's Sexual Health",
        "@DrKellyMcCann": "Dr. Kelly McCann - Sexual Medicine",
        "@urologyCareFoundation": "Urology Care Foundation",
        "@AmerUrological": "American Urological Association",
        "@SexualWellbeing": "Sexual Wellbeing",
        "@MensSexualHealth": "Men's Sexual Health",
        "@ErgoLog": "Ergo-Log Research Database",
        # Psychedelics / Alternative Medicine
        "@PsychedelicsToday": "Psychedelics Today",
        "@psymposia": "Psymposia",
        "@maps_org": "MAPS - Multidisciplinary Association for Psychedelic Studies",
        "@beckleyfoundation": "Beckley Foundation",
        "@MyceliumTV": "Mycelium TV",
        "@DrMatthewJohnson": "Dr. Matthew Johnson",
        "@psychedelicmedicine": "Psychedelic Medicine",
        "@NIMHgov": "National Institute of Mental Health",
        # Biohacking / Longevity
        "@DaveAspreyBPR": "Dave Asprey",
        "@BiohackersWorld": "Biohackers World",
        "@JohnsHopkinsMedicine": "Johns Hopkins Medicine",
        # Performance Science
        "@Physionic": "Nick Norwitz PhD",
        "@TRTandHormoneOptimization": "Jay Campbell",
        "@BarBend": "BarBend",
        "@InsideBodybuilding": "Inside Bodybuilding",
        "@drandygalpin": "Dr. Andy Galpin",
        "@BretContreras1": "Bret Contreras",
        "@joeydsmith": "Joey Smith - NeoBarbell",
        "@nutritionfactsorg": "NutritionFacts.org",
        # Dosing Guides / Reference / Cycle Design
        "@DanDuchaine": "Dan Duchaine",
        "@CycleDesignGuide": "Forged by Freedom Cycle Design Guide",
        # Vendor Testing / Lab Results
        "@Janoshik": "Janoshik Analytical",
        # Harm Reduction / PED Education
        "@SethFeroce": "Seth Feroce",
        "@RussoLifts": "Russo Lifts",
        "@EnhancedInfo": "Enhanced Info",
        "@GearGoblin": "Gear Goblin",
        "@HarmReductionGuides": "Harm Reduction Guide",
    }

    if channel in channel_speakers:
        return channel_speakers[channel]

    return "unknown"


def get_namespace(channel: str, path: Path) -> str:
    """Determine namespace based on channel or path."""
    # Check if it's in a specific namespace folder
    path_str = str(path).lower()

    # Map channels to namespaces
    namespace_map = {
        # Research (highest priority)
        "@PubMed": "research_primary",
        "@ClinicalTrials": "research_primary",
        "@BMJupdates": "research_primary",
        # ThinkBig Priority
        "@ThinkBIGBodybuilding": "thinkbig_priority",
        "@rxmuscle": "rxmuscle_priority",
        # Medical Education
        "@NinjaNerdOfficial": "medical_education",
        "@LecturioMedical": "medical_education",
        "@MedCram": "medical_education",
        "@Kenhub": "medical_education",
        "@DrBeen": "medical_education",
        "@Physeo": "medical_education",
        "@AnatomyZone": "medical_education",
        "@ArmandoHasudungan": "medical_education",
        "@muscleandmotion": "medical_education",
        # Academic / Hospitals
        "@mitocw": "academic",
        "@Stanford": "academic",
        "@StanfordMed": "academic",
        "@YaleCourses": "academic",
        "@MayoClinic": "medical_primary",
        "@ClevelandClinic": "medical_primary",
        "@JohnsHopkinsMedicine": "medical_primary",
        "@UCLAHealth": "medical_primary",
        "@DukeHealth": "medical_primary",
        "@PennMedicine": "medical_primary",
        "@MassGeneralHospital": "medical_primary",
        # PED / Anabolic
        "@MorePlatesMoreDates": "anabolic_bodybuilding_priority",
        "@MPMD": "anabolic_bodybuilding_priority",
        "@GregDoucette": "anabolic_bodybuilding_priority",
        "@vigoroussteve": "anabolic_bodybuilding_priority",
        "@LeoandLongevity": "anabolic_bodybuilding_priority",
        "@CoachTrevorBlack": "anabolic_bodybuilding_priority",
        "@anabolicbodybuilding": "anabolic_bodybuilding_priority",
        "@anabolicuniversity": "anabolic_bodybuilding_priority",
        # Peptide Experts (priority namespace)
        "@TrevorBachmeyer": "peptide_priority",
        "@drtrevorbachmeyer": "peptide_priority",
        "@JayCampbell": "peptide_priority",
        # Biohacking / Health / Longevity
        "@FoundMyFitness": "biohacking",
        "@hubermanlab": "biohacking",
        "@PeterAttiaMD": "medical_primary",
        "@DrGabrielleLyon": "medical_primary",
        "@HighIntensityHealth": "biohacking",
        "@BryanJohnson": "biohacking",
        "@DavidSinclair": "biohacking",
        "@DrBradStanfield": "biohacking",
        "@Physionic": "biohacking",
        # PED Pharmacology
        "@SethFeroce": "anabolic_bodybuilding_priority",
        "@MilosSarcev": "anabolic_bodybuilding_priority",
        # Sports Science / Hypertrophy
        "@DrAndyGalpin": "sports_nutrition",
        "@BradSchoenfeldPhD": "sports_nutrition",
        "@OmarIsuf": "sports_nutrition",
        "@MuscleIntelligence": "anabolic_bodybuilding_priority",
        # Contest Prep
        "@HypertrophyCoach": "anabolic_bodybuilding_priority",
        "@MattJansen": "anabolic_bodybuilding_priority",
        # Hormone / Endocrinology
        "@BalanceMyHormones": "endocrinology",
        "@DrAkshayJainMD": "endocrinology",
        "@johnjewett3": "anabolic_bodybuilding_priority",
        "@J3University": "anabolic_bodybuilding_priority",
        # Female Hormone & Menopause Experts
        "@DrStacySims": "female_health_priority",
        "@DrMindyPelz": "female_health_priority",
        # Female Science-Based Fitness
        "@HollyBaxter": "female_health_priority",
        "@SoheeFit": "female_health_priority",
        "@LaurinConlin": "female_health_priority",
        "@megsquats": "female_health_priority",
        # Female Bodybuilding
        "@ErinSternFitness": "female_health_priority",
        "@coachmusclenugget": "female_health_priority",
        "@CarolineGirvan": "female_health_priority",
        "@BarbellMedicine": "medical_primary",
        "@DrEricBerg": "biohacking",
        "@SiimLand": "biohacking",
        # Sports Nutrition
        "@JeffNippard": "sports_nutrition",
        "@RenaissancePeriodization": "sports_nutrition",
        "@StrongerByScience": "sports_nutrition",
        # Sports Science
        "@ACEfitness": "sports_science",
        # Sports Nutrition (expanded)
        "@NutritionByKylie": "sports_nutrition",
        "@CarbonDietCoach": "sports_nutrition",
        # Peptides & GLP-1
        "@DrSeedman": "peptides",
        "@JayCampbell": "peptides",
        "@PeptidesScienceDaily": "peptides",
        # Endocrinology
        "@DocGerryTan": "endocrinology",
        "@ThyroidUK": "endocrinology",
        # Sports Psychology
        "@PeakPerformanceSports": "sports_psych",
        "@DrHaleyPerlus": "sports_psych",
        "@BrianCainPeak": "sports_psych",
        # Sports Psychology / Mindset
        "@JockoPodcastOfficial": "sports_psych",
        # Performance Science
        "@TheReadyState": "performance_science",
        "@E3Rehab": "performance_science",
        # Anti-Doping / Testing Organizations
        "@cleanprotocol": "anti_doping",
        # Bodybuilding Legends
        "@RonnieColeman8": "bodybuilding_legends",
        "@JayCutlerTV": "bodybuilding_legends",
        "@PhilHeath": "bodybuilding_legends",
        "@ShawnRay": "bodybuilding_legends",
        "@LeeHaney": "bodybuilding_legends",
        "@KaiGreene": "bodybuilding_legends",
        # Mutant / Bodybuilding Media
        "@MutantOfficial": "bodybuilding_media",
        "@RonHarrisMuscle": "bodybuilding_media",
        "@GenerationIron": "bodybuilding_media",
        "@LondonReal": "interviews",
        # Government / Medical Organizations
        "@NIH": "medical_primary",
        "@WHO": "medical_primary",
        "@JAMANetwork": "research_primary",
        "@ObesityMedicine": "medical_primary",
        # TRT/Hormone Optimization
        "@TRTandHormoneOptimization": "endocrinology",
        "@BalanceMyHormones": "endocrinology",
        # Bodybuilding Historians
        "@NicksStrengthandPower": "bodybuilding_history",
        "@OldSchoolLabs": "bodybuilding_history",
        "@VintageGenetics": "bodybuilding_history",
        # Contest Prep Coaches
        # Bodybuilding Podcasts
        "@MuscleIntelligence": "bodybuilding_media",
        "@MarkBellsPowerProject": "bodybuilding_media",
        "@RealBodybuilding": "bodybuilding_media",
        "@FouadAbiad": "bodybuilding_media",
        "@BroChat": "bodybuilding_media",
        # Current Pro Bodybuilders
        # Supplement Science
        "@ExamineCom": "sports_nutrition",
        # Compound Reference Databases
        # FBF Proprietary Content
        "@ForgedByFreedom": "cycle_design_guides",
        "@PrecisionBloodwork": "cycle_design_guides",
        # Compound Reference Databases
        "@ThinkSteroids": "anabolic_bodybuilding_priority",
        "@AnabolicSteroids_UK": "anabolic_bodybuilding_priority",
        # Sexual Health / HRT / Female Hormones
        "@MenopauseSociety": "medical_primary",
        "@SexWithDrJess": "medical_primary",
        "@NickPanay": "medical_primary",
        "@SexHealthMatters": "medical_primary",
        "@DrMaryClaire": "medical_primary",
        "@menopause_doctor": "medical_primary",
        "@BalanceApp": "medical_primary",
        "@NewsonHealth": "medical_primary",
        "@intimacycoordinator": "medical_primary",
        "@DrJenGunter": "medical_primary",
        "@WomensHealthMag": "medical_primary",
        "@DrSherry": "medical_primary",
        "@DrKellyMcCann": "medical_primary",
        "@urologyCareFoundation": "medical_primary",
        "@AmerUrological": "medical_primary",
        "@SexualWellbeing": "medical_primary",
        "@MensSexualHealth": "medical_primary",
        "@ErgoLog": "sports_nutrition",
        # Psychedelics / Alternative Medicine
        "@PsychedelicsToday": "medical_primary",
        "@psymposia": "medical_primary",
        "@maps_org": "medical_primary",
        "@beckleyfoundation": "medical_primary",
        "@MyceliumTV": "medical_primary",
        "@DrMatthewJohnson": "medical_primary",
        "@psychedelicmedicine": "medical_primary",
        "@NIMHgov": "medical_primary",
        # Biohacking / Longevity
        "@DaveAspreyBPR": "biohacking",
        "@BiohackersWorld": "biohacking",
        "@JohnsHopkinsMedicine": "medical_primary",
        # Performance Science
        "@Physionic": "sports_nutrition",
        "@TRTandHormoneOptimization": "medical_primary",
        "@BarBend": "sports_nutrition",
        "@InsideBodybuilding": "anabolic_bodybuilding_priority",
        "@drandygalpin": "medical_primary",
        "@BretContreras1": "sports_nutrition",
        "@joeydsmith": "sports_nutrition",
        "@nutritionfactsorg": "sports_nutrition",
        # Dosing Guides / Reference / Cycle Design
        "@DanDuchaine": "anabolic_bodybuilding_priority",
        "@CycleDesignGuide": "cycle_design_guides",
        # Vendor Testing / Lab Results
        "@Janoshik": "vendor_testing",
        # Harm Reduction / PED Education
        "@SethFeroce": "harm_reduction",
        "@RussoLifts": "harm_reduction",
        "@EnhancedInfo": "harm_reduction",
        "@GearGoblin": "harm_reduction",
        "@HarmReductionGuides": "harm_reduction",
    }

    if channel in namespace_map:
        return namespace_map[channel]

    return "transcripts"


def delete_channel_vectors(channel, namespace):
    """Delete all existing vectors for a channel in a namespace before re-ingesting.
    Prevents duplicate/stale vectors when re-running ingest for the same channel.
    """
    print(f"🗑️  Deleting existing vectors for {channel} in namespace '{namespace}'...")

    # Use list+delete approach since Pinecone doesn't support delete-by-metadata-filter
    # on all plans. We'll list vectors with a prefix scan.
    try:
        # Try metadata filter delete (works on Standard+ plans)
        index.delete(
            filter={"channel": {"$eq": channel}},
            namespace=namespace
        )
        print(f"   ✅ Deleted existing {channel} vectors from '{namespace}'")
    except Exception as e:
        # If filter delete isn't supported, fall back to listing and deleting by ID
        print(f"   ⚠️  Filter delete not supported ({e}), skipping pre-delete")
        print(f"   ℹ️  Vectors will be upserted (overwritten if same ID)")


def ingest(only_channels=None):
    """Main ingest function with rich metadata.

    Args:
        only_channels: Optional list of channel names (e.g. ['@ThinkBIGBodybuilding'])
                       to ingest. If None, ingests all channels.
    """
    print("\n🔍 INGEST STARTUP")
    print(f"• CHANNELS_DIR: {CHANNELS_DIR}")
    print(f"• Pinecone index: {INDEX_NAME}")
    print(f"• Embedding model: {EMBED_MODEL}")
    print(f"• Chunk tokens: {CHUNK_TOKENS}")
    if only_channels:
        print(f"• Targeting channels: {', '.join(only_channels)}")

    # Get all txt files, excluding master transcripts
    txt_files = [
        f for f in CHANNELS_DIR.rglob("*.txt")
        if not f.name.startswith("master_transcript")
        and not f.name.startswith(".")
    ]

    # Filter to specific channels if requested
    if only_channels:
        txt_files = [f for f in txt_files if extract_channel(f) in only_channels]

    total_files = len(txt_files)
    print(f"• Episodes to ingest: {total_files}")

    # Dedup: delete existing vectors for targeted channels before re-ingesting
    if only_channels:
        cleaned = set()
        for txt in txt_files:
            ch = extract_channel(txt)
            ns = get_namespace(ch, txt)
            key = f"{ch}:{ns}"
            if key not in cleaned:
                delete_channel_vectors(ch, ns)
                cleaned.add(key)

    print("🚀 BEGIN INGEST\n")

    episode_count = 0
    word_count = 0
    chunk_count = 0
    errors = []

    for txt in txt_files:
        try:
            text = txt.read_text(errors="ignore").strip()
            if not text:
                continue

            words = len(text.split())
            chunks = list(chunk_text(text))

            # Extract metadata
            channel = extract_channel(txt)
            title = extract_title(txt.name)
            video_id = extract_video_id(txt.name)
            speaker = extract_speaker(title, channel)
            namespace = get_namespace(channel, txt)
            source = f"transcripts/{channel}/{txt.name}"

            vectors = []
            for chunk_idx, chunk_content in enumerate(chunks):
                # Create unique ID from content hash
                vec_id = hashlib.sha1(
                    f"{channel}:{video_id}:{chunk_idx}:{chunk_content[:100]}".encode()
                ).hexdigest()

                vectors.append({
                    "id": vec_id,
                    "values": None,  # Will be filled by embedding
                    "metadata": {
                        "text": chunk_content[:8000],  # Pinecone metadata limit
                        "channel": channel,
                        "speaker": speaker,
                        "title": title,
                        "source": source,
                        "video_id": video_id,
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                        "word_count": words
                    }
                })

            # Embed and upsert in batches
            for i in range(0, len(vectors), EMBED_BATCH):
                batch = vectors[i:i + EMBED_BATCH]
                texts_to_embed = [v["metadata"]["text"] for v in batch]

                embeddings = embed_batch(texts_to_embed)

                for vec, emb in zip(batch, embeddings):
                    vec["values"] = emb

                # Upsert to namespace
                index.upsert(vectors=batch, namespace=namespace)
                chunk_count += len(batch)
                time.sleep(SLEEP_BETWEEN_BATCHES)

            episode_count += 1
            word_count += words

            print(f"✅ [{episode_count}/{total_files}] {channel} | {speaker} | {title[:40]}... | {len(chunks)} chunks")

        except Exception as e:
            errors.append((txt.name, str(e)))
            print(f"❌ Failed: {txt.name} — {e}")

    print("\n" + "=" * 60)
    print("✅ INGEST COMPLETE")
    print(f"📚 Episodes: {episode_count:,}")
    print(f"🧩 Chunks: {chunk_count:,}")
    print(f"📝 Words: {word_count:,}")

    if errors:
        print(f"\n⚠️  {len(errors)} errors:")
        for name, err in errors[:10]:
            print(f"   • {name}: {err}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--channels", nargs="+", help="Only ingest specific channels (e.g. @ThinkBIGBodybuilding @rxmuscle)")
    args = parser.parse_args()
    ingest(only_channels=args.channels)
