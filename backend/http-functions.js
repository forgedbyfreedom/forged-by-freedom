// backend/http-functions.js
import { ok, serverError } from 'wix-http-functions';

const API_BASE = "https://ai-fbf-search-1.onrender.com";

export async function get_stats() {
  try {
    const res = await fetch(`${API_BASE}/stats`);
    if (!res.ok) throw new Error("Stats fetch failed");

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

export async function post_search(request) {
  try {
    const body = await request.body.json();
    const res = await fetch(`${API_BASE}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    if (!res.ok) throw new Error("Search failed");
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
