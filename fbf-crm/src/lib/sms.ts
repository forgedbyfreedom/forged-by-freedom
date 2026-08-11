// Fire-and-forget SMS alerts via Twilio. Soft-fails (logs only) so a Twilio
// outage or missing env vars never blocks a CRM write.
//
// Env vars (server-only):
//   TWILIO_ACCOUNT_SID
//   TWILIO_AUTH_TOKEN
//   TWILIO_PHONE_NUMBER   (the Twilio-provided 'from' number)
//   SMS_ALERT_NUMBERS     (comma-separated E.164 destinations,
//                          e.g. "+17757418209,+17757418213")
//
// Reuses the AI Coach's existing Twilio account.

function parseRecipients(): string[] {
  const raw = process.env.SMS_ALERT_NUMBERS || "";
  return raw
    .split(",")
    .map((n) => n.trim())
    .filter(Boolean);
}

function configured(): boolean {
  return Boolean(
    process.env.TWILIO_ACCOUNT_SID &&
      process.env.TWILIO_AUTH_TOKEN &&
      process.env.TWILIO_PHONE_NUMBER &&
      parseRecipients().length > 0,
  );
}

async function sendOne(to: string, body: string): Promise<void> {
  const sid = process.env.TWILIO_ACCOUNT_SID!;
  const token = process.env.TWILIO_AUTH_TOKEN!;
  const from = process.env.TWILIO_PHONE_NUMBER!;
  const url = `https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`;
  const params = new URLSearchParams({ To: to, From: from, Body: body });
  const auth = Buffer.from(`${sid}:${token}`).toString("base64");

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params,
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    console.error(`[SMS] Twilio ${res.status} -> ${to}: ${txt}`);
  }
}

// Fire-and-forget: don't await this from a server action. Returns immediately.
export function notifyInventory(message: string): void {
  if (!configured()) {
    console.log(`[SMS] not configured — would have sent: ${message}`);
    return;
  }
  const recipients = parseRecipients();
  const body = `[FBF] ${message}`;
  // Don't block the server action on the SMS round-trips.
  Promise.allSettled(recipients.map((r) => sendOne(r, body))).catch(() => {
    /* swallow — already logged per-recipient */
  });
}
