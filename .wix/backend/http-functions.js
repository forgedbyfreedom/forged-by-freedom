// backend/http-functions.js
// Wix HTTP endpoints for external integrations

import { ok, badRequest, forbidden, serverError } from 'wix-http-functions';
import { getSecret } from 'wix-secrets-backend';
import { ingestTranscriptText } from 'backend/transcriptIngest.jsw';
import { askCoach } from 'backend/aiQuery.jsw';

/* ============================================================
   POST /transcriptIngest
   External endpoint for pushing transcripts
============================================================ */
export async function post_transcriptIngest(request) {
  try {
    // Auth check
    const secret = await getSecret("WIX_INGEST_SECRET");
    const incoming = request.headers["x-fbf-secret"];

    if (!incoming || incoming !== secret) {
      return forbidden({ body: "Unauthorized" });
    }

    const channel = request.query["channel"];
    if (!channel) {
      return badRequest({ body: "Channel required" });
    }

    const text = await request.body.text();
    if (!text) {
      return badRequest({ body: "Body required" });
    }

    const result = await ingestTranscriptText(text, channel);

    return ok({
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: "OK",
        channel,
        chunks: result.total
      })
    });

  } catch (err) {
    console.error("[transcriptIngest ERROR]", err);
    return serverError({ body: err.message });
  }
}

/* ============================================================
   POST /analyze
   Bloodwork analysis — parses pasted lab text via Coach Bryan AI
============================================================ */
export async function post_analyze(request) {
  try {
    const body = await request.body.json();
    const labText = (body?.text || "").trim();

    if (!labText) {
      return badRequest({
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: "Please paste your lab results." })
      });
    }

    // Build a bloodwork analysis prompt and send to Coach Bryan
    const question = `Please analyze my bloodwork results. For each marker, tell me: the value, standard lab range, enhanced athlete acceptable range, and your assessment (normal/watch/intervene/red flag). Flag anything concerning, explain which compounds could cause abnormal values, and provide the intervention ladder (lifestyle → supplements with doses → pharmaceuticals with doses → discontinuation thresholds). Here are my results:\n\n${labText}`;

    const result = await askCoach({ question });

    if (result?.status === "OK") {
      return ok({
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: "OK",
          answer: result.answer,
          sources: result.sources || []
        })
      });
    } else {
      return serverError({
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: result?.message || "Analysis failed" })
      });
    }

  } catch (err) {
    console.error("[analyze ERROR]", err);
    return serverError({
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error: err.message })
    });
  }
}

/* ============================================================
   POST /ask
   External endpoint for AI queries (backup to main API)
============================================================ */
export async function post_ask(request) {
  try {
    const body = await request.body.json();

    if (!body?.question) {
      return badRequest({
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: "Question required" })
      });
    }

    const result = await askCoach({ question: body.question });

    return ok({
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(result)
    });

  } catch (err) {
    console.error("[ask ERROR]", err);
    return serverError({
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error: err.message })
    });
  }
}
