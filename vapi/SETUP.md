# FBF AI Phone Agent (Ashley) — Setup Guide

Ashley is your AI call answering agent for Forged by Freedom. She answers calls,
handles FAQs, collects caller info, and transfers directly to you when it's Wendy,
the kids, or someone who's ready to move.

---

## Step 1 — Sign Up for Vapi

1. Go to **https://vapi.ai** and create an account
2. Dashboard → **API Keys** → copy your key
3. Dashboard → **Phone Numbers** → Buy a number (~$2/month)
   - Copy the **Phone Number ID** (looks like `pn_xxxxxxxx`)

---

## Step 2 — Add Your ElevenLabs Female Voice (Optional)

If you have a specific ElevenLabs voice you want Ashley to use:
1. Go to **https://elevenlabs.io** → your Voice Library
2. Find the female voice → copy its **Voice ID**
3. Add it to your env: `ELEVENLABS_FEMALE_VOICE_ID=your_voice_id`

If you skip this, Ashley defaults to "Rachel" — a professional female voice.

---

## Step 3 — Set Environment Variables

Add these to your `.env` file AND to Render's environment variables:

```
VAPI_API_KEY=your_vapi_api_key
VAPI_PHONE_NUMBER_ID=pn_xxxxxxxx
BRYAN_CELL_NUMBER=+1XXXXXXXXXX       ← your actual cell (E.164 format)
ELEVENLABS_FEMALE_VOICE_ID=          ← optional, leave blank for default
VAPI_WEBHOOK_SECRET=                 ← optional, leave blank for now
```

---

## Step 4 — Update the System Prompt with Real Pricing

Before running the setup script, open `vapi/setup-fbf-agent.js` and find:

```
Pricing: [FILL IN — e.g. "The program investment is $X..."]
```

Replace that with your actual pricing or what you want Ashley to say about it.

---

## Step 5 — Run the Setup Script

```bash
cd /Users/bryanantonelli/forged-by-freedom
node vapi/setup-fbf-agent.js
```

This creates Ashley in Vapi and assigns your phone number to her.
It prints your `VAPI_ASSISTANT_ID` — add that to Render env vars too.

---

## Step 6 — Deploy to Render

Push to GitHub (or trigger a manual deploy in Render).
The new `/vapi/webhook` and `/vapi/log-call` routes will be live.

---

## Step 7 — Set Call Forwarding on Your iPhone

You want calls to forward to your Vapi number after ~4 rings (20 seconds).

**Option A — iPhone Settings:**
1. Settings → Phone → **Call Forwarding** → ON
   *(This forwards ALL calls — only use if you want Ashley to always answer)*

**Option B — Conditional Forward (Forward when no answer — RECOMMENDED):**

Dial this code from your iPhone:
```
**61*+1XXXXXXXXXX*11*20#
```
Replace `+1XXXXXXXXXX` with your Vapi phone number.
`20` = seconds before forwarding (≈ 4 rings).

To cancel:
```
##61#
```

**Option C — Via Carrier:**
Call your carrier (Verizon/AT&T/T-Mobile) and ask them to set
"no-answer call forwarding" to your Vapi number after 20 seconds.

---

## Step 8 — Test It

1. Call your Vapi phone number directly first
2. Ashley should answer: *"Thank you for calling Forged by Freedom! This is Ashley..."*
3. Test the transfer: say "this is Wendy" — she should connect you immediately
4. Check call logs: `forged-by-freedom/call-logs/calls-YYYY-MM-DD.json`
5. If Twilio env vars are set, you'll get an SMS summary after each call ends

---

## Transfer Keywords (what triggers an immediate transfer to Bryan)

| Trigger | Who |
|---|---|
| Says name is "Wendy" | Wife |
| "it's the kids" / "it's family" / "it's your son/daughter" | Kids |
| "emergency" / "urgent" | Anyone |
| "contract ready" / "ready to sign" / "ready to start" / "move forward today" | Hot prospect |

---

## Call Logs

Every call is logged to:
```
forged-by-freedom/call-logs/calls-YYYY-MM-DD.json
```

Each line is a JSON object with:
- Caller name + number
- Reason for call
- Full transcript (on call end)
- AI summary of the call

---

## To Modify Ashley's Knowledge

Edit the `SYSTEM_PROMPT` in `vapi/setup-fbf-agent.js` then re-run the script.
It creates a new assistant — update `VAPI_ASSISTANT_ID` in Render with the new ID.

Or update in place via the Vapi dashboard → Assistants → Ashley → edit system prompt.

---

## Costs (approximate)

| Item | Cost |
|---|---|
| Vapi phone number | ~$2/month |
| Vapi usage | ~$0.05–$0.10/min (Claude + ElevenLabs) |
| Twilio SMS summaries | ~$0.0079/text |
| A 3-minute call | ~$0.15–$0.30 |
