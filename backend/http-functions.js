// backend/http-functions.js
import { ok, serverError } from 'wix-http-functions';

// Public endpoint:
// https://www.forgedbyfreedom.com/_functions/stats
export async function get_stats() {
  try {
    const res = await fetch(
      "https://ai-fbf-search-1.onrender.com/stats",
      { method: "GET" }
    );

    if (!res.ok) {
      throw new Error("Failed to fetch stats from AI backend");
    }

    const data = await res.json();

    return ok({
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      },
      body: data
    });

  } catch (err) {
    return serverError({
      headers: { "Content-Type": "application/json" },
      body: { error: err.message }
    });
  }
