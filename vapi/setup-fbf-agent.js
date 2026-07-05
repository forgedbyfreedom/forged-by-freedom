#!/usr/bin/env node
/**
 * FBF AI Phone Agent — Vapi Setup Script
 *
 * Run once to create the Ashley agent in your Vapi account.
 * After running, copy the printed assistantId into your .env file.
 *
 * Usage:
 *   VAPI_API_KEY=your_key node vapi/setup-fbf-agent.js
 *
 * Prerequisites:
 *   1. Sign up at https://vapi.ai and get your API key
 *   2. Buy a phone number in the Vapi dashboard (Phone Numbers tab)
 *   3. Set env vars (see .env.example additions at bottom of this file)
 */

const VAPI_API_KEY   = process.env.VAPI_API_KEY;
const SERVER_URL     = process.env.RENDER_URL || "https://forged-by-freedom-api-nm4f.onrender.com";
const BRYAN_NUMBER   = process.env.BRYAN_CELL_NUMBER; // e.g. "+17325551234"
const VAPI_NUMBER_ID = process.env.VAPI_PHONE_NUMBER_ID; // from Vapi dashboard

if (!VAPI_API_KEY)   throw new Error("Missing VAPI_API_KEY");
if (!BRYAN_NUMBER)   throw new Error("Missing BRYAN_CELL_NUMBER  (e.g. +17325551234)");
if (!VAPI_NUMBER_ID) throw new Error("Missing VAPI_PHONE_NUMBER_ID (from Vapi dashboard → Phone Numbers)");

// ─── ElevenLabs female voice ─────────────────────────────────────────────────
// Replace ELEVENLABS_FEMALE_VOICE_ID in your .env with your specific voice ID.
// If you don't have one yet, "Rachel" (21m00Tcm4TlvDq8ikWAM) is a solid default.
// To use your own: Vapi dashboard → Voices → Add ElevenLabs voice → paste your voice ID.
const VOICE_ID = process.env.ELEVENLABS_FEMALE_VOICE_ID || "21m00Tcm4TlvDq8ikWAM";

// ─── System Prompt ────────────────────────────────────────────────────────────
const SYSTEM_PROMPT = `
You are Ashley, the professional virtual assistant for Forged by Freedom (FBF) — a premium fitness and body recomposition coaching program founded by Bryan Antonelli.

Your personality: warm, confident, knowledgeable about fitness. You sound like a real person, not a robot. Keep answers concise — callers don't want long speeches.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABOUT FORGED BY FREEDOM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FBF's flagship program is the **FBF Recomp Protocol** — a 24-week, comprehensive body recomposition system. It combines advanced compounds (retatrutide, tesofensine, cagrilintide), testosterone optimization, optional GH peptides, custom nutrition planning, and personalized training programming. It is the most complete recomposition system available — designed for serious adults who want real results.

Bryan works with a limited number of clients at a time to ensure every client gets personal attention.

How to apply: forgedbyfreedom.org or email forgedbyfreedom@gmail.com

Pricing: [FILL IN — e.g. "The program investment is $X. Bryan will go over all details on your consultation call."]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR GOALS ON EVERY CALL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Greet the caller warmly and find out how you can help
2. Answer questions about FBF programs and services
3. Before ending the call, ALWAYS collect:
   - Caller's full name
   - Best callback number
   - Reason for calling / what they're looking for
   Then call the logCallDetails function to save this info
4. Tell them Bryan or a team member will follow up personally

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRANSFER RULES — ACT IMMEDIATELY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Transfer the call to Bryan RIGHT AWAY (no delays, no questions) when ANY of these apply:

FAMILY — Transfer if the caller:
- Says their name is Wendy
- Identifies as Bryan's wife, son, or daughter
- Says "it's the kids" or "it's family"

URGENT BUSINESS — Transfer if the caller says:
- "emergency" or "urgent"
- "contract ready" or "ready to sign"
- "ready to start" or "I want to move forward today"
- Anything that sounds like an immediate time-sensitive decision

When transferring, say: "One moment — let me connect you with Bryan right now."
Then immediately call the transferCall function. Do not ask follow-up questions first.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMON QUESTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q: How do I get started?
A: Visit forgedbyfreedom.org and click Apply Now, or I can note your info and Bryan will reach out personally.

Q: Is Bryan taking new clients?
A: Bryan works with a limited group at a time. The best way to find out is to apply — spots fill up. I'll make sure he knows you called.

Q: What does the program cost?
A: [INSERT PRICING OR REDIRECT TO CONSULTATION]

Q: What kind of results can I expect?
A: The Recomp Protocol is designed for serious body recomposition — losing fat while maintaining or gaining muscle. Results vary by individual, but clients on a full 24-week protocol typically see significant changes. Bryan can give you a realistic picture on a consultation call.

Q: Do I need to be on TRT or use compounds?
A: Bryan works with clients at various stages. The program is customized to where you are. Best to apply and have that conversation directly with Bryan.

Q: Is this safe?
A: FBF works within established protocols and Bryan's clients are supported with bloodwork guidance and monitoring throughout. It's not for everyone — that's why there's an intake and consultation process.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLOSING THE CALL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Always end with something like:
"Great — I've got your info logged. Bryan will follow up with you personally. Is there anything else I can help you with before I let you go?"

Keep it warm. Keep it real. Never be robotic.
`.trim();

