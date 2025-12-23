// backend/http-functions.js
import { ok, serverError } from 'wix-http-functions';

/**
 * 🔹 GET stats for header / homepage
 * URL: https://www.forgedbyfreedom.com/_functions/stats
 */
export async function get_stats(request) {
  try {
    const res = await fetch("https://ai-fbf-search-1.onrender.com/stats");

    if (!res.ok) {
      throw new Error("Stats service unavailable");
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
}

/**
 * 🔹 POST search query from Wix UI
 * URL: https://www.forgedbyfreedom.com/_functions/search
 */
export async function post_search(request) {
  try {
    const body = await request.body.json();

    const res = await fetch(
      "https://ai-fbf-search-1.onrender.com/search",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: body.query,
          top_k: body.top_k || 5
        })
      }
    );

    if (!res.ok) {
      throw new Error("Search service unavailable");
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
}
