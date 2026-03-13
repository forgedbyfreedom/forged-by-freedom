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

    // Route to the dedicated bloodwork analysis endpoint on Render API
    const resp = await fetch("https://forged-by-freedom-api-nm4f.onrender.com/analyze-bloodwork", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ labs: labText })
    });
    const result = await resp.json();

    if (result?.answer) {
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
        body: JSON.stringify({ error: result?.error || "Analysis failed" })
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
