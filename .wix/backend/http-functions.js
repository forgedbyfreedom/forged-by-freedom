// backend/http-functions.js
import { ok, forbidden, serverError } from 'wix-http-functions';
import { getSecret } from 'wix-secrets-backend';
import { ingestTranscriptText } from 'backend/transcriptIngest.jsw';

export async function post_transcriptIngest(request) {
  try {
    const allowed = await getSecret("WIX_INGEST_SECRET");
    const incoming = request.headers["x-fbf-secret"];

    if (!incoming || incoming !== allowed) return forbidden();

    const channel = request.query["channel"] ?? "default";
    const body = await request.body.text();

    await ingestTranscriptText(body, channel);

    return ok({ body: `Ingest started for ${channel}` });
  } catch (err) {
    console.error("Ingest error:", err);
    return serverError();
  }
}
