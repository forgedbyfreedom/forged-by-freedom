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

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("❌ OPENAI_API_KEY not set")

if not os.getenv("PINECONE_API_KEY"):
    raise RuntimeError("❌ PINECONE_API_KEY not set")

client = OpenAI()
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
        "@anabolicbodybuilding": "Anabolic Bodybuilding",
        "@anabolicuniversity": "Anabolic University",
        "@EnhancedAthlete": "Enhanced Athlete",
        "@TonyHuge": "Tony Huge",
        "@CoachTrevorBlack": "Coach Trevor",
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
        "@ThinkBIGBodybuilding": "Dave Palumbo",
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
        "@rxmuscle": "thinkbig_priority",
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
        # Sports Psychology / Mindset
        "@DavidGoggins": "sports_psych",
        "@JockoPodcast": "sports_psych",
        "@JockoPodcastOfficial": "sports_psych",
        "@MindPumpPodcast": "sports_psych",
    }

    if channel in namespace_map:
        return namespace_map[channel]

    return "transcripts"


def ingest():
    """Main ingest function with rich metadata."""
    print("\n🔍 INGEST STARTUP")
    print(f"• CHANNELS_DIR: {CHANNELS_DIR}")
    print(f"• Pinecone index: {INDEX_NAME}")
    print(f"• Embedding model: {EMBED_MODEL}")
    print(f"• Chunk tokens: {CHUNK_TOKENS}")

    # Get all txt files, excluding master transcripts
    txt_files = [
        f for f in CHANNELS_DIR.rglob("*.txt")
        if not f.name.startswith("master_transcript")
        and not f.name.startswith(".")
    ]

    total_files = len(txt_files)
    print(f"• Episodes to ingest: {total_files}")
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
    ingest()
