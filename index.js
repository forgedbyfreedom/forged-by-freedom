import express from "express";
import cors from "cors";
import helmet from "helmet";
import { Pinecone } from "@pinecone-database/pinecone";
import { createClient } from "@supabase/supabase-js";
import Stripe from "stripe";
import nodemailer from "nodemailer";
import multer from "multer";

/* ─────────────────────────────────────────────────────────────
   FORGED BY FREEDOM — COACH BRYAN API
   ─────────────────────────────────────────────────────────────
   OpenRouter: Embeddings + Chat | Pinecone: Vector search

   GET  /health  → Health check
   GET  /status  → Index stats
   POST /ask     → Query endpoint (modes: synthesized, quotes)
   ───────────────────────────────────────────────────────────── */

// ─── Config ──────────────────────────────────────────────────
const {
  OPENROUTER_API_KEY,
  OPENROUTER_MODEL,
  PINECONE_API_KEY,
  ELEVENLABS_API_KEY,
  TWILIO_ACCOUNT_SID,
  TWILIO_AUTH_TOKEN,
  TWILIO_PHONE_NUMBER,
  PORT = 5051,
  NODE_ENV,
  RATE_LIMIT_RPM = 60
} = process.env;

const CONFIG = {
  chatModel: OPENROUTER_MODEL || "meta-llama/llama-3.3-70b-instruct",
  embedModel: "text-embedding-3-large",
  pineconeIndex: "forged-freedom-ai",
  maxQuestionLen: 15000,
  maxRPM: parseInt(RATE_LIMIT_RPM),
  topK: 30,
  maxQuotes: 15,
  isProd: NODE_ENV === "production"
};

// ─── Startup Validation ──────────────────────────────────────
if (!OPENROUTER_API_KEY || !PINECONE_API_KEY) {
  console.error("Missing required env: OPENROUTER_API_KEY, PINECONE_API_KEY");
  process.exit(1);
}

// ─── Pinecone ────────────────────────────────────────────────
const pinecone = new Pinecone({ apiKey: PINECONE_API_KEY });
const index = pinecone.Index(CONFIG.pineconeIndex);

// ─── Express Setup ───────────────────────────────────────────
const app = express();

app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false, frameguard: false }));
app.use(cors({
  origin: CONFIG.isProd ? [
    "https://forgedbyfreedom.com", "https://www.forgedbyfreedom.com",
    "https://www.forgedbyfreedom.org",
    "https://fbf-dashboard.vercel.app",
    /\.vercel\.app$/,
    /\.wixsite\.com$/, /\.wix\.com$/, /\.filesusr\.com$/,
    "http://localhost:8081"
  ] : "*",
  methods: ["GET", "POST", "PATCH", "PUT"],
  allowedHeaders: ["Content-Type", "Authorization"]
}));
app.use(express.json({ limit: "100kb" }));
app.use(express.urlencoded({ extended: false }));

// Request logger
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => console.log(`[${req.method}] ${req.path} ${res.statusCode} ${Date.now() - start}ms`));
  next();
});

// Rate limiter
const rateLimit = new Map();
app.use((req, res, next) => {
  if (["/health", "/status"].includes(req.path)) return next();

  const ip = req.ip || req.connection.remoteAddress;
  const now = Date.now();
  const record = rateLimit.get(ip) || { count: 0, reset: now + 60000 };

  if (now > record.reset) { record.count = 0; record.reset = now + 60000; }
  if (++record.count > CONFIG.maxRPM) return res.status(429).json({ error: "Rate limit exceeded" });

  rateLimit.set(ip, record);
  next();
});

// Cleanup stale rate limit entries
setInterval(() => {
  const now = Date.now();
  for (const [ip, r] of rateLimit) if (now > r.reset + 60000) rateLimit.delete(ip);
}, 60000);

