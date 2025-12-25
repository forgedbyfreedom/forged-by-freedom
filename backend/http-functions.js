export async function post_search(request) {
  try {
    const body = await request.body.json();

    // Add debug logs
    console.log("Payload to /search:", JSON.stringify(body, null, 2));

    const res = await fetch(`${API_BASE}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    const responseText = await res.text();
    console.log("Response from /search:", res.status, responseText); // Debug response

    if (!res.ok) throw new Error(`Search failed with status: ${res.status}`);

    const data = JSON.parse(responseText);
    return ok({
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      },
      body: data
    });
  } catch (err) {
    console.error("Error in post_search:", err); // Debug error
    return serverError({
      headers: { "Content-Type": "application/json" },
      body: { error: err.message }
    });
  }
}
