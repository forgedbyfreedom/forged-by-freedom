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

# Use OpenAI directly for embeddings (cheaper, more reliable, no OpenRouter middleman)
if os.getenv("OPENAI_API_KEY"):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    print("📡 Embeddings: OpenAI direct")
elif os.getenv("OPENROUTER_API_KEY"):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )
    print("📡 Embeddings: via OpenRouter (set OPENAI_API_KEY to go direct)")
else:
    raise RuntimeError("❌ Need OPENAI_API_KEY or OPENROUTER_API_KEY")
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
        "@GregNuckols": "Greg Nuckols",
        "@TrevorBachmeyer": "Trevor Bachmeyer",
        "@AthleanX": "Jeff Cavaliere",
        "@JeremyEthier": "Jeremy Ethier",
        "@SeanNalewanyj": "Sean Nalewanyj",
        "@MennoHenselmans": "Menno Henselmans",
        "@EricHelms3DMJ": "Dr. Eric Helms",
        "@3DMuscleJourney": "3D Muscle Journey",
        "@AlbertNunez3DMJ": "Alberto Nunez",
        "@ReviveStronger": "Revive Stronger",
        "@IronCulturePodcast": "Eric Helms & Omar Isuf",
        # PEDs / longevity
        "@MorePlatesMoreDates": "Derek (MPMD)",
        "@MPMD": "Derek (MPMD)",
        "@vigoroussteve": "Vigorous Steve",
        "@LeoandLongevity": "Leo Rex",
        "@AnabolicDoc": "Dr. Thomas O'Connor",
        "@AnabolicTV": "Anabolic TV",
        "@anabolicbodybuilding": "Paul Barnett (Big Paul)",
        "@anabolicuniversity": "Anabolic University",
        "@EnhancedAthlete": "Enhanced Athlete",
        "@TonyHuge": "Tony Huge",
        "@CoachTrevorBlack": "Coach Trevor",
        "@TannerTatteredFAQ": "Tanner Tattered",
        "@realtattered": "Tanner Tattered",
        "@bostin_loyd": "Bostin Loyd",
        "@GeneticFreak": "Genetic Freak",
        "@GeneticallyShredded": "Genetically Shredded",
        # Health / longevity
        "@PeterAttiaMD": "Dr. Peter Attia",
        "@FoundMyFitness": "Dr. Rhonda Patrick",
        "@SiimLand": "Siim Land",
        "@ThomasDeLauer": "Thomas DeLauer",
        "@ThomasDeLauerOfficial": "Thomas DeLauer",
        "@DrTyna": "Dr. Tyna",
        "@hubermanlab": "Dr. Andrew Huberman",
        "@AndrewHuberman": "Dr. Andrew Huberman",
        "@DrGabrielleLyon": "Dr. Gabrielle Lyon",
        "@johnjewett3": "John Jewett",
        "@J3University": "John Jewett",
        # Female Hormone & Menopause Experts
        "@DrStacySims": "Dr. Stacy Sims",
        "@drmaryclairehaver": "Dr. Mary Claire Haver",
        "@DrMindyPelz": "Dr. Mindy Pelz",
        "@melrobbins": "Mel Robbins",
        # Female Science-Based Fitness
        "@HollyBaxter": "Holly Baxter",
        "@SoheeFit": "Sohee Lee",
        "@LaurinConlin": "Laurin Conlin",
        "@megsquats": "Meg Gallagher",
        # Female Bodybuilding & Contest Prep
        "@teamlocofit": "Team LoCoFit",
        "@JulieLohre": "Julie Lohre",
        "@AshleyKaltwasser": "Ashley Kaltwasser",
        "@ErinSternFitness": "Erin Stern",
        "@coachmusclenugget": "Britt Larson",
        # Women's Strength & Training
        "@CarolineGirvan": "Caroline Girvan",
        "@KatieCrewe": "Katie Crewe",
        "@KristyHawkins": "Kristy Hawkins",
        # Women's Mental Health & Nutrition
        "@LoriHarder": "Lori Harder",
        "@AbbeySharp": "Abbey Sharp",
        "@PickUpLimes": "Sadia Badiei",
        "@PaulSaladino": "Dr. Paul Saladino",
        "@CarnivoreMD": "Dr. Paul Saladino",
        "@BenGreenfield": "Ben Greenfield",
        "@DrEricBerg": "Dr. Eric Berg",
        "@DrEricBergDC": "Dr. Eric Berg",
        "@WhatIveLearned": "What I've Learned",
        "@NutritionFacts": "Dr. Michael Greger",
        "@NutritionMadeSimple": "Nutrition Made Simple",
        "@KetoConnect": "Keto Connect",
        "@TheBioneer": "Adam Sinicki",
        "@DaveFeldman": "Dave Feldman",
        "@GojiManUK": "GojiMan",
        "@ZDoggMD": "Dr. Zubin Damania",
        "@AliAbdaal": "Ali Abdaal",
        # Powerlifting / Strength
        "@eliteftsofficial": "EliteFTS",
        "@CalgaryBarbell": "Calgary Barbell",
        "@JuggernautTrainingSystems": "Chad Wesley Smith",
        "@WestsideBarbell": "Louie Simmons",
        "@MarkBellSlingShot": "Mark Bell",
        "@SuperTrainingGym": "Mark Bell",
        "@AlanThrall": "Alan Thrall",
        "@OmarIsuf": "Omar Isuf",
        "@BenPollack": "Ben Pollack",
        "@StanEfferding": "Stan Efferding",
        "@StefiCohen": "Stefi Cohen",
        "@LarrywheelsOFFICIAL": "Larry Wheels",
        # Strongman
        "@EddiehallStrongman": "Eddie Hall",
        "@BrianShawStrong": "Brian Shaw",
        "@HafporJuliusBjornsson": "Hafthor Bjornsson",
        # BJJ
        "@Chewjitsu": "Nick Albin (Chewy)",
        "@JordanTeachesJiujitsu": "Jordan Preisinger",
        "@KnightJiuJitsu": "Knight Jiu Jitsu",
        "@BJJFanatics": "BJJ Fanatics",
        # Mindset
        "@DavidGoggins": "David Goggins",
        "@JockoPodcast": "Jocko Willink",
        "@JockoPodcastOfficial": "Jocko Willink",
        "@MindPumpPodcast": "Mind Pump",
        # Bodybuilding
        "@GregDoucette": "Greg Doucette",
        "@ChrisBumstead": "Chris Bumstead",
        "@sam_sulek": "Sam Sulek",
        "@Biolayne": "Dr. Layne Norton",
        "@ThinkBIGBodybuilding": "Scott McNally, Dave Crosland & Skipp Hill",
        "@rxmuscle": "Dave Palumbo",
        "@mountainabordog1": "John Meadows",
        "@JohnMeadowsMountainDog": "John Meadows",
        "@dorian_yates_official": "Dorian Yates",
        "@KaiGreene": "Kai Greene",
        "@RichPianaRaw": "Rich Piana",
        "@BradleyMartyn": "Bradley Martyn",
        "@MattDoesFitness": "Matt Morsia",
        "@WillTennyson": "Will Tennyson",
        "@BuffDudes": "Buff Dudes",
        "@NickTrigili": "Nick Trigili",
        "@ScottHermanFitness": "Scott Herman",
        "@MikeThurston": "Mike Thurston",
        "@hanyrambod_FST7": "Hany Rambod",
        "@StephanieButtermore": "Stephanie Buttermore",
        "@Natacha_Oceane": "Natacha Oceane",
        "@RyanHumiston": "Ryan Humiston",
        "@BaldOmniMan": "Bald Omni Man",
        "@MassiveIron": "Steve Shaw",
        "@SteveShawFitness": "Steve Shaw",
        "@bodybuildingcom": "Bodybuilding.com",
        "@NicksStrengthandPower": "Nick Miller",
        "@AndreaNunezOfficially": "Andrea Nunez",
        "@HighLifeWorkout": "High Life Workout",
        "@BroScienceLife": "Dom Mazzetti",
        "@RBTGym": "RBT Gym",
        # Calisthenics
        "@FitnessFAQs": "FitnessFAQs",
        "@CalisthenicMovement": "Calisthenic Movement",
        "@HybridCalisthenics": "Hampton Liu",
        "@THENX": "Chris Heria",
        # Movement / Rehab
        "@SquatUniversity": "Dr. Aaron Horschig",
        "@BenPatrick": "Ben Patrick (Knees Over Toes)",
        "@DrJohnRusin": "Dr. John Rusin",
        # Medical Education
        "@NinjaNerdOfficial": "Ninja Nerd",
        "@ArmandoHasudungan": "Armando Hasudungan",
        "@OsmosisOrg": "Osmosis",
        "@LecturioMedical": "Lecturio",
        "@MedCram": "Dr. Roger Seheult",
        "@InstituteofHumanAnatomy": "Institute of Human Anatomy",
        "@AnatomyZone": "AnatomyZone",
        "@AnatomyMB": "Anatomy MB",
        "@AnatomyBootCamp": "Anatomy Boot Camp",
        "@DrMattAndDrMike": "Dr. Matt & Dr. Mike",
        "@DrJohnCampbell": "Dr. John Campbell",
        "@DrBeen": "Dr. Mobeen Syed",
        "@DrNajeebLectures": "Dr. Najeeb",
        "@Kenhub": "Kenhub",
        "@muscleandmotion": "Muscle and Motion",
        "@SketchyMedical": "Sketchy Medical",
        "@BoardsBeyond": "Boards and Beyond",
        "@DirtyMedicine": "Dirty Medicine",
        "@MedSimplified": "Med Simplified",
        "@MedSchoolInsiders": "Med School Insiders",
        "@GetBodySmart": "Get Body Smart",
        "@VisibleBody": "Visible Body",
        "@BioDigitalHuman": "BioDigital Human",
        "@SamWebster": "Sam Webster",
        "@Medicosis": "Medicosis Perfectionalis",
        "@StrongMedicine": "Strong Medicine",
        "@Physeo": "Physeo",
        "@HandwrittenTutorials": "Handwritten Tutorials",
        # Research / Journals
        "@PubMed": "PubMed Research",
        "@ClinicalTrials": "ClinicalTrials.gov",
        "@NEJMvideo": "NEJM",
        "@NatureVideo": "Nature",
        "@LancetTV": "The Lancet",
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
        "@NorthwesternMed": "Northwestern Medicine",
        "@MassGeneralHospital": "Mass General Hospital",
        "@MountSinaiHealth": "Mount Sinai Health",
        "@VanderbiltHealth": "Vanderbilt Health",
        "@RushUniversity": "Rush University",
        # Sports Science / Organizations
        "@NSCA": "NSCA",
        "@ACSM_org": "ACSM",
        "@ACSMNews": "ACSM",
        "@ISSN_Sport": "ISSN",
        "@ACEfitness": "ACE Fitness",
        "@ISSAPersonalTrainer": "ISSA",
        "@NasmOrgPersonalTrainer": "NASM",
        "@ClinicalAthlete": "Clinical Athlete",
        "@ExPhysResearch": "Exercise Physiology Research",
        "@SportsScience": "Sports Science",
        "@strengthandconditioningresearch": "S&C Research",
        # Science Education
        "@3Blue1Brown": "3Blue1Brown",
        "@kurzgesagt": "Kurzgesagt",
        "@veritasium": "Veritasium",
        "@SciShow": "SciShow",
        "@Vsauce": "Vsauce",
        "@TED": "TED",
        "@TEDxTalks": "TEDx",
        "@TheRoyalInstitution": "Royal Institution",
        "@numberphile": "Numberphile",
        "@minutephysics": "MinutePhysics",
        "@ProfessorDaveExplains": "Professor Dave",
        # Medical Journals / Organizations
        "@AHAScience": "American Heart Association",
        "@EndocrineSociety": "Endocrine Society",
        "@ACPInternist": "ACP Internist",
        "@BMJupdates": "BMJ",
        "@CellPress": "Cell Press",
        "@Healthline": "Healthline",
        # Sports Nutrition
        "@NutritionByKylie": "Kylie Sakaida RD",
        "@IlanaMuhlstein": "Ilana Muhlstein RD",
        "@rpstrength": "Renaissance Periodization",
        "@CarbonDietCoach": "Carbon Diet Coach",
        "@PrecisionNutrition": "Precision Nutrition",
        # Endocrinology
        "@DocGerryTan": "Dr. Gerry Tan",
        "@DrSarfrazZaidi": "Dr. Sarfraz Zaidi",
        "@DrAlanChristianson": "Dr. Alan Christianson",
        "@TOTRevolution": "Jay Campbell",
        "@JayCampbell": "Jay Campbell",
        "@gillettehealth": "Dr. Kyle Gillett",
        "@TaylorMadeCompounding": "Taylor Made Compounding",
        "@DrCraigKoniver": "Dr. Craig Koniver",
        "@ThyroidUK": "Thyroid UK",
        # Sports Psychology
        "@PeakPerformanceSports": "Dr. Patrick Cohn",
        "@DrHaleyPerlus": "Dr. Haley Perlus",
        "@DrJoAnnDahlkoetter": "Dr. JoAnn Dahlkoetter",
        "@SuccessStartsWithin": "Success Starts Within",
        "@BrianCainPeak": "Brian Cain",
        "@SportPsychSolutions": "Lindsay Huddleston",
        # Performance Science
        "@AndyGalpin": "Dr. Andy Galpin",
        "@PerformPodcast": "Dr. Andy Galpin",
        "@TheReadyState": "Dr. Kelly Starrett",
        "@Kabuki_Strength": "Chris Duffin",
        "@PrehabGuys": "Prehab Guys",
        "@E3Rehab": "E3 Rehab",
        # Anti-Doping Organizations
        "@USAntidoping": "USADA",
        "@WABORCS": "WADA",
        "@cleanprotocol": "Clean Protocol",
        # Bodybuilding Legends
        "@RonnieColeman8": "Ronnie Coleman",
        "@OfficialRonnieColeman": "Ronnie Coleman",
        "@LeePriest": "Lee Priest",
        "@kevinlevrone": "Kevin Levrone",
        "@JayCutlerTV": "Jay Cutler",
        "@PhilHeath": "Phil Heath",
        "@ShawnRay": "Shawn Ray",
        "@FlexWheeler": "Flex Wheeler",
        "@LeeHaney": "Lee Haney",
        "@dorian_yates_official": "Dorian Yates",
        "@KaiGreene": "Kai Greene",
        # Mutant / Bodybuilding Media
        "@MutantOfficial": "Mutant",
        "@RonHarrisMuscle": "Ron Harris",
        "@BigRobFitness": "Big Rob",
        "@GenerationIron": "Generation Iron",
        "@MuscleMemoirsOfficial": "Muscle Memoirs",
        "@LondonReal": "London Real",
        # Medical Organizations
        "@FDAChannel": "FDA",
        "@NIH": "NIH",
        "@CDCgov": "CDC",
        "@WHO": "WHO",
        "@CochraneCollaboration": "Cochrane",
        "@JAMANetwork": "JAMA",
        "@AmericanDiabetesAssociation": "American Diabetes Association",
        "@ObesityMedicine": "Obesity Medicine Association",
        # TRT/Hormone Clinics
        "@TRTandHormoneOptimization": "TRT & Hormone Optimization",
        "@MensHealthClinic": "Men's Health Clinic",
        "@BalanceMyHormones": "Balance My Hormones",
        # Bodybuilding Historians
        "@NicksStrengthandPower": "Nick Miller",
        "@GoldenEraBB": "Golden Era Bodybuilding",
        "@OldSchoolLabs": "Old School Labs",
        "@VintageGenetics": "Vintage Genetics",
        # Contest Prep Coaches
        "@teamlocofit": "Team LoCoFit",
        "@3DMJCoaching": "3DMJ Coaching",
        "@JoeGordonFitness": "Joe Gordon",
        "@PrepCoachGary": "Prep Coach Gary",
        "@JordanPetersCoaching": "Jordan Peters",
        # Bodybuilding Podcasts
        "@MuscleIntelligence": "Ben Pakulski",
        "@MarkBellsPowerProject": "Mark Bell",
        "@RealBodybuilding": "Fouad Abiad",
        "@FouadAbiad": "Fouad Abiad",
        "@BroChat": "Bro Chat",
        "@TheBodybuildingPodcast": "The Bodybuilding Podcast",
        # Current Pro Bodybuilders
        "@SteveKuclo": "Steve Kuclo",
        "@IainValliere": "Iain Valliere",
        "@NickWalkerBodybuilder": "Nick Walker",
        "@DerekLunsford": "Derek Lunsford",
        "@HadiChoopan": "Hadi Choopan",
        "@AndrewJacked": "Andrew Jacked",
        # Supplement Science
        "@ExamineCom": "Examine.com",
        "@NutritionExamined": "Nutrition Examined",
        # Dosing Guides / Reference / Cycle Design
        "@DanDuchaine": "Dan Duchaine",
        "@CycleDesignGuide": "Forged by Freedom Cycle Design Guide",
        # Vendor Testing / Lab Results
        "@Janoshik": "Janoshik Analytical",
        # Harm Reduction / PED Education
        "@SethFeroce": "Seth Feroce",
        "@RussoLifts": "Russo Lifts",
        "@BodybuilderInThailand": "Bodybuilder In Thailand",
        "@SwollenAF": "Swollen AF",
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
        "@NEJMvideo": "research_primary",
        "@NatureVideo": "research_primary",
        "@LancetTV": "research_primary",
        "@BMJupdates": "research_primary",
        "@CellPress": "research_primary",
        # ThinkBig Priority
        "@ThinkBIGBodybuilding": "thinkbig_priority",
        "@rxmuscle": "rxmuscle_priority",
        # Medical Education
        "@NinjaNerdOfficial": "medical_education",
        "@OsmosisOrg": "medical_education",
        "@LecturioMedical": "medical_education",
        "@MedCram": "medical_education",
        "@InstituteofHumanAnatomy": "medical_education",
        "@Kenhub": "medical_education",
        "@DrJohnCampbell": "medical_education",
        "@DrBeen": "medical_education",
        "@DrNajeebLectures": "medical_education",
        "@SketchyMedical": "medical_education",
        "@BoardsBeyond": "medical_education",
        "@Physeo": "medical_education",
        "@AnatomyZone": "medical_education",
        "@AnatomyMB": "medical_education",
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
        "@AnabolicDoc": "anabolic_bodybuilding_priority",
        "@TonyHuge": "anabolic_bodybuilding_priority",
        "@CoachTrevorBlack": "anabolic_bodybuilding_priority",
        "@anabolicbodybuilding": "anabolic_bodybuilding_priority",
        "@anabolicuniversity": "anabolic_bodybuilding_priority",
        # Biohacking / Health
        "@FoundMyFitness": "biohacking",
        "@hubermanlab": "biohacking",
        "@AndrewHuberman": "biohacking",
        "@PeterAttiaMD": "medical_primary",
        "@DrGabrielleLyon": "medical_primary",
        "@johnjewett3": "anabolic_bodybuilding_priority",
        "@J3University": "anabolic_bodybuilding_priority",
        # Female Hormone & Menopause Experts
        "@DrStacySims": "female_health_priority",
        "@drmaryclairehaver": "female_health_priority",
        "@DrMindyPelz": "female_health_priority",
        # Female Science-Based Fitness
        "@HollyBaxter": "female_health_priority",
        "@SoheeFit": "female_health_priority",
        "@LaurinConlin": "female_health_priority",
        "@megsquats": "female_health_priority",
        # Female Bodybuilding
        "@AshleyKaltwasser": "female_health_priority",
        "@ErinSternFitness": "female_health_priority",
        "@JulieLohre": "female_health_priority",
        "@coachmusclenugget": "female_health_priority",
        "@CarolineGirvan": "female_health_priority",
        "@KatieCrewe": "female_health_priority",
        "@KristyHawkins": "female_health_priority",
        "@BarbellMedicine": "medical_primary",
        "@ThomasDeLauer": "biohacking",
        "@BenGreenfield": "biohacking",
        "@DrEricBerg": "biohacking",
        "@SiimLand": "biohacking",
        # Sports Nutrition
        "@JeffNippard": "sports_nutrition",
        "@RenaissancePeriodization": "sports_nutrition",
        "@Biolayne": "sports_nutrition",
        "@3DMuscleJourney": "sports_nutrition",
        "@EricHelms3DMJ": "sports_nutrition",
        "@MennoHenselmans": "sports_nutrition",
        "@StrongerByScience": "sports_nutrition",
        # Sports Science
        "@NSCA": "sports_science",
        "@ACSM_org": "sports_science",
        "@ACSMNews": "sports_science",
        "@ISSN_Sport": "sports_science",
        "@ACEfitness": "sports_science",
        "@ExPhysResearch": "sports_science",
        # Sports Nutrition (expanded)
        "@NutritionByKylie": "sports_nutrition",
        "@IlanaMuhlstein": "sports_nutrition",
        "@rpstrength": "sports_nutrition",
        "@CarbonDietCoach": "sports_nutrition",
        "@PrecisionNutrition": "sports_nutrition",
        # Peptides & GLP-1
        "@TaylorMadeCompounding": "peptides",
        "@DrSeedman": "peptides",
        "@JayCampbell": "peptides",
        "@TOTRevolution": "peptides",
        "@gillettehealth": "peptides",
        "@DrCraigKoniver": "peptides",
        "@PeptidesScienceDaily": "peptides",
        # Endocrinology
        "@DocGerryTan": "endocrinology",
        "@DrSarfrazZaidi": "endocrinology",
        "@DrAlanChristianson": "endocrinology",
        "@TOTRevolution": "endocrinology",
        "@gillettehealth": "endocrinology",
        "@ThyroidUK": "endocrinology",
        "@EndocrineSociety": "endocrinology",
        "@AHAScience": "medical_primary",
        # Sports Psychology
        "@PeakPerformanceSports": "sports_psych",
        "@DrHaleyPerlus": "sports_psych",
        "@DrJoAnnDahlkoetter": "sports_psych",
        "@SuccessStartsWithin": "sports_psych",
        "@BrianCainPeak": "sports_psych",
        "@SportPsychSolutions": "sports_psych",
        # Sports Psychology / Mindset
        "@DavidGoggins": "sports_psych",
        "@JockoPodcast": "sports_psych",
        "@JockoPodcastOfficial": "sports_psych",
        "@MindPumpPodcast": "sports_psych",
        # Performance Science
        "@AndyGalpin": "performance_science",
        "@PerformPodcast": "performance_science",
        "@TheReadyState": "performance_science",
        "@Kabuki_Strength": "performance_science",
        "@PrehabGuys": "performance_science",
        "@E3Rehab": "performance_science",
        # Anti-Doping / Testing Organizations
        "@USAntidoping": "anti_doping",
        "@WABORCS": "anti_doping",
        "@cleanprotocol": "anti_doping",
        # Bodybuilding Legends
        "@RonnieColeman8": "bodybuilding_legends",
        "@OfficialRonnieColeman": "bodybuilding_legends",
        "@LeePriest": "bodybuilding_legends",
        "@kevinlevrone": "bodybuilding_legends",
        "@JayCutlerTV": "bodybuilding_legends",
        "@PhilHeath": "bodybuilding_legends",
        "@ShawnRay": "bodybuilding_legends",
        "@FlexWheeler": "bodybuilding_legends",
        "@LeeHaney": "bodybuilding_legends",
        "@dorian_yates_official": "bodybuilding_legends",
        "@KaiGreene": "bodybuilding_legends",
        # Mutant / Bodybuilding Media
        "@MutantOfficial": "bodybuilding_media",
        "@RonHarrisMuscle": "bodybuilding_media",
        "@BigRobFitness": "bodybuilding_media",
        "@GenerationIron": "bodybuilding_media",
        "@MuscleMemoirsOfficial": "bodybuilding_media",
        "@LondonReal": "interviews",
        # Government / Medical Organizations
        "@FDAChannel": "medical_primary",
        "@NIH": "medical_primary",
        "@CDCgov": "medical_primary",
        "@WHO": "medical_primary",
        "@CochraneCollaboration": "research_primary",
        "@JAMANetwork": "research_primary",
        "@AmericanDiabetesAssociation": "medical_primary",
        "@ObesityMedicine": "medical_primary",
        # TRT/Hormone Optimization
        "@TRTandHormoneOptimization": "endocrinology",
        "@MensHealthClinic": "endocrinology",
        "@BalanceMyHormones": "endocrinology",
        # Bodybuilding Historians
        "@NicksStrengthandPower": "bodybuilding_history",
        "@GoldenEraBB": "bodybuilding_history",
        "@OldSchoolLabs": "bodybuilding_history",
        "@VintageGenetics": "bodybuilding_history",
        # Contest Prep Coaches
        "@teamlocofit": "contest_prep",
        "@3DMJCoaching": "contest_prep",
        "@JoeGordonFitness": "contest_prep",
        "@PrepCoachGary": "contest_prep",
        "@JordanPetersCoaching": "contest_prep",
        # Bodybuilding Podcasts
        "@MuscleIntelligence": "bodybuilding_media",
        "@MarkBellsPowerProject": "bodybuilding_media",
        "@RealBodybuilding": "bodybuilding_media",
        "@FouadAbiad": "bodybuilding_media",
        "@BroChat": "bodybuilding_media",
        "@TheBodybuildingPodcast": "bodybuilding_media",
        # Current Pro Bodybuilders
        "@SteveKuclo": "pro_bodybuilders",
        "@IainValliere": "pro_bodybuilders",
        "@NickWalkerBodybuilder": "pro_bodybuilders",
        "@DerekLunsford": "pro_bodybuilders",
        "@HadiChoopan": "pro_bodybuilders",
        "@AndrewJacked": "pro_bodybuilders",
        # Supplement Science
        "@ExamineCom": "sports_nutrition",
        "@NutritionExamined": "sports_nutrition",
        # Dosing Guides / Reference / Cycle Design
        "@DanDuchaine": "anabolic_bodybuilding_priority",
        "@CycleDesignGuide": "cycle_design_guides",
        # Vendor Testing / Lab Results
        "@Janoshik": "vendor_testing",
        # Harm Reduction / PED Education
        "@SethFeroce": "harm_reduction",
        "@RussoLifts": "harm_reduction",
        "@BodybuilderInThailand": "harm_reduction",
        "@SwollenAF": "harm_reduction",
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