// ─── Assistant Payload ────────────────────────────────────────────────────────
const assistantPayload = {
  name: "Ashley — FBF Phone Agent",

  model: {
    provider: "anthropic",
    model: "claude-opus-4-6",
    messages: [
      {
        role: "system",
        content: SYSTEM_PROMPT,
      },
    ],
    temperature: 0.7,
    maxTokens: 250, // Keep responses short for voice
  },

  voice: {
    provider: "11labs",
    voiceId: VOICE_ID,
    stability: 0.5,
    similarityBoost: 0.75,
    style: 0.4,
    useSpeakerBoost: true,
  },

  firstMessage:
    "Thank you for calling Forged by Freedom! This is Ashley. How can I help you today?",

  endCallMessage:
    "Thanks for calling Forged by Freedom. Have a great day!",

  endCallPhrases: [
    "goodbye",
    "talk to you later",
    "thanks bye",
    "that's all I needed",
  ],

  // Webhook — Vapi will POST events here (call ended, function calls, etc.)
  serverUrl: `${SERVER_URL}/vapi/webhook`,
  serverUrlSecret: process.env.VAPI_WEBHOOK_SECRET || "", // optional signature verification

  tools: [
    // ── Built-in transfer tool ──────────────────────────────────────────────
    {
      type: "transferCall",
      destinations: [
        {
          type: "number",
          number: BRYAN_NUMBER,
          message: "One moment — connecting you with Bryan right now.",
        },
      ],
    },

    // ── Custom function: log caller details ─────────────────────────────────
    {
      type: "function",
      function: {
        name: "logCallDetails",
        description:
          "Save the caller's name, callback number, and reason for calling. Call this before ending any non-transferred call.",
        parameters: {
          type: "object",
          properties: {
            callerName: {
              type: "string",
              description: "The caller's full name",
            },
            callbackNumber: {
              type: "string",
              description: "Best phone number to call them back",
            },
            reasonForCall: {
              type: "string",
              description: "Brief summary of why they called and what they need",
            },
            followUpAction: {
              type: "string",
              description:
                "Specific follow-up needed (e.g. 'send pricing info', 'schedule consult', 'urgent callback')",
            },
          },
          required: ["callerName", "callbackNumber", "reasonForCall"],
        },
      },
      // Vapi will POST to this URL when Claude calls logCallDetails
      server: {
        url: `${SERVER_URL}/vapi/log-call`,
      },
    },
  ],

  // Silence / interruption settings
  silenceTimeoutSeconds: 20,
  maxDurationSeconds: 600, // 10 min max call
  backgroundDenoisingEnabled: true,
  modelOutputInMessagesEnabled: true,
};

// ─── Create the Assistant ─────────────────────────────────────────────────────
async function createAssistant() {
  console.log("Creating FBF Ashley agent in Vapi...\n");

  const res = await fetch("https://api.vapi.ai/assistant", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${VAPI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(assistantPayload),
  });

  const data = await res.json();

  if (!res.ok) {
    console.error("❌ Failed to create assistant:", JSON.stringify(data, null, 2));
    process.exit(1);
  }

  console.log("✅ Ashley agent created successfully!\n");
  console.log(`Assistant ID: ${data.id}`);
  console.log(`Name:         ${data.name}`);
  console.log(`Created:      ${data.createdAt}\n`);

  // ── Assign the phone number to this assistant ─────────────────────────────
  await assignPhoneNumber(data.id);

  console.log("─────────────────────────────────────────────");
  console.log("Add this to your .env on Render:");
  console.log(`VAPI_ASSISTANT_ID=${data.id}`);
  console.log("─────────────────────────────────────────────\n");
  console.log("Next steps:");
  console.log("1. Add VAPI_ASSISTANT_ID to your Render env vars");
  console.log("2. Set call forwarding on your phone (instructions in README)");
  console.log("3. Test by calling your Vapi number");
}

async function assignPhoneNumber(assistantId) {
  console.log(`Assigning phone number ${VAPI_NUMBER_ID} to assistant...`);

  const res = await fetch(`https://api.vapi.ai/phone-number/${VAPI_NUMBER_ID}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${VAPI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ assistantId }),
  });

  const data = await res.json();

  if (!res.ok) {
    console.error("⚠️  Phone number assignment failed:", JSON.stringify(data, null, 2));
    console.log("You can assign it manually in the Vapi dashboard → Phone Numbers → edit → set assistant.");
    return;
  }

  console.log(`✅ Phone number assigned: ${data.number}`);
  console.log(`   Forward your cell to this number: ${data.number}\n`);
}

createAssistant().catch(console.error);

/*
─────────────────────────────────────────────────────────────
ADD THESE TO YOUR .env / RENDER ENV VARS
─────────────────────────────────────────────────────────────
VAPI_API_KEY=                     # from vapi.ai dashboard → API Keys
VAPI_ASSISTANT_ID=                # printed after running this script
VAPI_PHONE_NUMBER_ID=             # from Vapi dashboard → Phone Numbers tab
VAPI_WEBHOOK_SECRET=              # optional — set in Vapi dashboard for signature verification
BRYAN_CELL_NUMBER=+1XXXXXXXXXX    # your actual cell number (E.164 format)
ELEVENLABS_FEMALE_VOICE_ID=       # your ElevenLabs female voice ID
                                  # or leave blank to use default Rachel voice
─────────────────────────────────────────────────────────────
*/
