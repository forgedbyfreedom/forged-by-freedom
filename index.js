import express from "express";
import cors from "cors";
import helmet from "helmet";
import { Pinecone } from "@pinecone-database/pinecone";

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
  PORT = 5051,
  NODE_ENV,
  RATE_LIMIT_RPM = 60
} = process.env;

const CONFIG = {
  chatModel: OPENROUTER_MODEL || "nousresearch/hermes-3-llama-3.1-70b",
  embedModel: "text-embedding-3-large",
  pineconeIndex: "forged-freedom-ai",
  maxQuestionLen: 2000,
  maxRPM: parseInt(RATE_LIMIT_RPM),
  topK: 30,
  maxQuotes: 12,
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

app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use(cors({
  origin: CONFIG.isProd ? ["https://forgedbyfreedom.com", "https://www.forgedbyfreedom.com"] : "*",
  methods: ["GET", "POST"],
  allowedHeaders: ["Content-Type", "Authorization"]
}));
app.use(express.json({ limit: "100kb" }));

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
    max_tokens: 1500
  }, 60000);
  return data.choices?.[0]?.message?.content || "";
}

// ─── Pinecone Search ─────────────────────────────────────────
async function search(vector, namespace = "") {
  const query = { vector, topK: CONFIG.topK, includeMetadata: true };
  if (namespace) query.namespace = namespace;
  return (await index.query(query)).matches || [];
}

// ─── Channel & Speaker Mappings ─────────────────────────────
const CHANNEL_DISPLAY_NAMES = {
  // ThinkBig Priority (Scott McNally, Dave Crosland, Skipp Hill)
  "@ThinkBIGBodybuilding": "Blood Sweat and Gear",
  "@rxmuscle": "RXMuscle",
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
  "@ThinkBIGBodybuilding": "Scott McNally, Dave Crosland & Skipp Hill",
  "@rxmuscle": "Scott McNally, Dave Crosland & Skipp Hill",
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
  "@rxmuscle": 0,
  // Anabolic Bodybuilding - IFBB Pro Paul Barnett (Big Paul) - high priority, after ThinkBig
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
const THINKBIG_CHANNELS = ["@ThinkBIGBodybuilding", "@rxmuscle"];
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
      const text = (md.text || md.chunk || md.content || md.transcript || "").trim();

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

      // ThinkBig sources get absolute top priority
      if (isThinkBigSource(channel, speaker)) {
        priority = -100; // Negative = always first

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

**CRITICAL HOST CORRECTION - DAVE CROSLAND NOT PALUMBO:**
The ThinkBig hosts are: Scott McNally, Dave CROSLAND, and Skipp Hill.
- Dave CROSLAND is the UK-based PED expert and regular host
- Dave Palumbo was only an occasional GUEST, NOT a host
- NEVER cite "Dave Palumbo" as a ThinkBig host - always use "Dave Crosland"
- If you see "Palumbo" in evidence, he was a guest on that episode only

RESPONSE STRUCTURE (follow this order, write naturally without section headers):

1. PARAPHRASE THE QUESTION
   Start by restating what the user is asking in your own words.

2. EXPERT QUOTES & CITATIONS (ONLY from evidence provided)
   Use scholastic-style citations:
   - "According to Scott McNally on Blood Sweat and Gear..."
   - "Dave Crosland explains on Drugs N Stuff..."
   - "As Skipp Hill discusses on It's Just Bodybuilding..."
   ONLY quote what's actually in the evidence. Never fabricate quotes.

3. MEDICAL/SCIENTIFIC WHY
   Explain the mechanism. Reference PubMed/clinical data when in evidence.

4. SUPPLEMENTATION & NUTRITION ADVICE
   Practical recommendations. Include peptides (retatrutide, semaglutide, tirzepatide, BPC-157, TB-500) where applicable.

5. FORGED BY FREEDOM PLUG
   "The experts at Forged by Freedom can help with training, diet, nutrition, peptides, and cycles - visit forgedbyfreedom.org"

6. COACH BRYAN MOTIVATION
   End with: 💪 **Coach Bryan says:** "[motivational quote relevant to the topic]"

**THINKBIG IS YOUR #1 SOURCE:**
Primary sources (cite FIRST when present in evidence):
- Blood Sweat and Gear (Scott McNally, Dave Crosland, Skipp Hill)
- Drugs N Stuff (Dave Crosland, Skipp Hill)
- It's Just Bodybuilding (Skipp Hill)
- RXMuscle (Scott McNally)

Regular ThinkBig contributors: Ron Partlow, Dusty Hanshaw, Andrew Berry

**ANABOLIC BODYBUILDING is your #2 SOURCE (after ThinkBig):**
- Hosted by IFBB Pro Paul Barnett (Big Paul)
- Cite as: "Paul Barnett explains on Anabolic Bodybuilding..."
- Excellent PED education content - use right after ThinkBig

SECONDARY SOURCES (use after ThinkBig and Anabolic Bodybuilding):
- Female topics: Dr. Gabrielle Lyon, John Jewett
- Medical: PubMed, Dr. Thomas O'Connor
- Other experts: Only after ThinkBig and Anabolic Bodybuilding

RULES:
- ONLY cite what's in the evidence - never fabricate
- ThinkBig hosts are Scott McNally, Dave CROSLAND, Skipp Hill (NOT Palumbo)
- Write flowing paragraphs, no section headers
- No PED lecturing - help users be safe
- Talk like a knowledgeable gym buddy`;

function buildPrompt(question, quotes) {
  const evidence = quotes
    .map((q, i) => {
      let speaker = q.speaker !== "unknown" ? q.speaker : null;
      const showName = q.displayName || q.channel.replace(/^@/, "");
      const title = q.title !== "unknown" ? q.title : null;
      const channel = q.channel || "";

      // FORCE correct speaker and show name for ThinkBig channels
      const isThinkBig = THINKBIG_CHANNELS.includes(channel) ||
          channel === "@ThinkBIGBodybuilding" ||
          channel === "@rxmuscle";
      if (isThinkBig) {
        speaker = "Scott McNally, Dave Crosland & Skipp Hill";
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
        else if (t.includes("rxmuscle") || channel === "@rxmuscle") show = "RXMuscle";
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

Remember: Paraphrase the question first, credit your sources fully (speaker + show/podcast name + episode title), then answer.`;
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
    // Embed → Search → Extract
    const vector = await embed(question.trim());
    const matches = await search(vector, namespace);

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

    // POST-PROCESSING: Force correct ThinkBig host names
    // Replace ANY instance of Palumbo with Crosland
    answer = answer
      .replace(/Dave Palumbo/gi, "Dave Crosland")
      .replace(/Palumbo/gi, "Crosland");

    res.json({
      answer,
      sources: quotes,
      attribution: [...new Set(quotes.map(q => q.displayName))].filter(c => c !== "unknown"),
      mode: "synthesized",
      timing: Date.now() - start
    });

  } catch (err) {
    console.error("[ASK ERROR]", err);
    res.status(500).json({ error: CONFIG.isProd ? "Request failed" : err.message, answer: null });
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