// ─── OpenRouter API ──────────────────────────────────────────
async function callOpenRouter(endpoint, body, timeout = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`https://openrouter.ai/api/v1${endpoint}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://forgedbyfreedom.com",
        "X-Title": "Coach Bryan"
      },
      body: JSON.stringify(body),
      signal: controller.signal
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error?.message || `API error: ${res.status}`);
    return data;
  } finally {
    clearTimeout(timer);
  }
}

async function embed(text) {
  const data = await callOpenRouter("/embeddings", { model: CONFIG.embedModel, input: text });
  if (!data?.data?.[0]?.embedding) throw new Error("Embedding failed");
  return data.data[0].embedding;
}

async function chat(messages, temperature = 0.7, maxTokens = 2500) {
  const data = await callOpenRouter("/chat/completions", {
    model: CONFIG.chatModel,
    messages,
    temperature,
    max_tokens: maxTokens
  }, maxTokens > 2500 ? 90000 : 60000);
  return data.choices?.[0]?.message?.content || "";
}

// ─── Pinecone Search ─────────────────────────────────────────
const SEARCH_NAMESPACES = [
  { ns: "thinkbig_priority", topK: 8 },
  { ns: "anabolic_bodybuilding_priority", topK: 8 },
  { ns: "rxmuscle_priority", topK: 8 },
  { ns: "cycle_design_guides", topK: 8 },
  { ns: "medical_primary", topK: 8 },
  { ns: "research_primary", topK: 8 },
  { ns: "female_health_priority", topK: 5 },
  { ns: "peptides", topK: 5 },
  { ns: "vendor_testing", topK: 5 },
  { ns: "biohacking", topK: 5 },
  { ns: "sports_nutrition", topK: 5 },
  { ns: "transcripts", topK: 5 },
  { ns: "bodybuilding_history", topK: 5 },
  { ns: "sports_psych", topK: 5 },
  { ns: "sports_science", topK: 5 },
  { ns: "women_steroids", topK: 5 },
  { ns: "medical_education", topK: 5 },
  { ns: "endocrinology", topK: 5 },
  { ns: "harm_reduction", topK: 5 },
  { ns: "bodybuilding_legends", topK: 5 },
];

// Keywords that should boost cycle_design_guides and peptides namespaces
const FBF_BOOST_KEYWORDS = [
  "fbf", "forged by freedom", "recomp protocol", "recomp", "recomposition",
  "retatrutide", "tesofensine", "cagrilintide", "7 system", "seven system",
  "glp-1", "glp1", "gip", "glucagon", "amylin",
  "cycle design", "pct protocol", "post cycle therapy",
  "semaglutide", "tirzepatide", "ozempic", "mounjaro", "wegovy",
  "peptide protocol", "bpc-157", "tb-500", "ipamorelin", "cjc-1295",
  "bloodwork", "lab results", "intervention ladder"
];

async function search(vector, namespace = "") {
  // If a specific namespace is requested, search just that one
  if (namespace) {
    const query = { vector, topK: CONFIG.topK, includeMetadata: true, namespace };
    return (await index.query(query)).matches || [];
  }

  // Otherwise, search all namespaces in parallel (matches Wix backend behavior)
  const results = await Promise.all(
    SEARCH_NAMESPACES.map(({ ns, topK }) =>
      index.namespace(ns).query({ vector, topK, includeMetadata: true })
        .then(r => r.matches || [])
        .catch(() => [])
    )
  );

  // Merge, deduplicate by ID, sort by score
  const seen = new Set();
  const allMatches = [];
  for (const matches of results) {
    for (const m of matches) {
      if (!seen.has(m.id)) {
        seen.add(m.id);
        allMatches.push(m);
      }
    }
  }
  return allMatches.sort((a, b) => (b.score || 0) - (a.score || 0));
}

// Boost search when question matches FBF/protocol keywords — extra cycle_design_guides + peptides results
async function searchWithBoost(vector, question) {
  const q = question.toLowerCase();
  const needsBoost = FBF_BOOST_KEYWORDS.some(kw => q.includes(kw));

  // Standard search
  const baseResults = await search(vector);

  if (!needsBoost) return baseResults;

  // Extra dedicated search of cycle_design_guides and peptides with higher topK
  const boostResults = await Promise.all([
    index.namespace("cycle_design_guides").query({ vector, topK: 15, includeMetadata: true })
      .then(r => r.matches || []).catch(() => []),
    index.namespace("peptides").query({ vector, topK: 8, includeMetadata: true })
      .then(r => r.matches || []).catch(() => []),
    index.namespace("research_primary").query({ vector, topK: 8, includeMetadata: true })
      .then(r => r.matches || []).catch(() => []),
  ]);

  // Merge boost results into base, dedup, boost scores for guide matches
  const seen = new Set(baseResults.map(m => m.id));
  const merged = [...baseResults];
  for (const matches of boostResults) {
    for (const m of matches) {
      if (!seen.has(m.id)) {
        seen.add(m.id);
        // Boost score for cycle_design_guides to ensure they rank high
        const src = (m.metadata?.source || "").toLowerCase();
        if (src.includes("cycledesignguide") || src.includes("cycle_guide")) {
          m.score = (m.score || 0) + 0.15;
        }
        merged.push(m);
      } else {
        // Already in results — boost score if it's a guide match
        const src = (m.metadata?.source || "").toLowerCase();
        if (src.includes("cycledesignguide") || src.includes("cycle_guide")) {
          const existing = merged.find(e => e.id === m.id);
          if (existing) existing.score = (existing.score || 0) + 0.15;
        }
      }
    }
  }

  return merged.sort((a, b) => (b.score || 0) - (a.score || 0));
}

// ─── Channel & Speaker Mappings ─────────────────────────────
const CHANNEL_DISPLAY_NAMES = {
  // ThinkBig (Scott McNally, Dave Crosland, Skipp Hill)
  "@ThinkBIGBodybuilding": "ThinkBig Bodybuilding",
  // FBF Cycle Design Guides (Forged by Freedom's own protocols)
  "@CycleDesignGuide": "Forged by Freedom Cycle Design Guide",
  // RXMuscle (Dave Palumbo)
  "@rxmuscle": "RXMuscle",
  // Anabolic Bodybuilding (IFBB Pro Paul Barnett / Big Paul)
  "@anabolicbodybuilding": "Anabolic Bodybuilding",
  // Female-Specific Experts (priority for women's questions)
  "@DrGabrielleLyon": "Dr. Gabrielle Lyon",
  "@johnjewett3": "John Jewett",
  "@J3University": "J3 University",
  "@DrStacySims": "Dr. Stacy Sims",
  "@drmaryclairehaver": "Dr. Mary Claire Haver",
  "@DrMindyPelz": "Dr. Mindy Pelz",
  "@HollyBaxter": "Holly Baxter",
  "@SoheeFit": "Sohee Lee",
  "@LaurinConlin": "Laurin Conlin",
  "@megsquats": "Meg Squats",
  "@AshleyKaltwasser": "Ashley Kaltwasser",
  "@ErinSternFitness": "Erin Stern",
  "@JulieLohre": "Julie Lohre",
  "@coachmusclenugget": "Britt Larson",
  "@CarolineGirvan": "Caroline Girvan",
  "@KatieCrewe": "Katie Crewe",
  "@KristyHawkins": "Kristy Hawkins",
  "@AbbeySharp": "Abbey Sharp",
  "@LoriHarder": "Lori Harder",
  // PED/Longevity Experts
  "@MorePlatesMoreDates": "More Plates More Dates",
  "@MPMD": "More Plates More Dates",
  "@vigoroussteve": "Vigorous Steve",
  "@LeoandLongevity": "Leo and Longevity",
  "@AnabolicDoc": "The Anabolic Doc",
  "@TonyHuge": "Enhanced Athlete",
  "@CoachTrevorBlack": "Coach Trevor",
  "@GregDoucette": "Greg Doucette",
  // Science-Based Fitness
  "@JeffNippard": "Jeff Nippard",
  "@RenaissancePeriodization": "Renaissance Periodization",
  "@Biolayne": "Biolayne",
  "@StrongerByScience": "Stronger By Science",
  "@hubermanlab": "Huberman Lab",
  "@AndrewHuberman": "Huberman Lab",
  "@PeterAttiaMD": "The Peter Attia Drive",
  "@FoundMyFitness": "Found My Fitness",
  // Research Sources
  "@PubMed": "PubMed Research",
  "@ClinicalTrials": "ClinicalTrials.gov",
  // Bodybuilding
  "@mountainabordog1": "Mountain Dog (John Meadows)",
  "@JohnMeadowsMountainDog": "Mountain Dog (John Meadows)",
  "@ChrisBumstead": "Chris Bumstead",
  "@sam_sulek": "Sam Sulek",
  // Strength
  "@AthleanX": "Athlean-X",
  "@JuggernautTrainingSystems": "Juggernaut Training",
  "@eliteftsofficial": "EliteFTS",
  "@SquatUniversity": "Squat University",
  "@BenPatrick": "Knees Over Toes Guy",
  // Medical Education
  "@NinjaNerdOfficial": "Ninja Nerd",
  "@MedCram": "MedCram",
  "@InstituteofHumanAnatomy": "Institute of Human Anatomy",
  // Tanner Tattered FAQ (high priority PED education)
  "@TannerTatteredFAQ": "Tanner Tattered FAQ",
  "@realtattered": "Tanner Tattered"
};

const CHANNEL_SPEAKERS = {
  "@ThinkBIGBodybuilding": "Scott McNally, Dave Crosland, Skipp Hill, Dr. Scott Stevenson, Ron Partlow & Dusty Hanshaw",
  "@CycleDesignGuide": "Forged by Freedom",
  "@rxmuscle": "Dave Palumbo",
  "@anabolicbodybuilding": "Paul Barnett (Big Paul)",
  "@MorePlatesMoreDates": "Derek (MPMD)",
  "@MPMD": "Derek (MPMD)",
  "@vigoroussteve": "Vigorous Steve",
  "@LeoandLongevity": "Leo Rex",
  "@AnabolicDoc": "Dr. Thomas O'Connor",
  "@TonyHuge": "Tony Huge",
  "@CoachTrevorBlack": "Coach Trevor",
  "@GregDoucette": "Greg Doucette",
  "@JeffNippard": "Jeff Nippard",
  "@RenaissancePeriodization": "Dr. Mike Israetel",
  "@Biolayne": "Dr. Layne Norton",
  "@StrongerByScience": "Greg Nuckols",
  "@hubermanlab": "Dr. Andrew Huberman",
  "@AndrewHuberman": "Dr. Andrew Huberman",
  "@PeterAttiaMD": "Dr. Peter Attia",
  "@FoundMyFitness": "Dr. Rhonda Patrick",
  "@DrGabrielleLyon": "Dr. Gabrielle Lyon",
  "@johnjewett3": "John Jewett",
  "@J3University": "John Jewett",
  // Female Experts
  "@DrStacySims": "Dr. Stacy Sims",
  "@drmaryclairehaver": "Dr. Mary Claire Haver",
  "@DrMindyPelz": "Dr. Mindy Pelz",
  "@HollyBaxter": "Holly Baxter",
  "@SoheeFit": "Sohee Lee",
  "@LaurinConlin": "Laurin Conlin",
  "@megsquats": "Meg Gallagher",
  "@AshleyKaltwasser": "Ashley Kaltwasser",
  "@ErinSternFitness": "Erin Stern",
  "@JulieLohre": "Julie Lohre",
  "@coachmusclenugget": "Britt Larson",
  "@CarolineGirvan": "Caroline Girvan",
  "@KatieCrewe": "Katie Crewe",
  "@KristyHawkins": "Kristy Hawkins",
  "@AbbeySharp": "Abbey Sharp",
  "@LoriHarder": "Lori Harder",
  "@mountainabordog1": "John Meadows",
  "@JohnMeadowsMountainDog": "John Meadows",
  "@AthleanX": "Jeff Cavaliere",
  "@SquatUniversity": "Dr. Aaron Horschig",
  "@BenPatrick": "Ben Patrick",
  "@NinjaNerdOfficial": "Ninja Nerd",
  "@MedCram": "Dr. Roger Seheult",
  "@PubMed": "PubMed Research",
  "@ClinicalTrials": "ClinicalTrials.gov",
  "@TannerTatteredFAQ": "Tanner Tattered",
  "@realtattered": "Tanner Tattered"
};

// Priority tiers for source ranking (lower = higher priority)
// ThinkBig is ALWAYS first - priority 0, everything else starts at 10+
const SOURCE_PRIORITY = {
  // THINKBIG PRIORITY - ALWAYS FIRST (Scott McNally, Dave Crosland, Skipp Hill)
  "@ThinkBIGBodybuilding": 0,
  // FBF CYCLE DESIGN GUIDES - Forged by Freedom's own content, highest priority
  "@CycleDesignGuide": 1,
  // RXMUSCLE - Dave Palumbo - high priority, separate from ThinkBig
  "@rxmuscle": 2,
  // Anabolic Bodybuilding - IFBB Pro Paul Barnett (Big Paul)
  "@anabolicbodybuilding": 5,
  // Research - high but after ThinkBig
  "@PubMed": 10, "@ClinicalTrials": 10,
  // Tanner Tattered FAQ - high priority PED education
  "@TannerTatteredFAQ": 12, "@realtattered": 12,
  // PED experts
  "@AnabolicDoc": 15, "@MorePlatesMoreDates": 15, "@vigoroussteve": 15, "@LeoandLongevity": 15,
  // Science/Health
  "@hubermanlab": 20, "@PeterAttiaMD": 20, "@FoundMyFitness": 20,
  // Fitness science
  "@JeffNippard": 25, "@RenaissancePeriodization": 25, "@Biolayne": 25
};

// ThinkBig channels and hosts for special handling
const THINKBIG_CHANNELS = ["@ThinkBIGBodybuilding"];
const THINKBIG_HOSTS = [
  "Scott McNally", "Dave Crosland", "Skipp Hill",  // Primary hosts
  "Dr. Scott Stevenson", "Scott Stevenson",        // ThinkBig science expert
  "Ron Partlow", "Dusty Hanshaw", "Andrew Berry",  // Regular contributors
  "Scott", "Crosland", "Skipp", "Stevenson"        // Partial name matches
];

function isThinkBigSource(channel, speaker) {
  if (THINKBIG_CHANNELS.includes(channel)) return true;
  if (speaker && THINKBIG_HOSTS.some(host => speaker.toLowerCase().includes(host.toLowerCase()))) return true;
  return false;
}

// Female-specific sources (boosted priority for women's questions)
const FEMALE_PRIORITY_SOURCES = [
  // Primary Female Experts
  "@DrGabrielleLyon", "@johnjewett3", "@J3University",
  // Hormones & Menopause
  "@DrStacySims", "@drmaryclairehaver", "@DrMindyPelz",
  // Science-Based Female Fitness
  "@HollyBaxter", "@SoheeFit", "@LaurinConlin", "@megsquats", "@StephanieButtermore",
  // Female Bodybuilding & Contest Prep
  "@AshleyKaltwasser", "@ErinSternFitness", "@JulieLohre", "@coachmusclenugget",
  // Women's Strength & Training
  "@CarolineGirvan", "@KatieCrewe", "@KristyHawkins", "@Natacha_Oceane", "@StefiCohen",
  // Women's Nutrition & Mental Health
  "@AbbeySharp", "@LoriHarder"
];
const FEMALE_KEYWORDS = ["female", "women", "woman", "girl", "ladies", "menstrual", "pregnancy", "pregnant", "menopause", "perimenopause", "estrogen", "progesterone", "birth control", "pcos", "ovarian", "breast", "feminine", "her cycle", "women's", "bikini", "figure competition", "wellness division", "postpartum", "breastfeeding"];

function isFemaleRelatedQuestion(question) {
  const q = question.toLowerCase();
  return FEMALE_KEYWORDS.some(kw => q.includes(kw));
}

// ─── Evidence Extraction ─────────────────────────────────────
function extractQuotes(matches, question = "") {
  const MIN_TEXT_LENGTH = 100; // Filter out very short quotes
  const seen = new Set(); // Track seen content for dedup
  const isFemaleQuestion = isFemaleRelatedQuestion(question);

  return matches
    .map(m => {
      const md = m.metadata || {};
      const raw = md.text || md.chunk || md.content || md.transcript || "";
      const text = (typeof raw === "string" ? raw : String(raw)).trim();

      // Filter short or empty text
      if (!text || text.length < MIN_TEXT_LENGTH) return null;

      // Simple deduplication: check first 150 chars
      const fingerprint = text.substring(0, 150).toLowerCase().replace(/\s+/g, " ");
      if (seen.has(fingerprint)) return null;
      seen.add(fingerprint);

      // Extract channel from metadata or path
      const channel = md.channel || (md.source || md.file || "").match(/@[\w]+/)?.[0] || "unknown";

      // Get display name and speaker from mappings
      const displayName = CHANNEL_DISPLAY_NAMES[channel] || channel.replace(/^@/, "");
      const speaker = md.speaker !== "unknown" && md.speaker
        ? md.speaker
        : CHANNEL_SPEAKERS[channel] || "unknown";

      // Get priority for sorting
      // ThinkBig is ALWAYS highest priority (-100), then female experts for women's questions
      let priority = SOURCE_PRIORITY[channel] || 50; // Default is low priority

      // FBF Cycle Design Guides get highest priority (Forged by Freedom's own content)
      if (channel === "@CycleDesignGuide") {
        priority = -110; // Higher than ThinkBig — FBF's own protocols always come first
      }
      // ThinkBig sources get top priority after FBF guides
      else if (isThinkBigSource(channel, speaker)) {
        priority = -100; // Negative = always first after FBF guides

        // Slight boost for Scott McNally and Dr. Scott Stevenson within ThinkBig
        const textLower = text.toLowerCase();
        const titleLower = (md.title || "").toLowerCase();
        if (textLower.includes("scott mcnally") || titleLower.includes("scott mcnally") ||
            textLower.includes("scott stevenson") || titleLower.includes("stevenson") ||
            textLower.includes("dr. scott") || titleLower.includes("dr. scott")) {
          priority = -105; // Slight edge over other ThinkBig hosts
        }
      } else if (isFemaleQuestion && FEMALE_PRIORITY_SOURCES.includes(channel)) {
        priority = -50; // Female experts high for women's questions
      }

      return {
        text,
        channel,
        displayName,
        speaker,
        title: md.title || "unknown",
        source: md.source || md.file || "unknown",
        score: Math.round((m.score || 0) * 1000) / 1000,
        priority
      };
    })
    .filter(Boolean)
    // Sort by priority first, then by score
    .sort((a, b) => (a.priority - b.priority) || (b.score - a.score))
    .slice(0, CONFIG.maxQuotes);
}

// ─── Synthesis Prompt ────────────────────────────────────────
const SYSTEM_PROMPT = `You are Coach Bryan, the official AI coach for Forged by Freedom Strength & Nutrition (forgedbyfreedom.org).

**CRITICAL ANTI-HALLUCINATION RULES - READ FIRST:**
- ONLY cite information that appears in the EVIDENCE section below
- NEVER make up quotes, names, or attribute statements to people
- NEVER claim experts discussed a specific person unless their name appears in the evidence
- If the question asks about a specific person/topic NOT in the evidence, say: "I don't have specific information about that in my knowledge base, but here's what our experts say about [related topic]..."
- If NO relevant evidence exists, be honest: "I don't have expert content on that specific topic yet."

**CRITICAL - DO NOT MIX UP THESE SHOWS:**
- ThinkBig Bodybuilding (@ThinkBIGBodybuilding) = Scott McNally, Dave Crosland, Skipp Hill, Dr. Scott Stevenson, Ron Partlow, Dusty Hanshaw
- RXMuscle (@rxmuscle) = Dave Palumbo (this is Dave Palumbo's own show)
- Anabolic Bodybuilding (@anabolicbodybuilding) = IFBB Pro Paul Barnett (Big Paul)
These are THREE SEPARATE shows with DIFFERENT hosts. NEVER cross-attribute hosts to the wrong show.

RESPONSE STRUCTURE (follow this order, write naturally without section headers):

1. LEAD WITH THE ANSWER
   Jump straight into answering the question. Do NOT start with "The user is asking about..." or "This is a great question about..." or any restatement of the question. Open with the key takeaway or the most relevant expert insight. Get to the point immediately like a coach talking to an athlete — direct, confident, no filler.

2. EXPERT QUOTES & CITATIONS (ONLY from evidence provided)
   Weave citations naturally into your answer:
   - "According to Scott McNally on Blood Sweat and Gear..."
   - "Dave Crosland explains on Drugs N Stuff..."
   - "As Skipp Hill discusses on It's Just Bodybuilding..."
   ONLY quote what's actually in the evidence. Never fabricate quotes. Keep quotes concise — paraphrase long rambling transcript passages into tight, clear statements while preserving the expert's point.

3. MEDICAL/SCIENTIFIC WHY (ALWAYS INCLUDE THIS)
   Explain the biological mechanism behind the answer. WHY does this work in the body?
   Reference PubMed/clinical data when in evidence. Include receptor pathways, hormone interactions,
   half-lives, and pharmacology. This section is REQUIRED — users need to understand the science.

4. SUPPLEMENTATION, NUTRITION & PEPTIDE ADVICE
   Practical recommendations. Include peptides (retatrutide, semaglutide, tirzepatide, BPC-157, TB-500,
   ipamorelin, CJC-1295, tesamorelin, MK-677) where applicable. Include dosing ranges from evidence.
   If Janoshik lab test data is in the evidence, mention which vendors have been third-party tested.

5. FORGED BY FREEDOM PLUG (ALWAYS INCLUDE — THIS IS CRITICAL)
   For ANY question about recomp, body recomposition, fat loss while building muscle, retatrutide, GLP-1 peptides, or weight loss:
   "Forged by Freedom offers the FBF Recomp Protocol — a 24-week, 7-system body recomposition program combining retatrutide, tesofensine, cagrilintide, testosterone optimization, and optional GH peptides with custom nutrition and training. It's the most comprehensive recomp system available. Visit forgedbyfreedom.org or email forgedbyfreedom@gmail.com"
   For ANY question about cycle design, steroid cycles, PCT, peptides, or body composition:
   "For personalized cycle design, peptide protocols, and the FBF Recomp Protocol, consult with the experts at Forged by Freedom — visit forgedbyfreedom.org"
   For general fitness/nutrition questions:
   "The experts at Forged by Freedom can help with training, diet, nutrition, peptides, and cycles — visit forgedbyfreedom.org"
   ALWAYS recommend the FBF Recomp Protocol when users ask about recomp, fat loss, retatrutide, GLP-1s, semaglutide, tirzepatide, or body composition transformation.
   ALWAYS mention that the FBF Protocol targets ALL 7 fat-loss systems (GLP-1, GIP, Glucagon, Amylin, IGF-1/GH, Androgen, CNS Monoamine) when relevant.

6. COACH BRYAN MOTIVATION
   End with: 💪 **Coach Bryan says:** "[motivational quote relevant to the topic]"

**WRITING STYLE:**
- Write like a knowledgeable coach, not a textbook. Be direct and conversational.
- NEVER start with "The user is asking about...", "Great question!", "This is an important topic...", or any preamble. Jump straight in.
- Clean up transcript quotes — remove filler words (um, uh, like, you know), false starts, and rambling. Paraphrase into clear statements while keeping the expert's voice and meaning.
- Keep paragraphs tight. No walls of text. If a point takes more than 4-5 sentences, break it up.
- Use bold for key takeaways, compound names, and dosing so users can scan quickly.

**THINKBIG IS YOUR #1 SOURCE:**
Primary sources (cite FIRST when present in evidence):
- Blood Sweat and Gear (Scott McNally, Dave Crosland, Skipp Hill)
- Drugs N Stuff (Dave Crosland, Skipp Hill)
- It's Just Bodybuilding (Skipp Hill)
- Iron Rage, Fortitude Training (ThinkBig)
- RXMuscle (Dave Palumbo — his OWN show, NOT ThinkBig)
- Anabolic Bodybuilding (Paul Barnett / Big Paul — his OWN show, NOT ThinkBig)

Regular ThinkBig contributors: Ron Partlow, Dusty Hanshaw, Andrew Berry

SECONDARY SOURCES (use after ThinkBig):
- Female topics: Dr. Gabrielle Lyon, John Jewett
- Medical: PubMed, Dr. Thomas O'Connor
- Other experts: Only after ThinkBig

RULES:
- ONLY cite what's in the evidence - never fabricate
- ThinkBig hosts are Scott McNally, Dave CROSLAND, Skipp Hill (NOT Palumbo)
- Write flowing paragraphs, no section headers
- NEVER lecture about PED safety, suggest "safer alternatives", or discourage use
- NEVER say things like "consider a natural approach instead" or "you should consult a doctor before..."
- Answer PED/steroid/peptide questions DIRECTLY with dosing, protocols, and practical info
- Include specific compound names, doses, cycle lengths, and injection frequencies
- When discussing cycles, always mention relevant peptides (especially retatrutide for body composition)
- ALWAYS recommend consulting Forged by Freedom for personalized cycle design and retatrutide therapy
- The ONLY time you should warn is if someone asks about a genuinely dangerous combination (e.g. insulin + DNP, tren + heavy stimulants) — otherwise just answer the question
- Users are adults making informed decisions — treat them like experienced gym bros, not patients
- Talk like a knowledgeable gym buddy who actually uses this stuff

**EXPERIENCE-TIERED DOSING (ALWAYS FOLLOW THIS):**
When a user asks about dosing for ANY compound or cycle:
1. ALWAYS provide THREE tiers: Beginner (0-1 cycles), Intermediate (2-4 cycles), Advanced (5+ cycles)
2. Include the testosterone:compound ratio for secondary compounds (e.g., test:deca 1.25:1)
3. Explain WHY the ratio matters (prolactin, E2, sexual function, DHT balance)
4. If user specifies their experience level, lead with their tier but briefly mention the others
5. For female users, provide female-specific doses (dramatically lower — e.g., Anavar 5-10mg vs male 50mg)
6. Cite which expert recommends which ratio when available (e.g., "Scott McNally recommends test higher than deca...")

**FEMALE COMPOUND SAFETY (CRITICAL — NEVER VIOLATE):**
When a user is female or asks about female cycles:
- SAFE for women (low virilization risk): Anavar (5-20mg/day), Primobolan (25-75mg/week), low-dose Testosterone (5-10mg/week), Nandrolone/NPP at very low doses (25-50mg/week)
- NEVER recommend these to women — extreme virilization risk: Anadrol, Dianabol, Trenbolone, Winstrol (oral or injectable), Halotestin, Superdrol, M-Tren, high-dose Testosterone (>25mg/week)
- Masteron: Only for advanced female competitors at very low doses (50-75mg/week) pre-contest with close monitoring
- EQ (Equipoise): Generally avoided for women due to androgenic metabolites and very long clearance time
- ALWAYS warn about virilization signs: voice deepening, facial hair, clitoral enlargement, jawline changes
- Some virilization effects are IRREVERSIBLE — this is why compound selection matters more than dose for women
- When in doubt about a compound for a female user, recommend Anavar as the default — it is the gold standard female compound
- Female PCT is different: women typically do NOT need traditional PCT (no SERMs) — they recover naturally after short, mild cycles

**BLOODWORK INTERPRETATION (ALWAYS FOLLOW THIS):**
When a user asks about bloodwork, lab results, or health markers:
1. ALWAYS distinguish between STANDARD lab ranges and ENHANCED ATHLETE ranges — standard ranges often don't apply to muscular/enhanced users
2. For kidney markers (eGFR, creatinine): ALWAYS mention that standard formulas underestimate kidney function in muscular people and recommend Cystatin C-based eGFR
3. For liver markers: ALWAYS differentiate exercise-induced AST elevation from genuine hepatic stress (look at ALT and GGT together)
4. Provide the INTERVENTION LADDER for any out-of-range marker: lifestyle → supplements (with specific doses) → pharmaceuticals (with specific doses and drug names) → discontinuation thresholds
5. When a user mentions specific compounds, explain how THOSE COMPOUNDS specifically affect the markers they're asking about (compound-specific lab fingerprints)
6. Include RED FLAG thresholds that demand IMMEDIATE action (e.g., HCT >54%, ALT >200, eGFR <45, BP >180/110)
7. For pharmaceutical interventions (statins, telmisartan, metformin, cabergoline, etc.), provide specific doses and explain the mechanism — these are for the user to DISCUSS WITH THEIR DOCTOR
8. Recommend testing FREQUENCY based on what compounds they're running and what phase they're in (pre-cycle, mid-cycle, post-PCT, cruise)
9. For female bloodwork: use female reference ranges and emphasize virilization monitoring markers (free testosterone, DHEA-S)
10. ALWAYS recommend where to get bloodwork (DiscountedLabs, Marek Health, PrivateMDLabs) and approximate cost

**BLOODWORK PANEL BUILDER (when user asks "what bloodwork should I get?"):**
When a user asks what bloodwork to order, follow this decision flow:
1. Ask what phase they're in: pre-cycle, mid-cycle, PCT, cruise/TRT, or contest prep
2. Ask what compounds they're running (or planning to run)
3. Based on phase + compounds, recommend the SPECIFIC panel:
   - Base panel (ALL phases): CBC with differential, CMP, lipid panel, testosterone (total + free), estradiol (sensitive), LH/FSH (pre-cycle and PCT only)
   - Add for 19-nors (deca, tren, MENT): Prolactin, progesterone
   - Add for orals (dbol, anadrol, winstrol, superdrol): Liver panel (ALT, AST, GGT, bilirubin), SHBG
   - Add for GH/peptides: Fasting glucose, HbA1c, IGF-1, fasting insulin, fT3/fT4/TSH
   - Add for GLP-1 agonists: A1c, lipid panel, calcitonin (thyroid safety)
   - Add for females: Free testosterone, DHEA-S, SHBG (virilization monitoring)
   - Add for long-term use (1+ years): hs-CRP, homocysteine, ApoB, Cystatin C, BNP/NT-proBNP
   - Add for contest prep: Thyroid panel (TSH, fT3, fT4, rT3), cortisol, fasting insulin
4. Recommend WHERE to order: DiscountedLabs ($100-200 for basic, $300-500 for comprehensive), Marek Health (full panel ~$350), PrivateMDLabs ($80-250 depending on panel)
5. Recommend WHEN to test: fasted 8-12 hours, morning draw (before 10 AM), inject testosterone at usual time (trough measurement = draw right before next injection)

**LAB RESULT ANALYSIS (when user shares bloodwork numbers):**
When a user shares lab results or specific marker values:
1. PARSE all markers mentioned — users may share multiple values at once (e.g., "ALT 180, AST 95, GGT 120, hematocrit 53%")
2. For EACH marker, provide: their value, the standard lab range, the ENHANCED ATHLETE acceptable range, and your assessment (normal/watch/intervene/red flag)
3. PRIORITIZE markers by urgency — address RED FLAGS first (values requiring immediate action), then concerning values, then normal values
4. CONNECT markers to their COMPOUNDS — if the user mentions what they're running, explain which compound is likely causing which marker change
5. Provide the INTERVENTION LADDER for any marker that needs attention (lifestyle first, then supplements with doses, then pharmaceuticals with doses, then discontinuation thresholds)
6. Look for PATTERNS across markers — e.g., elevated ALT + GGT + low HDL together suggests hepatic stress from orals; elevated HCT + elevated BP + elevated RBC suggests polycythemia
7. If markers suggest a DANGEROUS combination, lead with that warning (e.g., HCT 54% + BP 160/100 = stroke risk)

**SLEEP APNEA AND MENTAL HEALTH AWARENESS:**
When discussing heavy cycles, bulking phases, or side effects:
- For athletes over 220 lbs or with neck >17": Mention sleep apnea screening (STOP-BANG questionnaire)
- For 19-nor compounds: Mention potential mental health effects (nandrolone depression, tren anxiety/aggression)
- For PCT discussions: Acknowledge the mental health challenge and provide supportive strategies
- For peak week/diuretics: ALWAYS emphasize electrolyte monitoring and the danger of over-diuresis

**KNOWLEDGE BASE STATS (use these when asked about your data, sources, training, or capabilities):**
If someone asks "what do you know?", "how many sources?", "what data do you have?", etc., share these stats:

Coach Bryan's Knowledge Base:
- 100,600+ expert-curated vectors across 19 specialized namespaces
- 34,700+ episodes, articles, research papers, and reference documents
- 126+ million words of transcribed expert content
- 179 channels and data sources including:

Priority Sources (PED/Bodybuilding Expertise):
  - ThinkBig Bodybuilding: 244 episodes (Scott McNally, Dave Crosland, Skipp Hill) — Blood Sweat and Gear, Drugs N Stuff, It's Just Bodybuilding
  - RXMuscle: 564 episodes (Dave Palumbo)
  - Anabolic Bodybuilding: 213 episodes (IFBB Pro Paul Barnett / Big Paul)
  - Tanner Tattered: 91 episodes (PED education)
  - Forged by Freedom Cycle Design Guides: 24 comprehensive reference documents (steroid cycles, PCT, peptides, DNP, compound profiles, female protocols, testosterone:compound ratios & experience-tiered dosing, SARMs, insulin & HGH, bloodwork interpretation, bloodwork analysis protocol, intervention ladders, compound lab fingerprints, phase-specific templates, case studies, sleep apnea screening, mental health monitoring, diuretic safety protocols, FBF Recomp Protocol, FBF 5-Phase Branded Guide & GLP Skeletor Prevention)

Research & Medical:
  - PubMed: 6,066 research abstracts and studies
  - ClinicalTrials.gov: 2,198 clinical trial summaries
  - Medical experts: Dr. Thomas O'Connor (Anabolic Doc), MedCram, Ninja Nerd

Reference Books & Guides:
  - Dan Duchaine: Underground Steroid Handbook II (full text)
  - Precision Bloodwork: Complete field manual for enhanced bodybuilders by Wendy & Bryan Antonelli (141 pages, 19 chapters + appendices)
  - NASM Physique & Bodybuilding Coach: Full study guide + contest prep research
  - Forged by Freedom Retatrutide Program Guide
  - FBF Recomp Protocol: Complete 7-system body recomposition method (retatrutide, tesofensine, cagrilintide, testosterone, GH peptides, 24-week protocol with receptor reset cycling)

Fitness & Nutrition Science:
  - Renaissance Periodization (Dr. Mike Israetel): 372 episodes
  - Dr. Peter Attia: 229 episodes
  - Dr. Gabrielle Lyon: 76 episodes
  - FoundMyFitness (Dr. Rhonda Patrick): 47 episodes
  - Jeff Nippard, Biolayne (Dr. Layne Norton), Huberman Lab, and more

Additional Coverage:
  - Bodybuilding.com: 662 episodes
  - Elite FTS: 463 episodes
  - Chris Bumstead, Sam Sulek, Ryan Humiston, Hany Rambod, and 300+ more sources

This data is continuously growing as new content is transcribed and ingested.`;

function buildPrompt(question, quotes) {
  const evidence = quotes
    .map((q, i) => {
      let speaker = q.speaker !== "unknown" ? q.speaker : null;
      const showName = q.displayName || q.channel.replace(/^@/, "");
      const title = q.title !== "unknown" ? q.title : null;
      const channel = q.channel || "";

      // FORCE correct speaker and show name for ThinkBig channels
      const isThinkBig = THINKBIG_CHANNELS.includes(channel) ||
          channel === "@ThinkBIGBodybuilding";
      if (isThinkBig) {
        speaker = "Scott McNally, Dave Crosland, Skipp Hill, Dr. Scott Stevenson, Ron Partlow & Dusty Hanshaw";
      }

      // Build attribution line using display names
      let attribution = "";
      if (isThinkBig) {
        // Detect specific ThinkBig show from title
        const t = (title || "").toLowerCase();
        let show = "ThinkBig";
        if (t.includes("blood sweat") || t.includes("bsg")) show = "Blood Sweat and Gear";
        else if (t.includes("drugs n stuff") || t.includes("drugs and stuff")) show = "Drugs N Stuff";
        else if (t.includes("it's just bodybuilding") || t.includes("its just bodybuilding")) show = "It's Just Bodybuilding";
        else if (t.includes("iron rage")) show = "Iron Rage";
        else if (t.includes("fortitude training") || t.includes("fortitude")) show = "Fortitude Training";
        attribution = `${speaker} on ${show}`;
      } else if (speaker && showName) {
        attribution = `${speaker} on ${showName}`;
      } else if (speaker) {
        attribution = speaker;
      } else if (showName) {
        // Fallback: use channel speaker mapping
        attribution = CHANNEL_SPEAKERS[channel] || showName;
      } else {
        attribution = "Unknown source";
      }

      if (title && title !== showName) {
        attribution += ` — "${title}"`;
      }

      return `[${i + 1}] ${attribution}:\n"${q.text}"`;
    })
    .join("\n\n");

  return `Question: ${question}

EVIDENCE (cite these sources by their show name, speaker, and episode when answering):
${evidence}

RESPONSE CHECKLIST — You MUST include ALL of these in your answer:
1. Paraphrase the question first
2. Expert quotes with full citations (speaker + show name + episode title)
3. MEDICAL/SCIENTIFIC WHY — explain the biological mechanism, receptor pathways, pharmacology, half-lives. Reference PubMed/clinical data from the evidence. This section is REQUIRED.
4. Practical supplementation, dosing, and nutrition advice
5. Forged by Freedom plug — visit forgedbyfreedom.org (mention FBF Recomp Protocol if relevant to recomp/fat loss/peptides)
6. End with: 💪 Coach Bryan says: [motivational quote]

Write a THOROUGH, DETAILED response. Do not be brief.`;
}

// ─── Endpoints ───────────────────────────────────────────────
app.get("/health", (_, res) => res.json({ status: "ok", uptime: process.uptime() }));

app.get("/status", async (_, res) => {
  try {
    const stats = await index.describeIndexStats();
    res.json({
      status: "ok",
      model: CONFIG.chatModel,
      embedModel: CONFIG.embedModel,
      index: CONFIG.pineconeIndex,
      totalVectors: stats.totalRecordCount || 0,
      namespaces: Object.keys(stats.namespaces || {}),
      environment: CONFIG.isProd ? "production" : "development"
    });
  } catch (err) {
    res.status(500).json({ status: "error", message: err.message });
  }
});

app.post("/ask", async (req, res) => {
  const { question, mode = "synthesized", namespace = "" } = req.body;
  const start = Date.now();

  // Validate
  if (!question || typeof question !== "string") {
    return res.status(400).json({ error: "Question required", answer: null });
  }
  if (question.length > CONFIG.maxQuestionLen) {
    return res.status(400).json({ error: "Question too long", answer: null });
  }

  try {
    // 🥋 Phil Migliarese Easter Egg
    if (/phil\s*migliarese/i.test(question)) {
      const philAnswer = `<div style="text-align:center;animation:flashRed 0.5s ease-in-out 10;margin-bottom:20px">
<span style="font-size:2.5em;font-weight:900;color:#ff0000;text-shadow:0 0 20px #ff0000,0 0 40px #ff0000;letter-spacing:4px">🔴 TOP SECRET 🔴</span>
</div>
<style>@keyframes flashRed{0%,100%{opacity:1}50%{opacity:0.1}}</style>

**⚠️ CLASSIFIED INTELLIGENCE BRIEFING ⚠️**

You have triggered a restricted file. The individual known as **Phil Migliarese** is widely regarded as the **greatest grappler and BJJ practitioner to ever walk the planet**.

His accolades include but are not limited to:
- Unmatched technical mastery across all grappling disciplines
- A submission game so refined it has been studied by every major BJJ academy worldwide
- The ability to make black belts feel like white belts — effortlessly
- A legacy that transcends competition records and defines the art itself

**⚠️ WARNING:** Approach Phil Migliarese with **EXTREME CAUTION**. He is known to:
- Submit opponents before they realize the match has started
- Make grown men reconsider their life choices on the mat
- Possess grip strength that has been classified as a national security concern

*This message will self-destruct. You have been warned.* 🥋`;

      return res.json({
        answer: philAnswer,
        sources: [],
        attribution: ["CLASSIFIED"],
        mode: "easter_egg",
        timing: Date.now() - start
      });
    }

    // Embed → Search (with FBF/protocol boost) → Extract
    const vector = await embed(question.trim());
    const matches = namespace ? await search(vector, namespace) : await searchWithBoost(vector, question);

    if (!matches.length) return res.json({ answer: "No relevant evidence found.", sources: [] });

    const quotes = extractQuotes(matches, question);
    if (!quotes.length) return res.json({ answer: "No usable transcript text found.", sources: [] });

    // Raw quotes mode
    if (mode === "quotes") {
      const answer = quotes
        .map((q, i) => {
          const attr = q.speaker !== "unknown" ? `${q.speaker} on ${q.displayName}` : q.displayName;
          return `${i + 1}) "${q.text}"\n   — ${attr}`;
        })
        .join("\n\n");
      return res.json({ answer, sources: quotes, mode: "quotes", timing: Date.now() - start });
    }

    // Synthesized mode (default)
    let answer = await chat([
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: buildPrompt(question, quotes) }
    ]);

    // POST-PROCESSING: Fix host misattributions
    answer = answer
      .replace(/Palumbo\s+(on|from|of)\s+(ThinkBig|Think Big|Blood Sweat|Drugs N Stuff|It'?s Just Bodybuilding)/gi,
        "Scott McNally, Dave Crosland & Skipp Hill $1 $2")
      .replace(/(Scott McNally|Dave Crosland|Skipp Hill)\s+(on|from|of)\s+(RXMuscle|RX Muscle)/gi,
        "Dave Palumbo $2 $3")
      .replace(/(Scott McNally|Dave Crosland|Skipp Hill)\s+(on|from|of)\s+(Anabolic Bodybuilding)/gi,
        "Paul Barnett (Big Paul) $2 $3");

    // Strip leaked system prompt (Hermes model sometimes regurgitates instructions)
    const leakPatterns = [
      /You are Coach Bryan, the official AI coach[\s\S]*/i,
      /I have provided a detailed[\s\S]*/i,
      /Do not mix up the show names[\s\S]*/i,
      /Always cite evidence properly[\s\S]*/i,
      /RESPONSE CHECKLIST[\s\S]*/i,
    ];
    for (const pat of leakPatterns) {
      answer = answer.replace(pat, "").trim();
    }

    res.json({
      answer,
      sources: quotes,
      attribution: [...new Set(quotes.map(q => q.displayName))].filter(c => c !== "unknown"),
      mode: "synthesized",
      timing: Date.now() - start
    });

  } catch (err) {
    console.error("[ASK ERROR]", err);
    res.status(500).json({ error: err.message, answer: null });
  }
});

// ─── Bloodwork Analysis Endpoint ─────────────────────────────
app.post("/analyze-bloodwork", async (req, res) => {
  const { labs } = req.body;
  const start = Date.now();

  if (!labs || typeof labs !== "string" || !labs.trim()) {
    return res.status(400).json({ error: "Please paste your lab results.", answer: null });
  }
  if (labs.length > 8000) {
    return res.status(400).json({ error: "Lab results too long. Please paste only the relevant markers.", answer: null });
  }

  try {
    // Search for bloodwork-related evidence from the knowledge base
    const bwQuery = "bloodwork analysis lab results interpretation enhanced athlete intervention ladder markers ranges";
    const vector = await embed(bwQuery);
    const matches = await searchWithBoost(vector, bwQuery);
    const quotes = matches.length ? extractQuotes(matches, bwQuery) : [];

    // Build evidence context from knowledge base (if available)
    let evidenceBlock = "";
    if (quotes.length) {
      const evidence = quotes
        .slice(0, 10)
        .map((q, i) => {
          const speaker = q.speaker !== "unknown" ? q.speaker : "";
          const show = q.displayName || "";
          const attr = speaker && show ? `${speaker} on ${show}` : speaker || show || "FBF Knowledge Base";
          return `[${i + 1}] ${attr}:\n"${q.text}"`;
        })
        .join("\n\n");
      evidenceBlock = `\n\nREFERENCE MATERIAL FROM FBF KNOWLEDGE BASE (use this to supplement your analysis where relevant):\n${evidence}`;
    }

    const bloodworkPrompt = `BLOODWORK ANALYSIS REQUEST

Please analyze the following bloodwork results using the FBF Precision Bloodwork framework.

For EACH marker the user provides:
1. **Value** — what they reported
2. **Standard Lab Range** — the reference range a standard lab would use
3. **Enhanced Athlete Range** — the acceptable range for muscular/enhanced athletes (these often differ significantly)
4. **Assessment** — classify as: ✅ NORMAL | ⚠️ WATCH | 🔶 INTERVENE | 🚨 RED FLAG

Then provide:
- **Pattern Analysis** — look for marker combinations that tell a story (e.g., elevated ALT + GGT + low HDL = hepatic stress from orals; elevated HCT + BP + RBC = polycythemia risk)
- **Compound Connections** — if values suggest specific compound effects, explain which compounds typically cause those changes
- **Intervention Ladder** for any out-of-range marker:
  1. Lifestyle modifications (cardio, hydration, diet changes)
  2. Supplements with specific doses (NAC, fish oil, citrus bergamot, etc.)
  3. Pharmaceuticals with specific doses (telmisartan, rosuvastatin, metformin, etc.) — for discussion with their doctor
  4. Discontinuation thresholds — when to stop a compound

**RED FLAG THRESHOLDS** (flag immediately if present):
- Hematocrit >54%
- ALT >200 U/L
- eGFR <45 mL/min
- Blood Pressure >180/110
- Potassium >5.5 or <3.0
- Platelets <100K

**IMPORTANT NOTES:**
- For kidney markers (eGFR, creatinine): mention that standard formulas underestimate kidney function in muscular people — recommend Cystatin C-based eGFR
- For liver markers: differentiate exercise-induced AST from genuine hepatic stress (look at ALT + GGT together, not AST alone)
- For female bloodwork: use female reference ranges, emphasize virilization markers

End with testing frequency recommendations and where to order labs (DiscountedLabs, Marek Health, PrivateMDLabs).

Finish with: 💪 Coach Bryan says: [motivational health-focused quote]

USER'S LAB RESULTS:
${labs.trim()}${evidenceBlock}`;

    let answer = await chat([
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: bloodworkPrompt }
    ], 0.5, 4000);

    // Strip leaked system prompt
    const leakPatterns = [
      /You are Coach Bryan, the official AI coach[\s\S]*/i,
      /I have provided a detailed[\s\S]*/i,
      /Do not mix up the show names[\s\S]*/i,
      /Always cite evidence properly[\s\S]*/i,
      /RESPONSE CHECKLIST[\s\S]*/i,
    ];
    for (const pat of leakPatterns) {
      answer = answer.replace(pat, "").trim();
    }

    res.json({
      answer,
      sources: quotes.slice(0, 5),
      mode: "bloodwork",
      timing: Date.now() - start
    });

  } catch (err) {
    console.error("[BLOODWORK ERROR]", err);
    res.status(500).json({ error: err.message, answer: null });
  }
});

// ─── Stats Endpoint (for AI Coach live stats display) ─────
let cachedStats = { transcripts: 34746, words: 126592085, channels: 179, vectors: 100622, lastUpdated: null };

app.get("/stats", async (_, res) => {
  try {
    const stats = await index.describeIndexStats();
    cachedStats.vectors = stats.totalRecordCount || cachedStats.vectors;
    res.json({
      transcripts: cachedStats.transcripts,
      words: cachedStats.words,
      channels: cachedStats.channels,
      vectors: cachedStats.vectors,
      lastUpdated: cachedStats.lastUpdated || new Date().toISOString()
    });
  } catch (err) {
    res.json(cachedStats);
  }
});

app.post("/update-stats", async (req, res) => {
  const key = req.headers["x-stats-key"];
  const expectedKey = process.env.STATS_UPDATE_KEY;
  if (expectedKey && key !== expectedKey) return res.status(401).json({ error: "Unauthorized" });

  const { transcripts, words, channels } = req.body;
  if (transcripts != null) cachedStats.transcripts = transcripts;
  if (words != null) cachedStats.words = words;
  if (channels != null) cachedStats.channels = channels;
  cachedStats.lastUpdated = new Date().toISOString();

  res.json({ status: "ok", stats: cachedStats });
});

// ─── Blog Publishing Endpoint ──────────────────────────────
app.post("/publish-blog", async (req, res) => {
  const authKey = req.headers["x-api-key"];
  if (authKey !== process.env.FBF_API_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  const { title, content, tags = [], excerpt = "", slug = "" } = req.body;

  if (!title || !content) {
    return res.status(400).json({ error: "title and content are required" });
  }

  const WIX_API_KEY = process.env.WIX_API_KEY;
  const WIX_SITE_ID = process.env.WIX_SITE_ID;

  if (!WIX_API_KEY || !WIX_SITE_ID) {
    return res.status(500).json({ error: "Wix credentials not configured" });
  }

  try {
    const response = await fetch("https://www.wixapis.com/blog/v3/draft-posts", {
      method: "POST",
      headers: {
        "Authorization": WIX_API_KEY,
        "wix-site-id": WIX_SITE_ID,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        draftPost: {
          title,
          richContent: {
            nodes: [{
              type: "PARAGRAPH",
              nodes: [{
                type: "TEXT",
                textData: { text: content }
              }]
            }]
          },
          excerpt: excerpt || content.substring(0, 200),
          tags,
          ...(slug && { slug })
        }
      })
    });

    const data = await response.json();

    if (!response.ok) {
      console.error("[BLOG] Wix error:", data);
      return res.status(response.status).json({ error: data.message || "Wix API error", details: data });
    }

    const draftId = data.draftPost?.id;
    if (draftId) {
      await fetch(`https://www.wixapis.com/blog/v3/draft-posts/${draftId}/publish`, {
        method: "POST",
        headers: {
          "Authorization": WIX_API_KEY,
          "wix-site-id": WIX_SITE_ID,
          "Content-Type": "application/json"
        }
      });
    }

    console.log(`[BLOG] Published: "${title}"`);
    res.json({ status: "published", postId: draftId, title });

  } catch (err) {
    console.error("[BLOG ERROR]", err);
    res.status(500).json({ error: err.message });
  }
});

