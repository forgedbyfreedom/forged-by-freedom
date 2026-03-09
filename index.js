import express from "express";
import cors from "cors";
import helmet from "helmet";
import { Pinecone } from "@pinecone-database/pinecone";
import { createClient } from "@supabase/supabase-js";

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
    /\.wixsite\.com$/, /\.wix\.com$/, /\.filesusr\.com$/
  ] : "*",
  methods: ["GET", "POST", "PATCH"],
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

async function chat(messages, temperature = 0.7) {
  const data = await callOpenRouter("/chat/completions", {
    model: CONFIG.chatModel,
    messages,
    temperature,
    max_tokens: 2500
  }, 60000);
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