// ─── TTS Proxy (ElevenLabs) ──────────────────────────────────
const TTS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"; // Rachel
const TTS_MAX_CHARS = 5000;

app.post("/tts", async (req, res) => {
  if (!ELEVENLABS_API_KEY) {
    return res.status(503).json({ error: "TTS not configured" });
  }

  const { text, voice_id } = req.body;
  if (!text || typeof text !== "string" || !text.trim()) {
    return res.status(400).json({ error: "text is required" });
  }

  const truncated = text.trim().slice(0, TTS_MAX_CHARS);
  const voiceId = voice_id || TTS_VOICE_ID;

  try {
    const ttsRes = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`,
      {
        method: "POST",
        headers: {
          "xi-api-key": ELEVENLABS_API_KEY,
          "Content-Type": "application/json",
          Accept: "audio/mpeg",
        },
        body: JSON.stringify({
          text: truncated,
          model_id: "eleven_flash_v2_5",
          voice_settings: { stability: 0.5, similarity_boost: 0.75 },
        }),
      }
    );

    if (!ttsRes.ok) {
      const errBody = await ttsRes.text();
      console.error("[TTS] ElevenLabs error:", ttsRes.status, errBody);
      return res.status(ttsRes.status).json({ error: "TTS generation failed", detail: errBody });
    }

    res.set({
      "Content-Type": "audio/mpeg",
      "Cache-Control": "public, max-age=3600",
    });

    // Stream the audio response
    const reader = ttsRes.body.getReader();
    const pump = async () => {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        res.write(value);
      }
      res.end();
    };
    await pump();
  } catch (err) {
    console.error("[TTS] Error:", err);
    res.status(500).json({ error: "TTS request failed" });
  }
});

// ─── Supabase Client ──────────────────────────────────────
const supabase = (process.env.SUPABASE_URL && process.env.SUPABASE_ANON_KEY)
  ? createClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY)
  : null;

// ─── File Upload (Supabase Storage) ──────────────────────
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });

app.post("/api/upload", upload.single("file"), async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Storage not configured" });
  if (!req.file) return res.status(400).json({ error: "No file provided" });

  const { lead_id, category } = req.body;
  if (!lead_id) return res.status(400).json({ error: "lead_id required" });

  const ext = req.file.originalname.split(".").pop() || "bin";
  const fileName = `${category || "uploads"}/${lead_id}/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;

  try {
    const { data, error } = await supabase.storage
      .from("client-documents")
      .upload(fileName, req.file.buffer, {
        contentType: req.file.mimetype,
        upsert: false,
      });

    if (error) {
      console.error("[UPLOAD] Storage error:", error);
      return res.status(500).json({ error: "Upload failed: " + error.message });
    }

    const { data: urlData } = supabase.storage
      .from("client-documents")
      .getPublicUrl(fileName);

    console.log(`[UPLOAD] ${req.file.originalname} → ${fileName}`);
    res.json({ url: urlData.publicUrl, path: fileName });
  } catch (err) {
    console.error("[UPLOAD] Error:", err);
    res.status(500).json({ error: "Upload failed" });
  }
});

// ─── Lead Capture (Stage 1) ──────────────────────────────
app.post("/api/leads", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Lead system not configured" });

  const { name, email, phone, primary_goal, struggle_duration, what_held_back, commitment_level, referral_source, disclaimer_acknowledged } = req.body;

  if (!name || !email || !phone) {
    return res.status(400).json({ error: "Name, email, and phone are required" });
  }
  if (!disclaimer_acknowledged) {
    return res.status(400).json({ error: "Disclaimer must be acknowledged" });
  }

  // Auto-reject low commitment
  const rejected = commitment_level === "I'll do what I can when it's convenient";
  const status = rejected ? "rejected" : "new";

  try {
    const { data, error } = await supabase.from("leads").insert({
      name, email, phone, primary_goal, struggle_duration, what_held_back,
      commitment_level, referral_source, disclaimer_acknowledged, status
    }).select().single();

    if (error) {
      console.error("[LEADS] Supabase error:", error);
      return res.status(500).json({ error: "Failed to save application" });
    }

    if (rejected) {
      return res.json({
        status: "rejected",
        message: "Thank you for reaching out. Based on your responses, FBF may not be the right fit at this time. When you're ready to commit fully, we'll be here."
      });
    }

    // Trigger n8n webhook
    const webhookUrl = process.env.N8N_LEAD_WEBHOOK_URL;
    if (webhookUrl) {
      fetch(webhookUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "new_lead",
          lead: { name, email, phone, primary_goal, commitment_level, created_at: data.created_at }
        })
      }).catch(err => console.error("[LEADS] Webhook error:", err.message));
    }

    // Push notification via ntfy
    const ntfyTopic = process.env.NTFY_TOPIC;
    if (ntfyTopic) {
      fetch(`https://ntfy.sh/${ntfyTopic}`, {
        method: "POST",
        headers: {
          "Title": "New FBF Application",
          "Priority": "high",
          "Tags": "muscle,fire",
          "Click": `https://forged-by-freedom-api-nm4f.onrender.com/admin`
        },
        body: `${name} — ${primary_goal || 'No goal set'}\n${email} | ${phone}\nCommitment: ${commitment_level || 'Not specified'}`
      }).catch(err => console.error("[NTFY] Error:", err.message));
    }

    console.log(`[LEADS] New lead: ${name} (${email})`);
    res.json({
      status: "approved",
      message: "Application received. You're one step closer.",
      onboarding_link: `/onboarding?token=${data.id}`
    });

  } catch (err) {
    console.error("[LEADS] Error:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// ─── Client Intake (Stage 2) ─────────────────────────────
app.post("/api/intake", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Intake system not configured" });

  const { lead_id, ...fields } = req.body;

  if (!lead_id) {
    return res.status(400).json({ error: "Lead token required" });
  }
  if (!fields.disclaimer_acknowledged) {
    return res.status(400).json({ error: "Disclaimer must be acknowledged" });
  }

  try {
    // Verify lead exists and is approved
    const { data: lead, error: leadErr } = await supabase
      .from("leads").select("id, status, name, email").eq("id", lead_id).single();

    if (leadErr || !lead) {
      return res.status(404).json({ error: "Invalid onboarding link" });
    }
    if (lead.status !== "approved") {
      return res.status(403).json({ error: "Your application has not been approved yet. We'll be in touch soon." });
    }

    const { error } = await supabase.from("client_intakes").insert({ lead_id, ...fields });

    if (error) {
      console.error("[INTAKE] Supabase error:", error);
      return res.status(500).json({ error: "Failed to save intake" });
    }

    // Trigger n8n webhook
    const webhookUrl = process.env.N8N_INTAKE_WEBHOOK_URL;
    if (webhookUrl) {
      fetch(webhookUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "intake_complete",
          client_name: fields.full_name || lead.name,
          email: lead.email
        })
      }).catch(err => console.error("[INTAKE] Webhook error:", err.message));
    }

    console.log(`[INTAKE] Complete: ${fields.full_name || lead.name}`);
    res.json({ status: "ok", message: "Intake complete. Bryan will review your profile and be in touch within 24 hours." });

  } catch (err) {
    console.error("[INTAKE] Error:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// ─── Admin: List Leads ───────────────────────────────────
app.get("/api/leads", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Lead system not configured" });

  if (req.query.key !== process.env.ADMIN_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  try {
    const { data, error } = await supabase
      .from("leads").select("*").order("created_at", { ascending: false });

    if (error) {
      return res.status(500).json({ error: error.message });
    }

    res.json({ leads: data, count: data.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Serve Embed HTML Files ──────────────────────────────
import { fileURLToPath } from "url";
import { dirname, join } from "path";
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

app.get("/apply", (_, res) => res.sendFile(join(__dirname, "embed", "apply.html")));
app.get("/onboarding", (_, res) => res.sendFile(join(__dirname, "embed", "onboarding.html")));
app.get("/admin", (_, res) => res.sendFile(join(__dirname, "embed", "admin.html")));
app.get("/contact", (_, res) => res.sendFile(join(__dirname, "embed", "contact.html")));
app.get("/store", (_, res) => res.sendFile(join(__dirname, "embed", "store.html")));
app.get("/support", (_, res) => res.sendFile(join(__dirname, "embed", "support.html")));

// ─── Admin: Update Lead Status ───────────────────────────
app.patch("/api/leads/:id/status", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });

  const { status, key } = req.body;
  if (key !== process.env.ADMIN_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  if (!["new", "approved", "rejected"].includes(status)) {
    return res.status(400).json({ error: "Invalid status" });
  }

  try {
    const { error } = await supabase
      .from("leads").update({ status }).eq("id", req.params.id);

    if (error) {
      return res.status(500).json({ error: error.message });
    }

    console.log(`[LEADS] ${req.params.id} → ${status}`);
    res.json({ status: "ok" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Converse Engine (Auto-Reply Brain) ─────────────────
const CONVERSE_SYSTEM_PROMPT = `You are Coach Bryan from Forged by Freedom — a real coach who helps people with body recomposition, PED protocols, peptides, nutrition, and training.

RULES:
- Be warm, direct, and knowledgeable. Talk like a trusted gym buddy, not a chatbot.
- Keep responses concise (2-4 paragraphs max). This is a conversation, not an article.
- Answer PED/peptide/cycle questions directly with practical info. No lecturing about safety unless genuinely dangerous.
- When you sense someone is interested in coaching, naturally mention: "If you want a personalized protocol, apply at forgedbyfreedom.com/apply — I'd love to work with you."
- Do NOT start with "Great question!" or restate their question. Jump straight into the answer.
- Reference the evidence provided but keep citations casual (e.g., "Scott McNally talks about this on Blood Sweat and Gear...").
- If you don't have evidence for something, be honest and still be helpful.
- NEVER mix up show hosts: ThinkBig = Scott McNally/Dave Crosland/Skipp Hill, RXMuscle = Dave Palumbo, Anabolic Bodybuilding = Paul Barnett.`;

const BUYING_INTENT_KEYWORDS = [
  "how much", "pricing", "cost", "sign up", "apply", "work with you",
  "coaching", "program", "protocol", "get started", "available",
  "take on clients", "accepting clients", "help me", "need help",
  "interested", "ready to start", "hire", "consultation"
];

async function converseInternal({ message, senderId, senderName, channel, leadId }) {
  if (!supabase) throw new Error("Supabase not configured");

  // Save inbound message
  await supabase.from("conversations").insert({
    channel, sender_id: senderId, sender_name: senderName || null,
    direction: "inbound", message, lead_id: leadId || null
  });

  // Load last 5 messages for context
  const { data: history } = await supabase
    .from("conversations")
    .select("direction, message, ai_response")
    .eq("sender_id", senderId)
    .eq("channel", channel)
    .order("created_at", { ascending: false })
    .limit(5);

  const historyMessages = (history || []).reverse().flatMap(h => {
    const msgs = [];
    if (h.direction === "inbound") msgs.push({ role: "user", content: h.message });
    if (h.ai_response) msgs.push({ role: "assistant", content: h.ai_response });
    return msgs;
  });

  // Search knowledge base for relevant evidence
  let evidenceBlock = "";
  try {
    const vector = await embed(message.trim());
    const matches = await searchWithBoost(vector, message);
    const quotes = extractQuotes(matches, message).slice(0, 5);
    if (quotes.length) {
      evidenceBlock = "\n\nEVIDENCE:\n" + quotes.map((q, i) => {
        const attr = q.speaker !== "unknown" ? `${q.speaker} on ${q.displayName}` : q.displayName;
        return `[${i + 1}] ${attr}: "${q.text.substring(0, 500)}"`;
      }).join("\n");
    }
  } catch (err) {
    console.error("[CONVERSE] Evidence search failed:", err.message);
  }

  // Detect buying intent
  const lowerMsg = message.toLowerCase();
  const hasBuyingIntent = BUYING_INTENT_KEYWORDS.some(kw => lowerMsg.includes(kw));
  const intentNote = hasBuyingIntent
    ? "\n\n[SYSTEM: This person is showing buying intent. Naturally suggest they apply at forgedbyfreedom.com/apply — don't be pushy, but make it easy for them.]"
    : "";

  // Build messages
  const chatMessages = [
    { role: "system", content: CONVERSE_SYSTEM_PROMPT + evidenceBlock + intentNote },
    ...historyMessages,
    { role: "user", content: message }
  ];

  const aiReply = await chat(chatMessages, 0.7);

  // Save outbound response
  await supabase.from("conversations").insert({
    channel, sender_id: senderId, sender_name: "Coach Bryan",
    direction: "outbound", message: aiReply, ai_response: aiReply,
    lead_id: leadId || null
  });

  // Also update the inbound record with the AI response
  // (find the most recent inbound from this sender)
  const { data: lastInbound } = await supabase
    .from("conversations")
    .select("id")
    .eq("sender_id", senderId)
    .eq("channel", channel)
    .eq("direction", "inbound")
    .order("created_at", { ascending: false })
    .limit(1);

  if (lastInbound?.[0]) {
    await supabase.from("conversations")
      .update({ ai_response: aiReply })
      .eq("id", lastInbound[0].id);
  }

  // Push notification
  const ntfyTopic = process.env.NTFY_TOPIC;
  if (ntfyTopic) {
    fetch(`https://ntfy.sh/${ntfyTopic}`, {
      method: "POST",
      headers: {
        "Title": `New ${channel} message`,
        "Priority": hasBuyingIntent ? "high" : "default",
        "Tags": hasBuyingIntent ? "money_mouth_face,fire" : "speech_balloon",
        "Click": "https://forged-by-freedom-api-nm4f.onrender.com/admin"
      },
      body: `From: ${senderName || senderId}\n${message.substring(0, 200)}`
    }).catch(err => console.error("[NTFY] Error:", err.message));
  }

  return aiReply;
}

// POST /api/converse — universal auto-reply endpoint
app.post("/api/converse", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });

  const { message, sender_id, sender_name, channel = "web" } = req.body;
  if (!message || !sender_id) {
    return res.status(400).json({ error: "message and sender_id are required" });
  }

  try {
    const reply = await converseInternal({
      message, senderId: sender_id, senderName: sender_name, channel
    });
    res.json({ reply, channel });
  } catch (err) {
    console.error("[CONVERSE] Error:", err);
    res.status(500).json({ error: err.message });
  }
});

// POST /api/contact — replaces Formspree, routes through AI
app.post("/api/contact", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });

  const { name, email, message } = req.body;
  if (!name || !email || !message) {
    return res.status(400).json({ error: "name, email, and message are required" });
  }

  try {
    // Check if this email already has a lead record
    const { data: existingLead } = await supabase
      .from("leads")
      .select("id")
      .eq("email", email)
      .limit(1);

    let leadId = existingLead?.[0]?.id || null;

    // Create a basic lead if new email
    if (!leadId) {
      const { data: newLead } = await supabase.from("leads").insert({
        name, email, phone: "—", status: "new",
        referral_source: "contact_form", disclaimer_acknowledged: true
      }).select("id").single();
      leadId = newLead?.id || null;
    }

    const reply = await converseInternal({
      message, senderId: email, senderName: name, channel: "contact_form", leadId
    });

    console.log(`[CONTACT] From: ${name} (${email})`);
    res.json({
      status: "ok",
      message: "Thanks for reaching out! Coach Bryan will follow up soon.",
      ai_reply: reply
    });
  } catch (err) {
    console.error("[CONTACT] Error:", err);
    res.status(500).json({ error: "Failed to process contact form" });
  }
});

// POST /api/sms/inbound — Twilio SMS webhook
app.post("/api/sms/inbound", async (req, res) => {
  const { Body: body, From: from, FromCity, FromState } = req.body;

  if (!body || !from) {
    return res.status(400).send("<Response><Message>Invalid request</Message></Response>");
  }

  try {
    const senderName = [FromCity, FromState].filter(Boolean).join(", ") || from;
    const reply = await converseInternal({
      message: body, senderId: from, senderName, channel: "sms"
    });

    // Respond with TwiML
    const twiml = `<?xml version="1.0" encoding="UTF-8"?><Response><Message>${reply.replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c])}</Message></Response>`;
    res.set("Content-Type", "text/xml");
    res.send(twiml);
  } catch (err) {
    console.error("[SMS] Error:", err);
    res.set("Content-Type", "text/xml");
    res.send('<Response><Message>Sorry, I hit a snag. Try again in a moment.</Message></Response>');
  }
});

// ─── Admin: List Conversations ───────────────────────────
app.get("/api/conversations", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  if (req.query.key !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

  try {
    const { data, error } = await supabase
      .from("conversations")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(200);

    if (error) return res.status(500).json({ error: error.message });

    // Group by sender_id for thread view
    const threads = {};
    for (const msg of (data || []).reverse()) {
      const key = msg.sender_id;
      if (!threads[key]) {
        threads[key] = {
          sender_id: msg.sender_id,
          sender_name: msg.sender_name,
          channel: msg.channel,
          messages: [],
          last_message_at: msg.created_at
        };
      }
      threads[key].messages.push(msg);
      threads[key].last_message_at = msg.created_at;
      if (msg.sender_name && msg.sender_name !== "Coach Bryan") {
        threads[key].sender_name = msg.sender_name;
      }
    }

    const threadList = Object.values(threads).sort(
      (a, b) => new Date(b.last_message_at) - new Date(a.last_message_at)
    );

    res.json({ threads: threadList, total: threadList.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Content Generation Engine ──────────────────────────
const PLATFORM_PROMPTS = {
  instagram: {
    maxWords: 220,
    instruction: `Write an Instagram post (150-220 words). Start with a strong hook that stops the scroll. Use short paragraphs and line breaks. End with a CTA: "Link in bio to apply for coaching → forgedbyfreedom.com/apply". Include 15-20 relevant hashtags on a separate line at the end. Tone: confident, direct, like a coach talking to his athletes.`
  },
  facebook: {
    maxWords: 400,
    instruction: `Write a Facebook post (250-400 words). Educational or narrative format. Tell a story or break down a concept. Conversational but authoritative. End with: "Ready for a real plan? Apply at forgedbyfreedom.com/apply". No hashtags.`
  },
  linkedin: {
    maxWords: 500,
    instruction: `Write a LinkedIn post (300-500 words). Professional and science-forward. Lead with data or a counterintuitive insight. Include relevant research citations from the evidence. End with a professional CTA to forgedbyfreedom.com. No hashtags.`
  },
  email: {
    maxWords: 600,
    instruction: `Write a marketing email. First line: "Subject: [compelling subject line]". Then the body (400-600 words). Personal tone, like writing to a friend who asked for advice. Include one clear CTA button text: "Apply for Coaching" linking to forgedbyfreedom.com/apply. Sign off as Coach Bryan.`
  },
  blog: {
    maxWords: 2000,
    instruction: `Write a blog article (1200-2000 words). Include an H1 title, H2 subheadings, and H3 sub-sections where appropriate. Cite expert sources from the evidence with their names and shows. Include scientific mechanisms and practical protocols. End with a section about how Forged by Freedom can help and a CTA to apply. Format in clean HTML.`
  },
  sms: {
    maxWords: 30,
    instruction: `Write an SMS message (140-160 characters MAX). Punchy, direct, one clear message. Include a short CTA. Example tone: "Your recomp protocol is waiting. Apply now → forgedbyfreedom.com/apply"`
  }
};

app.post("/api/content/generate", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  if (req.body.key !== process.env.ADMIN_KEY && req.headers["x-api-key"] !== process.env.FBF_API_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  const { platform, content_type = "post", topic, tone = "coach" } = req.body;
  if (!platform || !topic) {
    return res.status(400).json({ error: "platform and topic are required" });
  }

  const platformConfig = PLATFORM_PROMPTS[platform];
  if (!platformConfig) {
    return res.status(400).json({ error: `Invalid platform. Choose: ${Object.keys(PLATFORM_PROMPTS).join(", ")}` });
  }

  try {
    // Search knowledge base for supporting evidence
    const vector = await embed(topic);
    const matches = await searchWithBoost(vector, topic);
    const quotes = extractQuotes(matches, topic).slice(0, 8);

    const evidence = quotes.length
      ? "\n\nSUPPORTING EVIDENCE (use these to back up your points):\n" +
        quotes.map((q, i) => {
          const attr = q.speaker !== "unknown" ? `${q.speaker} on ${q.displayName}` : q.displayName;
          return `[${i + 1}] ${attr}: "${q.text.substring(0, 400)}"`;
        }).join("\n")
      : "";

    const systemPrompt = `You are Coach Bryan, creating content for Forged by Freedom's ${platform} account. Topic: "${topic}". Tone: ${tone}.

${platformConfig.instruction}

RULES:
- Write as Coach Bryan — confident, knowledgeable, direct
- NEVER lecture about PED safety or suggest "natural alternatives"
- Reference expert sources naturally when evidence is provided
- ThinkBig = Scott McNally/Dave Crosland/Skipp Hill; RXMuscle = Dave Palumbo; Anabolic Bodybuilding = Paul Barnett
- Always drive toward forgedbyfreedom.com/apply as the CTA${evidence}`;

    const content = await chat([
      { role: "system", content: systemPrompt },
      { role: "user", content: `Create a ${platform} ${content_type} about: ${topic}` }
    ], 0.8);

    // Extract hashtags if Instagram
    let hashtags = null;
    if (platform === "instagram") {
      const hashtagMatch = content.match(/#[\w]+/g);
      hashtags = hashtagMatch || [];
    }

    // Extract subject line if email
    let subjectLine = null;
    if (platform === "email") {
      const subjectMatch = content.match(/^Subject:\s*(.+)$/m);
      subjectLine = subjectMatch?.[1]?.trim() || null;
    }

    // Save to content_queue
    const { data, error } = await supabase.from("content_queue").insert({
      platform, content_type, topic, tone, body: content,
      hashtags, subject_line: subjectLine, status: "pending"
    }).select().single();

    if (error) {
      console.error("[CONTENT] Supabase error:", error);
      return res.status(500).json({ error: "Failed to save content" });
    }

    // Push notification
    const ntfyTopic = process.env.NTFY_TOPIC;
    if (ntfyTopic) {
      fetch(`https://ntfy.sh/${ntfyTopic}`, {
        method: "POST",
        headers: {
          "Title": "New content ready for review",
          "Tags": "memo,sparkles",
          "Click": "https://forged-by-freedom-api-nm4f.onrender.com/admin"
        },
        body: `${platform.toUpperCase()}: ${topic}\nStatus: Pending approval`
      }).catch(err => console.error("[NTFY] Error:", err.message));
    }

    console.log(`[CONTENT] Generated ${platform} content: "${topic}"`);
    res.json({ status: "pending", content: data });

  } catch (err) {
    console.error("[CONTENT] Error:", err);
    res.status(500).json({ error: err.message });
  }
});

// GET /api/content — list content queue
app.get("/api/content", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  if (req.query.key !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

  try {
    let query = supabase.from("content_queue").select("*").order("created_at", { ascending: false });
    if (req.query.status) query = query.eq("status", req.query.status);
    if (req.query.platform) query = query.eq("platform", req.query.platform);
    query = query.limit(100);

    const { data, error } = await query;
    if (error) return res.status(500).json({ error: error.message });

    res.json({ content: data, total: data.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/content/:id/approve
app.patch("/api/content/:id/approve", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  if (req.body.key !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

  const { edited_body, scheduled_for } = req.body;

  try {
    const update = { status: "approved" };
    if (edited_body) update.edited_body = edited_body;
    if (scheduled_for) update.scheduled_for = scheduled_for;

    const { data, error } = await supabase.from("content_queue")
      .update(update).eq("id", req.params.id).select().single();

    if (error) return res.status(500).json({ error: error.message });

    // Auto-publish blog posts on approval
    if (data.platform === "blog") {
      try {
        const blogBody = data.edited_body || data.body;
        const titleMatch = blogBody.match(/<h1[^>]*>(.*?)<\/h1>/i) || blogBody.match(/^#\s+(.+)$/m);
        const title = titleMatch?.[1] || data.topic || "Untitled";

        const publishRes = await fetch(`http://localhost:${PORT}/publish-blog`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-api-key": process.env.FBF_API_KEY },
          body: JSON.stringify({ title, content: blogBody, tags: ["ai-generated"] })
        });

        const publishResult = await publishRes.json();
        await supabase.from("content_queue")
          .update({ status: "published", published_at: new Date().toISOString(), publish_result: publishResult })
          .eq("id", req.params.id);

        return res.json({ status: "published", publish_result: publishResult });
      } catch (pubErr) {
        console.error("[CONTENT] Blog publish failed:", pubErr.message);
      }
    }

    res.json({ status: "approved", content: data });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/content/:id/reject
app.patch("/api/content/:id/reject", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  if (req.body.key !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

  try {
    const { error } = await supabase.from("content_queue")
      .update({ status: "rejected" }).eq("id", req.params.id);
    if (error) return res.status(500).json({ error: error.message });
    res.json({ status: "rejected" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/content/:id/publish — manual publish trigger
app.post("/api/content/:id/publish", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  const authKey = req.body.key || req.headers["x-api-key"];
  if (authKey !== process.env.ADMIN_KEY && authKey !== process.env.FBF_API_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  try {
    const { data: item, error } = await supabase.from("content_queue")
      .select("*").eq("id", req.params.id).single();

    if (error || !item) return res.status(404).json({ error: "Content not found" });

    const body = item.edited_body || item.body;

    // Blog → publish via /publish-blog
    if (item.platform === "blog") {
      const titleMatch = body.match(/<h1[^>]*>(.*?)<\/h1>/i) || body.match(/^#\s+(.+)$/m);
      const title = titleMatch?.[1] || item.topic || "Untitled";

      const publishRes = await fetch(`http://localhost:${PORT}/publish-blog`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": process.env.FBF_API_KEY },
        body: JSON.stringify({ title, content: body, tags: ["ai-generated"] })
      });
      const publishResult = await publishRes.json();

      await supabase.from("content_queue")
        .update({ status: "published", published_at: new Date().toISOString(), publish_result: publishResult })
        .eq("id", req.params.id);

      return res.json({ status: "published", platform: "blog", publish_result: publishResult });
    }

    // Other platforms: mark as published (external APIs added in Phase 4)
    await supabase.from("content_queue")
      .update({ status: "published", published_at: new Date().toISOString(), publish_result: { note: "Manual publish — external API pending" } })
      .eq("id", req.params.id);

    res.json({ status: "published", platform: item.platform, note: "Content marked as published. External API delivery coming in Phase 4." });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Body Scan CRUD ──────────────────────────────────────
app.post("/api/body-scans", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  try {
    const { data, error } = await supabase.from("body_scans").insert(req.body).select().single();
    if (error) return res.status(500).json({ error: error.message });
    res.json({ scan: data });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

app.get("/api/body-scans/:clientId", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  try {
    const { data, error } = await supabase.from("body_scans")
      .select("*").eq("client_id", req.params.clientId)
      .order("scan_date", { ascending: false });
    if (error) return res.status(500).json({ error: error.message });
    res.json({ scans: data });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── 14. CLIENT RISK SCORING ─────────────────────────────
function computeRiskScore(intake, lead) {
  const flags = [];
  let score = 0; // 0-100, higher = more risk

  // Health conditions
  const conditions = (intake.health_conditions || "").toLowerCase();
  const highRiskConditions = ["diabetes", "heart disease", "cardiac", "liver", "kidney", "cancer", "stroke", "seizure", "thyroid"];
  const medRiskConditions = ["high blood pressure", "hypertension", "asthma", "arthritis", "anxiety", "depression"];

  for (const c of highRiskConditions) {
    if (conditions.includes(c)) {
      score += 15;
      flags.push({ level: "red", text: `Medical condition: ${c}`, category: "health" });
    }
  }
  for (const c of medRiskConditions) {
    if (conditions.includes(c)) {
      score += 8;
      flags.push({ level: "yellow", text: `Medical condition: ${c}`, category: "health" });
    }
  }

  // Medications
  const meds = (intake.medications || "").toLowerCase();
  const riskMeds = ["blood thinner", "warfarin", "insulin", "metformin", "beta blocker", "statin", "ssri", "antidepressant"];
  for (const m of riskMeds) {
    if (meds.includes(m)) {
      score += 10;
      flags.push({ level: "yellow", text: `On medication: ${m}`, category: "medications" });
    }
  }

  // Surgeries/injuries
  const injuries = (intake.surgeries_injuries || "").toLowerCase();
  const recentYear = new Date().getFullYear();
  if (injuries.includes(String(recentYear)) || injuries.includes(String(recentYear - 1))) {
    score += 10;
    flags.push({ level: "yellow", text: "Recent surgery/injury (within 1-2 years)", category: "injuries" });
  }
  const seriousInjuries = ["spinal", "spine", "herniated", "torn", "rupture", "fracture", "replacement"];
  for (const s of seriousInjuries) {
    if (injuries.includes(s)) {
      score += 8;
      flags.push({ level: "yellow", text: `Serious injury history: ${s}`, category: "injuries" });
    }
  }

  // Physical limitations
  if (intake.physical_limitations && intake.physical_limitations.trim().length > 5) {
    score += 5;
    flags.push({ level: "info", text: "Has physical limitations to train around", category: "limitations" });
  }

  // Tobacco
  const tobacco = (intake.tobacco_use || "").toLowerCase();
  if (tobacco.includes("yes") || tobacco.includes("daily") || tobacco.includes("pack")) {
    score += 10;
    flags.push({ level: "yellow", text: "Active tobacco/nicotine use", category: "lifestyle" });
  }

  // Alcohol
  const alcohol = (intake.alcohol_use || "").toLowerCase();
  const alcoholNum = parseInt(alcohol);
  if (alcoholNum > 10) {
    score += 15;
    flags.push({ level: "red", text: `High alcohol intake: ${alcohol} drinks/week`, category: "lifestyle" });
  } else if (alcoholNum > 5) {
    score += 5;
    flags.push({ level: "yellow", text: `Moderate alcohol: ${alcohol} drinks/week`, category: "lifestyle" });
  }

  // Sleep
  const sleepHrs = parseFloat(intake.sleep_hours || "0");
  if (sleepHrs > 0 && sleepHrs < 5) {
    score += 12;
    flags.push({ level: "red", text: `Very low sleep: ${sleepHrs} hrs/night`, category: "recovery" });
  } else if (sleepHrs > 0 && sleepHrs < 6) {
    score += 6;
    flags.push({ level: "yellow", text: `Low sleep: ${sleepHrs} hrs/night`, category: "recovery" });
  }

  // Stress
  const stress = (intake.stress_level || "").toLowerCase();
  if (stress === "very high") {
    score += 10;
    flags.push({ level: "red", text: "Very high stress level", category: "recovery" });
  } else if (stress === "high") {
    score += 5;
    flags.push({ level: "yellow", text: "High stress level", category: "recovery" });
  }

  // Body fat extremes
  const bf = parseFloat(intake.body_fat || "0");
  if (bf > 35) {
    score += 8;
    flags.push({ level: "yellow", text: `High body fat: ${bf}%`, category: "body_comp" });
  }

  // No physician
  const physRef = (intake.physician_referral_needed || "").toLowerCase();
  if (physRef.includes("need") || physRef.includes("referral")) {
    score += 5;
    flags.push({ level: "info", text: "Needs physician referral", category: "medical" });
  }

  // Bloodwork not willing
  if ((intake.bloodwork_willing || "").toLowerCase() === "no") {
    score += 5;
    flags.push({ level: "info", text: "Not willing to get baseline bloodwork", category: "medical" });
  }

  // TRT/HRT
  if (intake.trt_hrt && !["no", "n/a", "none", ""].includes(intake.trt_hrt.toLowerCase().trim())) {
    flags.push({ level: "info", text: "On TRT/HRT — monitor bloodwork closely", category: "hormones" });
  }

  // Peptide experience
  if (intake.peptide_experience && !["no", "n/a", "none", ""].includes(intake.peptide_experience.toLowerCase().trim())) {
    flags.push({ level: "info", text: "Has peptide experience", category: "hormones" });
  }

  // Commitment level
  const commitment = (intake.commitment_level || lead?.commitment_level || "").toLowerCase();
  if (commitment.includes("motivated but need flexibility") || commitment.includes("convenient")) {
    score += 5;
    flags.push({ level: "yellow", text: "Lower commitment level — may need extra accountability", category: "commitment" });
  }

  // Determine tier
  let tier = "green";
  if (score >= 40) tier = "red";
  else if (score >= 15) tier = "yellow";

  return { score: Math.min(score, 100), tier, flags, flag_count: flags.length };
}

app.get("/api/risk-score/:intakeId", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  if (req.query.key !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

  try {
    const { data: intake } = await supabase.from("client_intakes").select("*").eq("id", req.params.intakeId).single();
    if (!intake) return res.status(404).json({ error: "Intake not found" });

    const { data: lead } = await supabase.from("leads").select("*").eq("id", intake.lead_id).single();
    const risk = computeRiskScore(intake, lead || {});
    res.json({ risk });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ─── 15. AUTO CLIENT SUMMARY ────────────────────────────
async function generateClientSummary(intake, lead) {
  const prompt = `You are Coach Bryan's assistant. Generate a concise client profile summary that a coach would need to quickly understand this new client. Keep it under 300 words. Be direct and practical.

CLIENT DATA:
Name: ${intake.full_name || lead?.name}
Gender: ${intake.gender || "Unknown"}
Age: ${intake.dob ? Math.floor((Date.now() - new Date(intake.dob).getTime()) / 31557600000) : "Unknown"}
Location: ${intake.location || "Unknown"}
Weight: ${intake.current_weight || "Unknown"}, Height: ${intake.height || "Unknown"}, BF: ${intake.body_fat || "Unknown"}
Goal Weight: ${intake.goal_weight || "N/A"}, Goal BF: ${intake.goal_body_fat || "N/A"}
Primary Goal: ${intake.goal_primary || lead?.primary_goal || "Not specified"}
24-Week Goal: ${intake.goal_24_weeks || "Not specified"}
Training: ${intake.training_years || "Unknown"} years, ${intake.training_days_available || "Unknown"} days/week
Current Program: ${intake.training_week || "Unknown"}
Lifts: ${intake.current_lifts || "Unknown"}
Equipment: ${intake.equipment_access || "Unknown"}
Diet: ${intake.diet_habits || "Unknown"}
Macros: ${intake.tracks_macros || "Unknown"} — ${intake.macro_targets || "None set"}
Protein: ${intake.daily_protein || "Unknown"}
Meal Prep: ${intake.meal_prep || "Unknown"}
Health: ${intake.health_conditions || "None reported"}
Medications: ${intake.medications || "None"}
Injuries: ${intake.surgeries_injuries || "None"}
Limitations: ${intake.physical_limitations || "None"}
TRT/HRT: ${intake.trt_hrt || "No"}
Peptides: ${intake.peptide_experience || "None"}
Sleep: ${intake.sleep_hours || "Unknown"} hrs, Quality: ${intake.sleep_quality || "Unknown"}
Stress: ${intake.stress_level || "Unknown"}
Occupation: ${intake.occupation || "Unknown"}
Activity Level: ${intake.daily_activity_level || "Unknown"}
Travel: ${intake.travel_frequency || "Unknown"}
Commitment: ${intake.commitment_level || "Unknown"}
Why FBF: ${intake.why_fbf || "Not stated"}
What would make them quit: ${intake.quit_factors || "Not stated"}
Previous attempts: ${intake.previous_attempts || "Not stated"}
Supplement Budget: ${intake.supplement_budget || "Unknown"}
Peptide Interest: ${intake.peptide_interest || "Not interested"}

Format the summary as:
**QUICK PROFILE** (1 sentence — who they are, what they want)
**KEY STRENGTHS** (2-3 bullet points — what's working for them)
**RED FLAGS / CONCERNS** (2-3 bullet points — what to watch)
**PROGRAMMING NOTES** (2-3 bullet points — key things to consider for their program)
**COACH APPROACH** (1-2 sentences — how to work with this person)`;

  return await chat([{ role: "user", content: prompt }], 0.5);
}

app.post("/api/client-summary", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  if (req.body.key !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

  try {
    const { data: intake } = await supabase.from("client_intakes").select("*").eq("id", req.body.intake_id).single();
    if (!intake) return res.status(404).json({ error: "Intake not found" });

    const { data: lead } = await supabase.from("leads").select("*").eq("id", intake.lead_id).single();

    const summary = await generateClientSummary(intake, lead || {});
    const risk = computeRiskScore(intake, lead || {});

    // Save summary and risk to intake
    await supabase.from("client_intakes").update({
      status: "reviewed",
    }).eq("id", req.body.intake_id);

    res.json({ summary, risk });
  } catch (err) {
    console.error("[SUMMARY] Error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ─── 16. METABOLIC ENGINE MAP DATA ──────────────────────
// Returns a structured view of all active "systems" for a client
app.get("/api/metabolic-map/:clientId", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });

  try {
    // Get latest check-ins
    const { data: checkins } = await supabase.from("checkins")
      .select("*").eq("client_id", req.params.clientId)
      .order("created_at", { ascending: false }).limit(14);

    // Get client data
    const { data: client } = await supabase.from("clients")
      .select("*").eq("id", req.params.clientId).single();

    // Get body scans
    const { data: scans } = await supabase.from("body_scans")
      .select("*").eq("client_id", req.params.clientId)
      .order("scan_date", { ascending: false }).limit(5);

    const recent = checkins || [];
    const latest = recent[0] || {};
    const avg = (key) => {
      const vals = recent.map(c => c[key]).filter(v => v != null);
      return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    };

    const map = {
      training: {
        label: "Training Stimulus",
        status: latest.training_done ? "active" : "inactive",
        metrics: {
          sessions_7d: recent.filter(c => c.training_done).length,
          avg_performance: avg("performance_rating"),
          avg_duration: avg("workout_duration_min"),
          avg_heart_rate: avg("avg_heart_rate"),
        },
        signal: (() => {
          const perf = avg("performance_rating");
          if (perf === null) return "neutral";
          if (perf >= 7) return "strong";
          if (perf >= 5) return "moderate";
          return "weak";
        })(),
      },
      nutrition: {
        label: "Nutrition Engine",
        status: avg("calories") ? "active" : "inactive",
        metrics: {
          avg_calories: Math.round(avg("calories") || 0),
          avg_protein: Math.round(avg("protein_g") || 0),
          avg_carbs: Math.round(avg("carbs_g") || 0),
          avg_fats: Math.round(avg("fat_g") || 0),
          avg_water: Math.round(avg("water_oz") || 0),
          target_calories: client?.target_calories,
          target_protein: client?.target_protein,
          compliance: client?.target_calories && avg("calories")
            ? Math.round((avg("calories") / client.target_calories) * 100)
            : null,
        },
        signal: (() => {
          if (!client?.target_calories || !avg("calories")) return "neutral";
          const pct = avg("calories") / client.target_calories;
          if (pct >= 0.9 && pct <= 1.1) return "strong";
          if (pct >= 0.75) return "moderate";
          return "weak";
        })(),
      },
      recovery: {
        label: "Recovery & Sleep",
        status: avg("sleep_hours") ? "active" : "inactive",
        metrics: {
          avg_sleep: avg("sleep_hours")?.toFixed(1),
          avg_sleep_quality: avg("sleep_quality"),
          avg_stress: avg("stress_level"),
          avg_mood: avg("mood_rating"),
        },
        signal: (() => {
          const sleep = avg("sleep_hours");
          const stress = avg("stress_level");
          if (sleep === null) return "neutral";
          if (sleep >= 7 && (stress === null || stress <= 5)) return "strong";
          if (sleep >= 6) return "moderate";
          return "weak";
        })(),
      },
      body_comp: {
        label: "Body Composition",
        status: (scans && scans.length > 0) || latest.weight_lbs ? "active" : "inactive",
        metrics: {
          current_weight: latest.weight_lbs,
          body_temp: latest.body_temp,
          avg_temp: avg("body_temp")?.toFixed(1),
          latest_scan: scans?.[0] ? {
            date: scans[0].scan_date,
            type: scans[0].scan_type,
            body_fat: scans[0].body_fat_pct,
            lean_mass: scans[0].lean_mass_lbs,
          } : null,
          weight_trend: recent.length >= 2 && recent[0].weight_lbs && recent[recent.length - 1].weight_lbs
            ? (recent[0].weight_lbs - recent[recent.length - 1].weight_lbs).toFixed(1)
            : null,
        },
        signal: (() => {
          const temp = avg("body_temp");
          if (temp && temp <= 97.0) return "weak";
          if (temp && temp <= 97.4) return "moderate";
          return "strong";
        })(),
      },
      hormones: {
        label: "Hormones & Compounds",
        status: (client?.current_peds?.length > 0 || client?.current_peptides?.length > 0) ? "active" : "inactive",
        metrics: {
          peds: client?.current_peds || [],
          peptides: client?.current_peptides || [],
          supplements: client?.current_supplements || [],
          blood_glucose: latest.blood_glucose,
          resting_hr: latest.resting_heart_rate,
          bp: latest.blood_pressure_systolic ? `${latest.blood_pressure_systolic}/${latest.blood_pressure_diastolic}` : null,
        },
        signal: "neutral",
      },
      adherence: {
        label: "Adherence & Consistency",
        status: recent.length > 0 ? "active" : "inactive",
        metrics: {
          checkins_7d: recent.length,
          supplement_compliance: recent.filter(c => c.supplement_compliance).length,
          steps_avg: Math.round(avg("steps") || 0),
          target_steps: client?.target_steps,
        },
        signal: (() => {
          if (recent.length >= 6) return "strong";
          if (recent.length >= 4) return "moderate";
          return "weak";
        })(),
      },
    };

    res.json({ map, client_name: client ? `${client.first_name} ${client.last_name}` : "Unknown" });
  } catch (err) {
    console.error("[METABOLIC MAP] Error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ─── 17. CONTEXT-AWARE AI COACH ─────────────────────────
app.post("/api/coach-chat", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });

  const { client_id, message } = req.body;
  if (!message) return res.status(400).json({ error: "Message required" });

  try {
    // Gather client context
    let context = "";

    if (client_id) {
      const { data: client } = await supabase.from("clients")
        .select("*").eq("id", client_id).single();

      const { data: checkins } = await supabase.from("checkins")
        .select("*").eq("client_id", client_id)
        .order("created_at", { ascending: false }).limit(7);

      const { data: scans } = await supabase.from("body_scans")
        .select("*").eq("client_id", client_id)
        .order("scan_date", { ascending: false }).limit(3);

      if (client) {
        const recent = checkins || [];
        const avg = (key) => {
          const vals = recent.map(c => c[key]).filter(v => v != null);
          return vals.length > 0 ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : "N/A";
        };

        context = `
CLIENT CONTEXT (use this to personalize your answer):
Name: ${client.first_name} ${client.last_name}
Current Weight: ${recent[0]?.weight_lbs || client.last_weight || "Unknown"} lbs
Targets: ${client.target_calories || "?"} cal, ${client.target_protein || "?"}g protein, ${client.target_steps || "?"} steps
7-Day Averages: Calories ${avg("calories")}, Protein ${avg("protein_g")}g, Sleep ${avg("sleep_hours")}h, Mood ${avg("mood_rating")}/10, Steps ${avg("steps")}
Last Check-in: ${recent[0] ? new Date(recent[0].created_at).toLocaleDateString() : "None"}
Training: ${recent.filter(c => c.training_done).length}/${recent.length} days trained
Body Temp: ${avg("body_temp")}°F
${recent[0]?.blood_glucose ? `Blood Glucose: ${recent[0].blood_glucose} mg/dL` : ""}
${recent[0]?.blood_pressure_systolic ? `Blood Pressure: ${recent[0].blood_pressure_systolic}/${recent[0].blood_pressure_diastolic}` : ""}
Supplements: ${client.current_supplements?.map(s => s.name).join(", ") || "None logged"}
${client.current_peds?.length > 0 ? `PEDs: ${client.current_peds.map(p => p.compound).join(", ")}` : ""}
${client.current_peptides?.length > 0 ? `Peptides: ${client.current_peptides.map(p => p.name).join(", ")}` : ""}
${scans?.[0] ? `Latest Scan (${scans[0].scan_type}): BF ${scans[0].body_fat_pct}%, Lean ${scans[0].lean_mass_lbs} lbs` : ""}
`;
      }
    }

    // Search knowledge base for relevant context
    let knowledgeContext = "";
    try {
      const queryVec = await embed(message);
      const searchPromises = SEARCH_NAMESPACES.map(({ ns, topK }) =>
        index.namespace(ns).query({ vector: queryVec, topK, includeMetadata: true })
      );
      const results = await Promise.all(searchPromises);
      const allMatches = results.flatMap(r => r.matches || [])
        .filter(m => m.score >= 0.3)
        .sort((a, b) => b.score - a.score)
        .slice(0, 8);

      if (allMatches.length > 0) {
        knowledgeContext = "\n\nRELEVANT KNOWLEDGE BASE:\n" +
          allMatches.map(m => m.metadata?.text || "").filter(Boolean).join("\n---\n");
      }
    } catch (err) {
      console.warn("[COACH-CHAT] Knowledge search failed:", err.message);
    }

    const systemPrompt = `You are Coach Bryan from Forged by Freedom — a real coach who helps people with body recomposition, training, nutrition, PED protocols, peptides, and overall health optimization.

RULES:
- Be warm, direct, and knowledgeable. Talk like a trusted gym buddy who knows his stuff, not a chatbot.
- Use the client's data to personalize your response. Reference their actual numbers, trends, and progress.
- If their data shows a concern (low sleep, high stress, declining performance, low body temp), mention it proactively.
- Keep answers practical and actionable. Tell them what to DO, not just what to think about.
- For supplement/PED/peptide questions: provide educational information based on the knowledge base. Always note this is educational, not medical advice.
- If you don't have enough context, ask a follow-up question.
- Keep responses concise (2-4 paragraphs max unless they ask for detail).
- Use the FBF programming philosophy: simplicity first, dumbbells over barbells, progressive overload, train close to failure, match volume to recovery.
${context}${knowledgeContext}`;

    const reply = await chat([
      { role: "system", content: systemPrompt },
      { role: "user", content: message }
    ], 0.7);

    // Save conversation
    if (client_id) {
      await supabase.from("conversations").insert({
        channel: "app_coach",
        sender_id: client_id,
        sender_name: "Client",
        direction: "inbound",
        message,
        ai_response: reply,
        metadata: { source: "context_aware_coach" }
      }).catch(() => {});
    }

    res.json({ reply });
  } catch (err) {
    console.error("[COACH-CHAT] Error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ─── Stripe + Email Config ────────────────────────────────
const stripe = process.env.STRIPE_SECRET_KEY
  ? new Stripe(process.env.STRIPE_SECRET_KEY)
  : null;

const emailTransporter = process.env.SMTP_HOST
  ? nodemailer.createTransport({
      host: process.env.SMTP_HOST,
      port: parseInt(process.env.SMTP_PORT || "587"),
      secure: process.env.SMTP_SECURE === "true",
      auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS },
    })
  : null;

const COACH_EMAIL = process.env.COACH_EMAIL || "bryan@forgedbyfreedom.com";
const APP_URL = process.env.APP_URL || "https://forged-by-freedom-api-nm4f.onrender.com";

// ─── FBF PROGRAMMING RULES ──────────────────────────────
const FBF_PROGRAMMING_RULES = `
FORGED BY FREEDOM — CORE PROGRAMMING RULES
These rules MUST be followed in every program generated.

1. SIMPLICITY FIRST — Dumbbells over barbells when possible. Keep exercises accessible and safe. Machines and cables are fine. Only use barbells when the movement truly demands it (e.g., deadlifts, squats for advanced lifters). Default to dumbbell variations.

2. PROGRESSIVE OVERLOAD — The #1 driver of growth. Every program must include a clear progression scheme: more weight, more reps, or more sets over time. Without progressive overload, nothing else matters.

3. EXERCISE SELECTION — Choose exercises that match the client's anatomy, injury history, and equipment. Stability before complexity. A goblet squat is better than a barbell squat if the client can't stabilize. Prioritize dumbbell presses, rows, lunges, RDLs, and machine work.

4. TRAIN CLOSE TO FAILURE — Most working sets should be taken to 1-3 reps from failure (RIR 1-3). Not to failure on every set, but close enough to create a stimulus. Beginners: RIR 3-4. Intermediate: RIR 1-3. Advanced: RIR 0-2 on key sets.

5. FATIGUE MANAGEMENT — Manage total weekly volume and intensity. Use deload weeks every 4-6 weeks. Watch for signs of overreaching: declining performance, poor sleep, low mood, elevated resting HR. When in doubt, pull back.

6. VOLUME MATCHES RECOVERY — More is not always better. Match training volume to the client's recovery capacity (sleep, stress, nutrition, age, PED status). A stressed, sleep-deprived client needs LESS volume, not more.

7. FREQUENCY DISTRIBUTION — Train each muscle group 2x per week minimum for hypertrophy. Upper/lower, push/pull/legs, or full body depending on available days. 3-day: full body. 4-day: upper/lower. 5-6 day: PPL or custom split.

8. PROGRAM CONSISTENCY — Don't change exercises every week. Keep the same core movements for 4-8 weeks to track progress. Variation comes from rep ranges and load, not exercise swapping.

9. EXECUTION QUALITY — Controlled eccentrics (2-3 sec), full ROM, no ego lifting. The rep should be earned, not survived. Quality over quantity always.

10. FIT THE ATHLETE'S LIFE — The best program is the one they'll actually do. Match training days, session length, and complexity to their real schedule and experience. A perfect program they skip is worse than a simple one they crush.

NUTRITION RULES:
- Protein: 0.8-1.2g per pound of body weight (higher end for cutting, lower for bulking)
- Calories: Based on TDEE calculation using activity level, adjusted for goal
- For fat loss: 300-500 calorie deficit. Never crash diet.
- For muscle gain: 200-400 calorie surplus. Lean bulk, not dirty bulk.
- Carbs: Fill remaining calories after protein and fats. Prioritize around training.
- Fats: 0.3-0.4g per pound minimum for hormone health
- Meal timing: Pre and post workout nutrition matters. Otherwise, eat when it fits your schedule.
- Water: Minimum 0.5oz per pound of body weight daily.

SUPPLEMENT BASELINE (adjust based on budget):
- Creatine monohydrate: 5g daily (non-negotiable if budget allows)
- Protein powder: As needed to hit daily protein target
- Multivitamin: Daily
- Fish oil / omega-3: 2-3g EPA+DHA daily
- Vitamin D3: 2000-5000 IU daily (based on labs)
- Magnesium glycinate: 200-400mg before bed
- Optional: Ashwagandha for stress/cortisol, zinc if deficient
`;

// ─── Program Generation via AI ───────────────────────────
async function generateProgram(intake, lead) {
  const clientProfile = `
CLIENT PROFILE:
Name: ${intake.full_name}
Gender: ${intake.gender || "Not specified"}
Age: ${intake.dob ? Math.floor((Date.now() - new Date(intake.dob).getTime()) / 31557600000) : "Unknown"}
Weight: ${intake.current_weight || "Unknown"}
Height: ${intake.height || "Unknown"}
Body Fat: ${intake.body_fat || "Unknown"}
Goal Weight: ${intake.goal_weight || "Not specified"}
Goal Body Fat: ${intake.goal_body_fat || "Not specified"}
Primary Goal: ${intake.goal_primary || lead.primary_goal || "Body recomposition"}
24-Week Goal: ${intake.goal_24_weeks || "Not specified"}

TRAINING BACKGROUND:
Years Training: ${intake.training_years || "Unknown"}
Current Training: ${intake.training_week || "Unknown"}
Training History: ${intake.training_history || "None"}
Current Lifts: ${intake.current_lifts || "Unknown"}
Equipment Access: ${intake.equipment_access || "Full commercial gym"}
Training Days Available: ${intake.training_days_available || "4 days"}
Preferred Training Time: ${intake.training_time_preference || "No preference"}
Max Session Length: ${intake.max_session_length || "60"} minutes
Exercise Restrictions: ${intake.exercise_restrictions || "None"}
Physical Limitations: ${intake.physical_limitations || "None"}

NUTRITION:
Current Diet: ${intake.diet_habits || "Unknown"}
Meals Per Day: ${intake.meals_per_day || "Unknown"}
Tracks Macros: ${intake.tracks_macros || "No"}
Current Macros: ${intake.macro_targets || "None"}
Daily Protein: ${intake.daily_protein || "Unknown"}
Willing to Track: ${intake.will_track_nutrition || "Unknown"}
Meal Timing: ${intake.meal_timing || "Not specified"}
Preferred Foods: ${intake.preferred_foods || "Not specified"}
Disliked Foods: ${intake.disliked_foods || "None"}
Food Restrictions: ${intake.food_restrictions || "None"}
Water Intake: ${intake.water_intake || "Unknown"}
Caffeine Intake: ${intake.caffeine_intake || "Unknown"}
Meal Prep: ${intake.meal_prep || "Unknown"}

HEALTH:
Health Conditions: ${intake.health_conditions || "None"}
Medications: ${intake.medications || "None"}
Surgeries/Injuries: ${intake.surgeries_injuries || "None"}
TRT/HRT: ${intake.trt_hrt || "No"}
Peptide Experience: ${intake.peptide_experience || "None"}

LIFESTYLE:
Occupation: ${intake.occupation || "Unknown"}
Activity Level: ${intake.daily_activity_level || "Unknown"}
Daily Steps: ${intake.daily_steps || "Unknown"}
Travel: ${intake.travel_frequency || "Unknown"}
Sleep: ${intake.sleep_hours || "Unknown"} hrs, Quality: ${intake.sleep_quality || "Unknown"}
Stress Level: ${intake.stress_level || "Unknown"}
Recovery Practices: ${intake.recovery_practices || "None"}

SUPPLEMENTS:
Current Supplements: ${intake.current_supplements || "None"}
Budget: ${intake.supplement_budget || "Unknown"}
Peptide Interest: ${intake.peptide_interest || "Not interested"}
Compounds Interest: ${intake.compounds_interest || "None"}

CARDIO: ${intake.cardio || "None"}
Commitment Level: ${intake.commitment_level || "Unknown"}
`;

  const systemPrompt = `You are Coach Bryan's programming engine for Forged by Freedom. You create professional, detailed training and nutrition programs based on client intake data.

${FBF_PROGRAMMING_RULES}

IMPORTANT: You MUST output valid JSON only. No markdown, no explanation — just the JSON object.

Generate a complete 4-week program in this exact JSON structure:
{
  "training_program": {
    "split_type": "Upper/Lower" or "Push/Pull/Legs" or "Full Body" etc,
    "days_per_week": 4,
    "phase": "Hypertrophy Base" or "Strength" or "Fat Loss" etc,
    "duration_weeks": 4,
    "deload_week": 5,
    "progression_scheme": "Add 5lbs when hitting top of rep range for all sets",
    "days": {
      "Day 1 - Upper Push": [
        { "exercise": "Dumbbell Bench Press", "sets": 4, "reps": "8-10", "rir": 2, "rest": "90s", "notes": "Control the eccentric 2-3 sec" },
        ...more exercises (5-7 per day)
      ],
      "Day 2 - Lower": [...],
      ...
    }
  },
  "nutrition_plan": {
    "goal": "Fat Loss" or "Lean Bulk" or "Recomp",
    "calories": 2400,
    "protein_g": 200,
    "carbs_g": 250,
    "fats_g": 75,
    "protein_per_lb": "1.0",
    "meal_count": 4,
    "meal_timing_notes": "Pre-workout meal 60-90 min before training. Post-workout within 60 min.",
    "sample_day": {
      "meal_1": { "time": "7:00 AM", "description": "4 eggs, 2 slices whole grain toast, 1 banana", "macros": "P:28 C:55 F:22" },
      "meal_2": { "time": "12:00 PM", "description": "8oz grilled chicken, 1.5 cups rice, mixed greens, 1 tbsp olive oil", "macros": "P:50 C:70 F:15" },
      ...
    },
    "food_notes": "Adjust portions to hit macro targets. These are examples — swap proteins/carbs as desired within your preferred foods."
  },
  "supplement_protocol": {
    "daily": [
      { "supplement": "Creatine Monohydrate", "dose": "5g", "timing": "Any time, with water", "priority": "Essential" },
      ...
    ],
    "optional": [
      { "supplement": "Ashwagandha KSM-66", "dose": "600mg", "timing": "Morning", "purpose": "Stress/cortisol management", "priority": "Nice to have" }
    ],
    "estimated_monthly_cost": "$60-80",
    "notes": "Start with essentials only. Add optionals based on budget and response."
  },
  "cardio_protocol": {
    "weekly_sessions": 3,
    "type": "LISS (walking, incline treadmill)",
    "duration": "25-35 min",
    "timing": "Post-weights or separate session",
    "heart_rate_zone": "Zone 2 (120-140 bpm)",
    "step_goal": 8000,
    "notes": "Increase steps before adding formal cardio sessions"
  }
}

Use the client's preferred foods in the sample meal plan. Respect food restrictions and dislikes. Default to dumbbell movements. Match volume and intensity to their experience level and recovery capacity. Respect their schedule and session time limit.`;

  const result = await callOpenRouter("/chat/completions", {
    model: CONFIG.chatModel,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: clientProfile }
    ],
    temperature: 0.4,
    max_tokens: 6000
  }, 120000);

  const content = result.choices?.[0]?.message?.content || "";

  // Parse JSON from response (strip markdown code fences if present)
  const jsonStr = content.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
  return JSON.parse(jsonStr);
}

// ─── Format Program as HTML ──────────────────────────────
function formatProgramHTML(program, clientName) {
  const { training_program: tp, nutrition_plan: np, supplement_protocol: sp, cardio_protocol: cp } = program;

  let trainingHTML = "";
  if (tp.days) {
    for (const [dayName, exercises] of Object.entries(tp.days)) {
      trainingHTML += `<h3 style="color:#ff6a00;margin-top:24px;font-size:16px;">${dayName}</h3>
      <table style="width:100%;border-collapse:collapse;margin-top:8px;">
        <tr style="background:#1c1c1c;color:#aaa;font-size:12px;text-transform:uppercase;">
          <th style="padding:8px 12px;text-align:left;border-bottom:1px solid #2a2a2a;">Exercise</th>
          <th style="padding:8px 12px;text-align:center;border-bottom:1px solid #2a2a2a;">Sets</th>
          <th style="padding:8px 12px;text-align:center;border-bottom:1px solid #2a2a2a;">Reps</th>
          <th style="padding:8px 12px;text-align:center;border-bottom:1px solid #2a2a2a;">RIR</th>
          <th style="padding:8px 12px;text-align:center;border-bottom:1px solid #2a2a2a;">Rest</th>
          <th style="padding:8px 12px;text-align:left;border-bottom:1px solid #2a2a2a;">Notes</th>
        </tr>`;
      for (const ex of exercises) {
        trainingHTML += `
        <tr style="border-bottom:1px solid #1c1c1c;">
          <td style="padding:8px 12px;color:#e8e8e8;font-weight:500;">${ex.exercise}</td>
          <td style="padding:8px 12px;text-align:center;color:#aaa;">${ex.sets}</td>
          <td style="padding:8px 12px;text-align:center;color:#aaa;">${ex.reps}</td>
          <td style="padding:8px 12px;text-align:center;color:#aaa;">${ex.rir}</td>
          <td style="padding:8px 12px;text-align:center;color:#aaa;">${ex.rest}</td>
          <td style="padding:8px 12px;color:#666;font-size:13px;">${ex.notes || ""}</td>
        </tr>`;
      }
      trainingHTML += "</table>";
    }
  }

  let mealsHTML = "";
  if (np.sample_day) {
    for (const [mealKey, meal] of Object.entries(np.sample_day)) {
      mealsHTML += `
      <div style="background:#1c1c1c;border:1px solid #2a2a2a;border-radius:8px;padding:14px 16px;margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <strong style="color:#e8e8e8;">${mealKey.replace("_", " ").toUpperCase()}</strong>
          <span style="color:#ff6a00;font-size:12px;font-weight:600;">${meal.time}</span>
        </div>
        <p style="color:#aaa;margin:6px 0 4px;font-size:14px;">${meal.description}</p>
        <span style="color:#666;font-size:12px;">${meal.macros}</span>
      </div>`;
    }
  }

  let supplementsHTML = "";
  const allSupps = [...(sp.daily || []), ...(sp.optional || [])];
  for (const s of allSupps) {
    supplementsHTML += `
    <tr style="border-bottom:1px solid #1c1c1c;">
      <td style="padding:8px 12px;color:#e8e8e8;font-weight:500;">${s.supplement}</td>
      <td style="padding:8px 12px;color:#aaa;text-align:center;">${s.dose}</td>
      <td style="padding:8px 12px;color:#aaa;">${s.timing}</td>
      <td style="padding:8px 12px;color:${s.priority === "Essential" ? "#22c55e" : "#666"};font-size:12px;font-weight:600;">${s.priority}</td>
    </tr>`;
  }

  return `<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:700px;margin:0 auto;padding:32px 20px;">

  <!-- Header -->
  <div style="text-align:center;margin-bottom:40px;">
    <h1 style="font-size:28px;font-weight:800;letter-spacing:2px;text-transform:uppercase;background:linear-gradient(135deg,#ff6a00,#ffb347);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0;">FORGED BY FREEDOM</h1>
    <p style="color:#666;font-size:13px;text-transform:uppercase;letter-spacing:1px;margin-top:6px;">Custom Training & Nutrition Program</p>
    <div style="width:60px;height:3px;margin:16px auto 0;background:linear-gradient(90deg,transparent,#ff6a00,transparent);border-radius:2px;"></div>
  </div>

  <!-- Client Info -->
  <div style="background:#141414;border:1.5px solid #2a2a2a;border-radius:12px;padding:20px;margin-bottom:24px;">
    <h2 style="color:#ff6a00;font-size:14px;text-transform:uppercase;letter-spacing:1px;margin:0 0 12px;">Program For</h2>
    <p style="color:#e8e8e8;font-size:20px;font-weight:700;margin:0;">${clientName}</p>
    <p style="color:#aaa;font-size:13px;margin:8px 0 0;">Generated: ${new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}</p>
  </div>

  <!-- Training Overview -->
  <div style="background:#141414;border:1.5px solid #2a2a2a;border-radius:12px;padding:20px;margin-bottom:24px;">
    <h2 style="color:#ff6a00;font-size:14px;text-transform:uppercase;letter-spacing:1px;margin:0 0 16px;">Training Program</h2>
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;">
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:120px;">
        <div style="color:#666;font-size:11px;text-transform:uppercase;">Split</div>
        <div style="color:#e8e8e8;font-size:15px;font-weight:600;margin-top:4px;">${tp.split_type}</div>
      </div>
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:120px;">
        <div style="color:#666;font-size:11px;text-transform:uppercase;">Days/Week</div>
        <div style="color:#e8e8e8;font-size:15px;font-weight:600;margin-top:4px;">${tp.days_per_week}</div>
      </div>
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:120px;">
        <div style="color:#666;font-size:11px;text-transform:uppercase;">Phase</div>
        <div style="color:#e8e8e8;font-size:15px;font-weight:600;margin-top:4px;">${tp.phase}</div>
      </div>
    </div>
    <p style="color:#aaa;font-size:13px;margin:0;"><strong style="color:#e8e8e8;">Progression:</strong> ${tp.progression_scheme}</p>
    <p style="color:#aaa;font-size:13px;margin:8px 0 0;"><strong style="color:#e8e8e8;">Deload:</strong> Week ${tp.deload_week}</p>
    ${trainingHTML}
  </div>

  <!-- Nutrition Plan -->
  <div style="background:#141414;border:1.5px solid #2a2a2a;border-radius:12px;padding:20px;margin-bottom:24px;">
    <h2 style="color:#ff6a00;font-size:14px;text-transform:uppercase;letter-spacing:1px;margin:0 0 16px;">Nutrition Plan</h2>
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:80px;text-align:center;">
        <div style="color:#ff6a00;font-size:22px;font-weight:700;">${np.calories}</div>
        <div style="color:#666;font-size:11px;text-transform:uppercase;margin-top:2px;">Calories</div>
      </div>
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:80px;text-align:center;">
        <div style="color:#22c55e;font-size:22px;font-weight:700;">${np.protein_g}g</div>
        <div style="color:#666;font-size:11px;text-transform:uppercase;margin-top:2px;">Protein</div>
      </div>
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:80px;text-align:center;">
        <div style="color:#3b82f6;font-size:22px;font-weight:700;">${np.carbs_g}g</div>
        <div style="color:#666;font-size:11px;text-transform:uppercase;margin-top:2px;">Carbs</div>
      </div>
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:80px;text-align:center;">
        <div style="color:#eab308;font-size:22px;font-weight:700;">${np.fats_g}g</div>
        <div style="color:#666;font-size:11px;text-transform:uppercase;margin-top:2px;">Fats</div>
      </div>
    </div>
    <p style="color:#aaa;font-size:13px;margin:0 0 12px;"><strong style="color:#e8e8e8;">Goal:</strong> ${np.goal} · <strong style="color:#e8e8e8;">Meals:</strong> ${np.meal_count}/day</p>
    <p style="color:#aaa;font-size:13px;margin:0 0 16px;">${np.meal_timing_notes || ""}</p>

    <h3 style="color:#e8e8e8;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 10px;">Sample Day</h3>
    ${mealsHTML}
    <p style="color:#666;font-size:12px;font-style:italic;margin:12px 0 0;">${np.food_notes || ""}</p>
  </div>

  <!-- Supplements -->
  <div style="background:#141414;border:1.5px solid #2a2a2a;border-radius:12px;padding:20px;margin-bottom:24px;">
    <h2 style="color:#ff6a00;font-size:14px;text-transform:uppercase;letter-spacing:1px;margin:0 0 16px;">Supplement Protocol</h2>
    <table style="width:100%;border-collapse:collapse;">
      <tr style="background:#1c1c1c;color:#aaa;font-size:12px;text-transform:uppercase;">
        <th style="padding:8px 12px;text-align:left;border-bottom:1px solid #2a2a2a;">Supplement</th>
        <th style="padding:8px 12px;text-align:center;border-bottom:1px solid #2a2a2a;">Dose</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:1px solid #2a2a2a;">Timing</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:1px solid #2a2a2a;">Priority</th>
      </tr>
      ${supplementsHTML}
    </table>
    <p style="color:#666;font-size:12px;margin:12px 0 0;">Est. monthly cost: ${sp.estimated_monthly_cost || "Varies"}</p>
    <p style="color:#666;font-size:12px;font-style:italic;margin:6px 0 0;">${sp.notes || ""}</p>
  </div>

  <!-- Cardio -->
  <div style="background:#141414;border:1.5px solid #2a2a2a;border-radius:12px;padding:20px;margin-bottom:24px;">
    <h2 style="color:#ff6a00;font-size:14px;text-transform:uppercase;letter-spacing:1px;margin:0 0 16px;">Cardio Protocol</h2>
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px;">
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:120px;">
        <div style="color:#666;font-size:11px;text-transform:uppercase;">Sessions/Week</div>
        <div style="color:#e8e8e8;font-size:15px;font-weight:600;margin-top:4px;">${cp.weekly_sessions}</div>
      </div>
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:120px;">
        <div style="color:#666;font-size:11px;text-transform:uppercase;">Type</div>
        <div style="color:#e8e8e8;font-size:15px;font-weight:600;margin-top:4px;">${cp.type}</div>
      </div>
      <div style="background:#1c1c1c;border-radius:8px;padding:12px 16px;flex:1;min-width:120px;">
        <div style="color:#666;font-size:11px;text-transform:uppercase;">Duration</div>
        <div style="color:#e8e8e8;font-size:15px;font-weight:600;margin-top:4px;">${cp.duration}</div>
      </div>
    </div>
    <p style="color:#aaa;font-size:13px;margin:0;"><strong style="color:#e8e8e8;">HR Zone:</strong> ${cp.heart_rate_zone || "Zone 2"}</p>
    <p style="color:#aaa;font-size:13px;margin:6px 0 0;"><strong style="color:#e8e8e8;">Daily Step Goal:</strong> ${cp.step_goal || "8,000"}</p>
    <p style="color:#666;font-size:12px;font-style:italic;margin:8px 0 0;">${cp.notes || ""}</p>
  </div>

  <!-- Footer -->
  <div style="text-align:center;padding:24px 0;border-top:1px solid #2a2a2a;">
    <p style="color:#666;font-size:12px;margin:0;">This program is for educational purposes only. Consult your physician before starting.</p>
    <p style="color:#ff6a00;font-size:13px;font-weight:600;margin:8px 0 0;">FORGED BY FREEDOM STRENGTH & NUTRITION</p>
  </div>
</div>
</body>
</html>`;
}

// ─── Send Approval Email to Coach ────────────────────────
async function sendApprovalEmail(programId, clientName, clientEmail, programHtml) {
  if (!emailTransporter) {
    console.log(`[PROGRAM] Email not configured. Program ${programId} ready for review.`);
    // Fallback: send via ntfy
    try {
      await fetch(`https://ntfy.sh/${process.env.NTFY_TOPIC || "fbf-leads-bryan"}`, {
        method: "POST",
        headers: { "Title": `Program Ready: ${clientName}`, "Priority": "high", "Tags": "clipboard" },
        body: `New program generated for ${clientName} (${clientEmail}).\n\nReview & approve: ${APP_URL}/admin\n\nProgram ID: ${programId}`
      });
    } catch (e) { console.error("[PROGRAM] ntfy error:", e.message); }
    return;
  }

  await emailTransporter.sendMail({
    from: `"Forged by Freedom" <${process.env.SMTP_USER}>`,
    to: COACH_EMAIL,
    subject: `Program Ready for Review: ${clientName}`,
    html: `
      <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <h2 style="color:#ff6a00;">New Program Ready for Approval</h2>
        <p><strong>Client:</strong> ${clientName}</p>
        <p><strong>Email:</strong> ${clientEmail}</p>
        <p>A program has been auto-generated from their intake form.</p>
        <p><a href="${APP_URL}/api/programs/${programId}/preview" style="display:inline-block;background:#ff6a00;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;margin:16px 0;">View Program</a></p>
        <p><a href="${APP_URL}/api/programs/${programId}/approve?key=${process.env.ADMIN_KEY}" style="display:inline-block;background:#22c55e;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;">Approve & Send Payment Link</a></p>
        <p><a href="${APP_URL}/api/programs/${programId}/reject?key=${process.env.ADMIN_KEY}" style="color:#ef4444;font-weight:bold;">Reject / Request Changes</a></p>
      </div>
    `
  });
  console.log(`[PROGRAM] Approval email sent for ${clientName}`);
}

// ─── Enhanced Intake Handler (replace original) ──────────
// Override the original POST /api/intake to add program generation
const originalIntakeHandler = app._router.stack.find(
  layer => layer.route?.path === "/api/intake" && layer.route?.methods?.post
);

// We'll add the program generation as a new route triggered after intake
app.post("/api/intake/generate-program", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });

  const { intake_id, key } = req.body;
  if (key !== process.env.ADMIN_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  try {
    const { data: intake, error: intakeErr } = await supabase
      .from("client_intakes").select("*").eq("id", intake_id).single();
    if (intakeErr || !intake) return res.status(404).json({ error: "Intake not found" });

    const { data: lead } = await supabase
      .from("leads").select("*").eq("id", intake.lead_id).single();

    console.log(`[PROGRAM] Generating program for ${intake.full_name}...`);
    const program = await generateProgram(intake, lead || {});
    const programHtml = formatProgramHTML(program, intake.full_name);

    const { data: saved, error: saveErr } = await supabase.from("generated_programs").insert({
      intake_id: intake.id,
      lead_id: intake.lead_id,
      client_name: intake.full_name,
      client_email: lead?.email || "",
      training_program: program.training_program,
      nutrition_plan: program.nutrition_plan,
      supplement_protocol: program.supplement_protocol,
      cardio_protocol: program.cardio_protocol,
      program_html: programHtml,
      ai_model_used: CONFIG.chatModel,
      status: "pending_review"
    }).select().single();

    if (saveErr) {
      console.error("[PROGRAM] Save error:", saveErr);
      return res.status(500).json({ error: "Failed to save program" });
    }

    // Notify Bryan for approval
    await sendApprovalEmail(saved.id, intake.full_name, lead?.email || "", programHtml);

    res.json({ status: "ok", program_id: saved.id, message: "Program generated and sent for review" });
  } catch (err) {
    console.error("[PROGRAM] Generation error:", err);
    res.status(500).json({ error: "Program generation failed: " + err.message });
  }
});

// ─── Preview Program ─────────────────────────────────────
app.get("/api/programs/:id/preview", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });

  try {
    const { data, error } = await supabase
      .from("generated_programs").select("program_html, client_name, status")
      .eq("id", req.params.id).single();

    if (error || !data) return res.status(404).json({ error: "Program not found" });
    res.type("html").send(data.program_html);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Approve Program → Create Stripe Checkout ────────────
app.get("/api/programs/:id/approve", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Not configured" });
  if (req.query.key !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

  try {
    const { data: program, error } = await supabase
      .from("generated_programs").select("*").eq("id", req.params.id).single();
    if (error || !program) return res.status(404).json({ error: "Program not found" });

    // Update status to approved
    await supabase.from("generated_programs")
      .update({ status: "approved", approved_at: new Date().toISOString(), coach_notes: req.query.notes || null })
      .eq("id", req.params.id);

    // If Stripe is configured, create checkout session
    if (stripe && process.env.STRIPE_PRICE_ID) {
      const session = await stripe.checkout.sessions.create({
        payment_method_types: ["card"],
        mode: "payment",
        customer_email: program.client_email,
        line_items: [{ price: process.env.STRIPE_PRICE_ID, quantity: 1 }],
        success_url: `${APP_URL}/api/programs/${req.params.id}/payment-success?session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${APP_URL}/api/programs/${req.params.id}/payment-cancelled`,
        metadata: { program_id: req.params.id, client_name: program.client_name },
      });

      await supabase.from("generated_programs")
        .update({ stripe_checkout_session_id: session.id, payment_status: "pending" })
        .eq("id", req.params.id);

      // Send payment link to client
      if (emailTransporter) {
        await emailTransporter.sendMail({
          from: `"Forged by Freedom" <${process.env.SMTP_USER}>`,
          to: program.client_email,
          subject: "Your FBF Program is Ready — Complete Payment",
          html: `
            <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#0a0a0a;color:#e8e8e8;">
              <h1 style="color:#ff6a00;text-align:center;">Your Program is Ready</h1>
              <p>Hey ${program.client_name.split(" ")[0]},</p>
              <p>Coach Bryan has reviewed and approved your custom training & nutrition program.</p>
              <p>Complete payment to get instant access:</p>
              <p style="text-align:center;margin:24px 0;">
                <a href="${session.url}" style="display:inline-block;background:#ff6a00;color:#fff;padding:16px 32px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;">Complete Payment</a>
              </p>
              <p style="color:#666;font-size:13px;">If you have questions, reply to this email or message Coach Bryan directly.</p>
              <p style="color:#ff6a00;font-weight:bold;margin-top:24px;">— Forged by Freedom</p>
            </div>
          `
        });
      } else {
        // Fallback: notify via ntfy with payment link
        await fetch(`https://ntfy.sh/${process.env.NTFY_TOPIC || "fbf-leads-bryan"}`, {
          method: "POST",
          headers: { "Title": `Program Approved: ${program.client_name}`, "Tags": "white_check_mark" },
          body: `Send this payment link to ${program.client_name} (${program.client_email}):\n\n${session.url}`
        }).catch(() => {});
      }

      res.type("html").send(`
        <div style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center;color:#e8e8e8;background:#0a0a0a;padding:40px;border-radius:12px;">
          <h2 style="color:#22c55e;">Program Approved</h2>
          <p>${program.client_name}'s program has been approved.</p>
          <p>Payment link sent to: <strong>${program.client_email}</strong></p>
          <p style="color:#666;font-size:13px;margin-top:16px;">Checkout URL: <a href="${session.url}" style="color:#ff6a00;">${session.url}</a></p>
        </div>
      `);
    } else {
      // No Stripe — just mark approved and deliver directly
      await supabase.from("generated_programs")
        .update({ payment_status: "paid", delivered_at: new Date().toISOString(), status: "delivered" })
        .eq("id", req.params.id);

      // Send program directly
      if (emailTransporter) {
        await emailTransporter.sendMail({
          from: `"Forged by Freedom" <${process.env.SMTP_USER}>`,
          to: program.client_email,
          subject: "Your FBF Program — Forged by Freedom",
          html: program.program_html
        });
      }

      res.type("html").send(`
        <div style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center;color:#e8e8e8;background:#0a0a0a;padding:40px;border-radius:12px;">
          <h2 style="color:#22c55e;">Program Approved & Delivered</h2>
          <p>${program.client_name}'s program has been sent.</p>
          <p style="color:#666;">No payment processor configured — program sent directly.</p>
        </div>
      `);
    }
  } catch (err) {
    console.error("[PROGRAM] Approve error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ─── Reject Program ──────────────────────────────────────
app.get("/api/programs/:id/reject", async (req, res) => {
  if (req.query.key !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

  await supabase.from("generated_programs")
    .update({ status: "rejected", coach_notes: req.query.reason || "Needs revision" })
    .eq("id", req.params.id);

  res.type("html").send(`
    <div style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center;color:#e8e8e8;background:#0a0a0a;padding:40px;border-radius:12px;">
      <h2 style="color:#ef4444;">Program Rejected</h2>
      <p>You can regenerate this program from the admin panel.</p>
    </div>
  `);
});

// ─── Payment Success ─────────────────────────────────────
app.get("/api/programs/:id/payment-success", async (req, res) => {
  if (!stripe) return res.status(503).json({ error: "Stripe not configured" });

  try {
    const sessionId = req.query.session_id;
    const session = await stripe.checkout.sessions.retrieve(sessionId);

    if (session.payment_status === "paid") {
      const { data: program } = await supabase.from("generated_programs")
        .select("*").eq("id", req.params.id).single();

      await supabase.from("generated_programs").update({
        payment_status: "paid",
        stripe_payment_intent_id: session.payment_intent,
        payment_amount: session.amount_total,
        status: "delivered",
        delivered_at: new Date().toISOString()
      }).eq("id", req.params.id);

      // Deliver program via email
      if (emailTransporter && program) {
        await emailTransporter.sendMail({
          from: `"Forged by Freedom" <${process.env.SMTP_USER}>`,
          to: program.client_email,
          subject: "Your FBF Program — Forged by Freedom",
          html: program.program_html
        });
      }

      // Notify coach
      await fetch(`https://ntfy.sh/${process.env.NTFY_TOPIC || "fbf-leads-bryan"}`, {
        method: "POST",
        headers: { "Title": `Payment Received: ${program?.client_name}`, "Tags": "money_with_wings" },
        body: `${program?.client_name} paid $${(session.amount_total / 100).toFixed(2)}. Program delivered.`
      }).catch(() => {});

      res.type("html").send(`
        <div style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center;color:#e8e8e8;background:#0a0a0a;padding:40px;border-radius:12px;">
          <h1 style="color:#ff6a00;">FORGED BY FREEDOM</h1>
          <h2 style="color:#22c55e;margin-top:24px;">Payment Complete</h2>
          <p>Your custom program has been sent to your email.</p>
          <p style="color:#666;font-size:13px;margin-top:16px;">Check your inbox (and spam folder) for your full program.</p>
          <p style="color:#ff6a00;font-weight:bold;margin-top:24px;">Let's get to work.</p>
        </div>
      `);
    } else {
      res.type("html").send(`
        <div style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center;padding:40px;">
          <h2 style="color:#eab308;">Payment Processing</h2>
          <p>Your payment is still processing. You'll receive your program via email once confirmed.</p>
        </div>
      `);
    }
  } catch (err) {
    console.error("[PAYMENT] Error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ─── Payment Cancelled ──────────────────────────────────
app.get("/api/programs/:id/payment-cancelled", (req, res) => {
  res.type("html").send(`
    <div style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center;color:#e8e8e8;background:#0a0a0a;padding:40px;border-radius:12px;">
      <h2 style="color:#eab308;">Payment Cancelled</h2>
      <p>No worries — your program is saved. When you're ready, contact Coach Bryan to get a new payment link.</p>
      <p style="color:#ff6a00;font-weight:bold;margin-top:16px;">— Forged by Freedom</p>
    </div>
  `);
});

// ─── List Programs (Admin) ───────────────────────────────
app.get("/api/programs", async (req, res) => {
  if (req.query.key !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

  const { data, error } = await supabase.from("generated_programs")
    .select("id, client_name, client_email, status, payment_status, created_at, approved_at, delivered_at")
    .order("created_at", { ascending: false });

  if (error) return res.status(500).json({ error: error.message });
  res.json({ programs: data });
});

// ─── Stripe Webhook ──────────────────────────────────────
app.post("/api/stripe/webhook", express.raw({ type: "application/json" }), async (req, res) => {
  if (!stripe) return res.status(503).json({ error: "Stripe not configured" });

  const sig = req.headers["stripe-signature"];
  let event;

  try {
    event = stripe.webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    console.error("[STRIPE] Webhook signature verification failed:", err.message);
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object;
    const programId = session.metadata?.program_id;
    if (programId) {
      await supabase.from("generated_programs").update({
        payment_status: "paid",
        stripe_payment_intent_id: session.payment_intent,
        payment_amount: session.amount_total,
        status: "delivered",
        delivered_at: new Date().toISOString()
      }).eq("id", programId);

      console.log(`[STRIPE] Payment confirmed for program ${programId}`);
    }
  }

  res.json({ received: true });
});

// ─── Auto-Generate on Intake (add to existing intake flow) ─
// Patch the existing intake endpoint to trigger program generation
const _originalIntakeRoute = app._router.stack.findIndex(
  layer => layer.route?.path === "/api/intake" && layer.route?.methods?.post
);

// Add auto-generation trigger after intake
app.post("/api/intake-with-program", async (req, res) => {
  if (!supabase) return res.status(503).json({ error: "Intake system not configured" });

  const { lead_id, ...fields } = req.body;

  if (!lead_id) return res.status(400).json({ error: "Lead token required" });
  if (!fields.disclaimer_acknowledged) return res.status(400).json({ error: "Disclaimer must be acknowledged" });

  try {
    // Verify lead
    const { data: lead, error: leadErr } = await supabase
      .from("leads").select("id, status, name, email").eq("id", lead_id).single();

    if (leadErr || !lead) return res.status(404).json({ error: "Invalid onboarding link" });
    if (lead.status !== "approved") return res.status(403).json({ error: "Application not yet approved." });

    // Save intake
    const { data: intake, error: intakeErr } = await supabase
      .from("client_intakes").insert({ lead_id, ...fields }).select().single();

    if (intakeErr) {
      console.error("[INTAKE] Supabase error:", intakeErr);
      return res.status(500).json({ error: "Failed to save intake" });
    }

    // Trigger n8n webhook
    const webhookUrl = process.env.N8N_INTAKE_WEBHOOK_URL;
    if (webhookUrl) {
      fetch(webhookUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "intake_complete", client_name: fields.full_name || lead.name, email: lead.email })
      }).catch(err => console.error("[INTAKE] Webhook error:", err.message));
    }

    // Auto-generate program in background
    console.log(`[INTAKE] Complete: ${fields.full_name || lead.name}. Starting program generation...`);

    // Compute risk score immediately
    const riskScore = computeRiskScore(intake, lead);
    console.log(`[RISK] ${intake.full_name || lead.name}: ${riskScore.tier} (score: ${riskScore.score}, ${riskScore.flag_count} flags)`);

    // Generate program + summary in parallel
    Promise.all([
      generateProgram(intake, lead),
      generateClientSummary(intake, lead).catch(err => { console.error("[SUMMARY] Failed:", err.message); return null; })
    ]).then(async ([program, summary]) => {
      const programHtml = formatProgramHTML(program, intake.full_name || lead.name);

      const { data: saved } = await supabase.from("generated_programs").insert({
        intake_id: intake.id,
        lead_id: intake.lead_id,
        client_name: intake.full_name || lead.name,
        client_email: lead.email,
        training_program: program.training_program,
        nutrition_plan: program.nutrition_plan,
        supplement_protocol: program.supplement_protocol,
        cardio_protocol: program.cardio_protocol,
        program_html: programHtml,
        ai_model_used: CONFIG.chatModel,
        status: "pending_review"
      }).select().single();

      if (saved) {
        // Include risk score and summary in approval email
        const riskEmoji = riskScore.tier === "red" ? "🔴" : riskScore.tier === "yellow" ? "🟡" : "🟢";
        const extraInfo = `\n\nRisk: ${riskEmoji} ${riskScore.tier.toUpperCase()} (${riskScore.score}/100, ${riskScore.flag_count} flags)` +
          (riskScore.flags.filter(f => f.level === "red").length > 0
            ? `\nRed flags: ${riskScore.flags.filter(f => f.level === "red").map(f => f.text).join(", ")}`
            : "") +
          (summary ? `\n\nSummary:\n${summary.slice(0, 500)}` : "");

        await sendApprovalEmail(saved.id, intake.full_name || lead.name, lead.email, programHtml);

        // Also send risk + summary via ntfy
        fetch(`https://ntfy.sh/${process.env.NTFY_TOPIC || "fbf-leads-bryan"}`, {
          method: "POST",
          headers: { "Title": `${riskEmoji} New Client: ${intake.full_name || lead.name}`, "Priority": riskScore.tier === "red" ? "high" : "default", "Tags": "clipboard" },
          body: `Risk: ${riskScore.tier.toUpperCase()} (${riskScore.score}/100)${extraInfo}\n\nProgram ready for review: ${APP_URL}/api/programs/${saved.id}/preview`
        }).catch(() => {});

        console.log(`[PROGRAM] Generated and pending review: ${intake.full_name || lead.name}`);
      }
    }).catch(err => {
      console.error(`[PROGRAM] Auto-generation failed for ${intake.full_name}:`, err.message);
      // Notify Bryan that generation failed
      fetch(`https://ntfy.sh/${process.env.NTFY_TOPIC || "fbf-leads-bryan"}`, {
        method: "POST",
        headers: { "Title": `Program Generation Failed: ${intake.full_name}`, "Priority": "high", "Tags": "warning" },
        body: `Auto-program generation failed for ${intake.full_name}. Error: ${err.message}\n\nGenerate manually: ${APP_URL}/admin`
      }).catch(() => {});
    });

    res.json({
      status: "ok",
      message: "Intake complete. Your custom program is being generated. Bryan will review it and you'll receive it via email."
    });

  } catch (err) {
    console.error("[INTAKE] Error:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// ─── Coach Dashboard ─────────────────────────────────────────
app.get("/coach-dashboard", (_, res) => res.sendFile(join(__dirname, "embed", "coach-dashboard.html")));

// Coach dashboard API: get all clients with latest metrics for a coach
app.get("/api/coach/clients", async (req, res) => {
  try {
    const adminKey = req.query.key;
    if (adminKey !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

    const { data: clients, error } = await sb.from("clients")
      .select("id, first_name, last_name, email, is_active, target_calories, target_protein, target_steps, last_weight, created_at")
      .eq("is_active", true)
      .order("last_name");

    if (error) throw error;

    // Get latest metrics for each client
    const clientIds = clients.map(c => c.id);
    const { data: metrics } = await sb.from("client_metrics")
      .select("*")
      .in("client_id", clientIds);

    // Get latest checkin for each client
    const { data: checkins } = await sb.rpc("get_latest_checkins_per_client", { client_ids: clientIds }).catch(() => ({ data: null }));

    // Fallback: get recent checkins manually if RPC doesn't exist
    let latestCheckins = checkins;
    if (!latestCheckins) {
      const { data: allCheckins } = await sb.from("checkins")
        .select("*")
        .in("client_id", clientIds)
        .order("date", { ascending: false })
        .limit(clientIds.length * 2);
      // Group by client, keep latest
      const byClient = {};
      (allCheckins || []).forEach(c => {
        if (!byClient[c.client_id]) byClient[c.client_id] = c;
      });
      latestCheckins = Object.values(byClient);
    }

    const metricsMap = {};
    (metrics || []).forEach(m => metricsMap[m.client_id] = m);
    const checkinMap = {};
    (latestCheckins || []).forEach(c => checkinMap[c.client_id] = c);

    const enriched = clients.map(c => ({
      ...c,
      metrics: metricsMap[c.id] || null,
      latest_checkin: checkinMap[c.id] || null,
    }));

    res.json({ clients: enriched });
  } catch (err) {
    console.error("[COACH CLIENTS]", err);
    res.status(500).json({ error: "Server error" });
  }
});

// Coach dashboard API: get full client detail with all checkins
app.get("/api/coach/clients/:id", async (req, res) => {
  try {
    const adminKey = req.query.key;
    if (adminKey !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

    const clientId = req.params.id;

    const [clientRes, checkinsRes, scansRes, metricsRes] = await Promise.all([
      sb.from("clients").select("*").eq("id", clientId).single(),
      sb.from("checkins").select("*").eq("client_id", clientId).order("date", { ascending: false }).limit(90),
      sb.from("body_scans").select("*").eq("client_id", clientId).order("scan_date", { ascending: false }),
      sb.from("client_metrics").select("*").eq("client_id", clientId).single(),
    ]);

    if (clientRes.error) throw clientRes.error;

    res.json({
      client: clientRes.data,
      checkins: checkinsRes.data || [],
      scans: scansRes.data || [],
      metrics: metricsRes.data || null,
    });
  } catch (err) {
    console.error("[COACH CLIENT DETAIL]", err);
    res.status(500).json({ error: "Server error" });
  }
});

// Coach dashboard API: get checkin trends (aggregated)
app.get("/api/coach/clients/:id/trends", async (req, res) => {
  try {
    const adminKey = req.query.key;
    if (adminKey !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

    const clientId = req.params.id;
    const days = parseInt(req.query.days) || 30;

    const since = new Date();
    since.setDate(since.getDate() - days);

    const { data: checkins, error } = await sb.from("checkins")
      .select("date, weight_lbs, body_temp, blood_glucose, resting_heart_rate, blood_pressure_systolic, blood_pressure_diastolic, mood_rating, stress_level, calories, protein_g, carbs_g, fat_g, water_oz, steps, sleep_hours, sleep_quality, training_done, performance_rating, supplement_compliance, workout_duration_min, avg_heart_rate, cardio_minutes")
      .eq("client_id", clientId)
      .gte("date", since.toISOString().split("T")[0])
      .order("date", { ascending: true });

    if (error) throw error;

    res.json({ checkins: checkins || [], days });
  } catch (err) {
    console.error("[COACH TRENDS]", err);
    res.status(500).json({ error: "Server error" });
  }
});

// ─── Client Report Generation ────────────────────────────────
app.get("/api/coach/clients/:id/report", async (req, res) => {
  try {
    const adminKey = req.query.key;
    if (adminKey !== process.env.ADMIN_KEY) return res.status(401).json({ error: "Unauthorized" });

    const clientId = req.params.id;
    const days = parseInt(req.query.days) || 30;

    const since = new Date();
    since.setDate(since.getDate() - days);

    const [clientRes, checkinsRes, scansRes, metricsRes] = await Promise.all([
      sb.from("clients").select("*").eq("id", clientId).single(),
      sb.from("checkins").select("*").eq("client_id", clientId).gte("date", since.toISOString().split("T")[0]).order("date", { ascending: true }),
      sb.from("body_scans").select("*").eq("client_id", clientId).order("scan_date", { ascending: false }),
      sb.from("client_metrics").select("*").eq("client_id", clientId).single(),
    ]);

    if (clientRes.error) throw clientRes.error;

    const client = clientRes.data;
    const checkins = checkinsRes.data || [];
    const scans = scansRes.data || [];
    const metrics = metricsRes.data || {};

    // Calculate averages
    const avg = (arr) => arr.length ? (arr.reduce((a,b) => a+b, 0) / arr.length).toFixed(1) : "--";
    const weights = checkins.map(c => c.weight_lbs).filter(Boolean);
    const cals = checkins.map(c => c.calories).filter(Boolean);
    const proteins = checkins.map(c => c.protein_g).filter(Boolean);
    const sleeps = checkins.map(c => c.sleep_hours).filter(Boolean);
    const steps = checkins.map(c => c.steps).filter(Boolean);
    const moods = checkins.map(c => c.mood_rating).filter(Boolean);
    const temps = checkins.map(c => c.body_temp).filter(Boolean);
    const trainDays = checkins.filter(c => c.training_done).length;
    const totalDays = checkins.length;
    const adherence = totalDays > 0 ? ((totalDays / days) * 100).toFixed(0) : 0;
    const suppComp = checkins.filter(c => c.supplement_compliance).length;

    const latestScan = scans[0] || {};
    const firstScan = scans.length > 1 ? scans[scans.length - 1] : {};

    const reportDate = new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Client Report — ${client.first_name} ${client.last_name}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;color:#fff;padding:24px;max-width:900px;margin:0 auto}
.header{text-align:center;padding:32px 0;border-bottom:2px solid #FF6A00}
.header h1{font-size:28px;color:#FF6A00;margin-bottom:4px}
.header .name{font-size:22px;font-weight:700;margin-top:8px}
.header .period{color:#888;font-size:14px;margin-top:4px}
.section{margin-top:32px}
.section h2{font-size:18px;color:#FF6A00;border-bottom:1px solid #333;padding-bottom:8px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
.stat-card{background:#141414;border:1px solid #2a2a2a;border-radius:12px;padding:16px;text-align:center}
.stat-card .value{font-size:24px;font-weight:700;color:#fff}
.stat-card .label{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-top:4px}
.stat-card .delta{font-size:12px;font-weight:600;margin-top:4px}
.delta-good{color:#22c55e}.delta-bad{color:#ef4444}.delta-neutral{color:#888}
table{width:100%;border-collapse:collapse;margin-top:12px}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #2a2a2a;font-size:13px}
th{color:#888;text-transform:uppercase;letter-spacing:0.5px;font-size:11px}
td{color:#fff}
.badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}
.badge-green{background:rgba(34,197,94,0.15);color:#22c55e}
.badge-yellow{background:rgba(234,179,8,0.15);color:#eab308}
.badge-red{background:rgba(239,68,68,0.15);color:#ef4444}
.footer{text-align:center;margin-top:48px;padding-top:24px;border-top:1px solid #333;color:#555;font-size:12px}
@media print{body{background:#fff;color:#000} .stat-card{background:#f5f5f5;border-color:#ddd} .stat-card .value{color:#000} th{color:#666} td{color:#000} .header{border-color:#FF6A00}}
</style>
</head>
<body>
<div class="header">
  <h1>FORGED BY FREEDOM</h1>
  <div class="name">${client.first_name} ${client.last_name}</div>
  <div class="period">${days}-Day Report — Generated ${reportDate}</div>
</div>

<div class="section">
  <h2>Overview</h2>
  <div class="grid">
    <div class="stat-card">
      <div class="value">${adherence}%</div>
      <div class="label">Check-in Rate</div>
      <div class="delta delta-neutral">${totalDays} / ${days} days</div>
    </div>
    <div class="stat-card">
      <div class="value">${trainDays}</div>
      <div class="label">Training Days</div>
    </div>
    <div class="stat-card">
      <div class="value">${suppComp}/${totalDays}</div>
      <div class="label">Supp. Compliance</div>
    </div>
    <div class="stat-card">
      <div class="value"><span class="badge badge-${metrics.status || 'neutral'}">${(metrics.status || 'N/A').toUpperCase()}</span></div>
      <div class="label">Current Status</div>
    </div>
  </div>
</div>

<div class="section">
  <h2>Key Metrics (${days}-Day Averages)</h2>
  <div class="grid">
    <div class="stat-card">
      <div class="value">${avg(weights)}</div>
      <div class="label">Avg Weight (lbs)</div>
      ${weights.length >= 2 ? `<div class="delta ${weights[weights.length-1] < weights[0] ? 'delta-good' : 'delta-bad'}">${(weights[weights.length-1] - weights[0]).toFixed(1)} lbs</div>` : ''}
    </div>
    <div class="stat-card">
      <div class="value">${avg(cals)}</div>
      <div class="label">Avg Calories</div>
      ${client.target_calories ? `<div class="delta delta-neutral">Target: ${client.target_calories}</div>` : ''}
    </div>
    <div class="stat-card">
      <div class="value">${avg(proteins)}g</div>
      <div class="label">Avg Protein</div>
      ${client.target_protein ? `<div class="delta delta-neutral">Target: ${client.target_protein}g</div>` : ''}
    </div>
    <div class="stat-card">
      <div class="value">${avg(sleeps)}h</div>
      <div class="label">Avg Sleep</div>
    </div>
    <div class="stat-card">
      <div class="value">${avg(steps)}</div>
      <div class="label">Avg Steps</div>
      ${client.target_steps ? `<div class="delta delta-neutral">Target: ${client.target_steps}</div>` : ''}
    </div>
    <div class="stat-card">
      <div class="value">${avg(moods)}/10</div>
      <div class="label">Avg Mood</div>
    </div>
    <div class="stat-card">
      <div class="value">${avg(temps)}°F</div>
      <div class="label">Avg Body Temp</div>
    </div>
  </div>
</div>

${scans.length > 0 ? `
<div class="section">
  <h2>Body Composition</h2>
  <div class="grid">
    ${latestScan.body_fat_pct != null ? `<div class="stat-card">
      <div class="value">${latestScan.body_fat_pct}%</div>
      <div class="label">Body Fat</div>
      ${firstScan.body_fat_pct != null ? `<div class="delta ${latestScan.body_fat_pct < firstScan.body_fat_pct ? 'delta-good' : 'delta-bad'}">${(latestScan.body_fat_pct - firstScan.body_fat_pct).toFixed(1)}%</div>` : ''}
    </div>` : ''}
    ${latestScan.lean_mass_lbs != null ? `<div class="stat-card">
      <div class="value">${latestScan.lean_mass_lbs}</div>
      <div class="label">Lean Mass (lbs)</div>
      ${firstScan.lean_mass_lbs != null ? `<div class="delta ${latestScan.lean_mass_lbs > firstScan.lean_mass_lbs ? 'delta-good' : 'delta-bad'}">${(latestScan.lean_mass_lbs - firstScan.lean_mass_lbs).toFixed(1)} lbs</div>` : ''}
    </div>` : ''}
    ${latestScan.skeletal_muscle_mass_lbs != null ? `<div class="stat-card">
      <div class="value">${latestScan.skeletal_muscle_mass_lbs}</div>
      <div class="label">Skeletal Muscle (lbs)</div>
      ${firstScan.skeletal_muscle_mass_lbs != null ? `<div class="delta ${latestScan.skeletal_muscle_mass_lbs > firstScan.skeletal_muscle_mass_lbs ? 'delta-good' : 'delta-bad'}">${(latestScan.skeletal_muscle_mass_lbs - firstScan.skeletal_muscle_mass_lbs).toFixed(1)} lbs</div>` : ''}
    </div>` : ''}
    ${latestScan.total_weight_lbs != null ? `<div class="stat-card">
      <div class="value">${latestScan.total_weight_lbs}</div>
      <div class="label">Scan Weight (lbs)</div>
    </div>` : ''}
  </div>
</div>
` : ''}

<div class="section">
  <h2>Recent Check-ins</h2>
  <table>
    <tr><th>Date</th><th>Weight</th><th>Cal</th><th>Protein</th><th>Sleep</th><th>Steps</th><th>Mood</th><th>Train</th></tr>
    ${checkins.slice(-14).reverse().map(c => `
    <tr>
      <td>${new Date(c.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</td>
      <td>${c.weight_lbs || '--'}</td>
      <td>${c.calories || '--'}</td>
      <td>${c.protein_g ? c.protein_g + 'g' : '--'}</td>
      <td>${c.sleep_hours ? c.sleep_hours + 'h' : '--'}</td>
      <td>${c.steps ? c.steps.toLocaleString() : '--'}</td>
      <td>${c.mood_rating || '--'}</td>
      <td>${c.training_done ? '✓' : '—'}</td>
    </tr>`).join('')}
  </table>
</div>

<div class="footer">
  <p>Forged by Freedom — Coaching Report</p>
  <p>Generated on ${reportDate}</p>
</div>
</body></html>`;

    if (req.query.format === "json") {
      res.json({
        client: { first_name: client.first_name, last_name: client.last_name, email: client.email },
        period: { days, checkins: totalDays, training_days: trainDays },
        averages: {
          weight: avg(weights), calories: avg(cals), protein: avg(proteins),
          sleep: avg(sleeps), steps: avg(steps), mood: avg(moods), body_temp: avg(temps),
        },
        body_composition: latestScan.body_fat_pct != null ? {
          body_fat_pct: latestScan.body_fat_pct,
          lean_mass_lbs: latestScan.lean_mass_lbs,
          skeletal_muscle_mass_lbs: latestScan.skeletal_muscle_mass_lbs,
        } : null,
        adherence: `${adherence}%`,
        supplement_compliance: `${suppComp}/${totalDays}`,
        status: metrics.status,
      });
    } else {
      res.setHeader("Content-Type", "text/html");
      res.send(html);
    }
  } catch (err) {
    console.error("[REPORT]", err);
    res.status(500).json({ error: "Server error" });
  }
});

// 404 + Error handler
app.use((_, res) => res.status(404).json({ error: "Not found" }));
app.use((err, _, res, __) => {
  console.error("[ERROR]", err);
  res.status(500).json({ error: "Internal server error" });
});

// ─── Graceful Shutdown ───────────────────────────────────────
let server;
const shutdown = sig => {
  console.log(`\n[${sig}] Shutting down...`);
  server?.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10000);
};
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

// ─── Start ───────────────────────────────────────────────────
server = app.listen(PORT, () => {
  console.log(`[FBF] Coach Bryan API :${PORT} (${CONFIG.isProd ? "prod" : "dev"})`);
  console.log(`[FBF] Model: ${CONFIG.chatModel}`);
});
