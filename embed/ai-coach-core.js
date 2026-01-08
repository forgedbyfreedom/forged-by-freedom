import { queryPinecone } from 'backend/aiQuery';

$w.onReady(() => {
  console.log("🔥 AI Coach ready");

  $w("#searchButton").onClick(async () => {
    const query = $w("#searchInput").value;
    console.log("➡️ Frontend sending:", query);

    if (!query) {
      $w("#searchOutput").text = "Enter a question.";
      return;
    }

    $w("#searchOutput").text = "Thinking…";

    try {
      const result = await queryPinecone(query);
      console.log("⬅️ Frontend received:", result);

      if (!result) {
        $w("#searchOutput").text = "No response from backend.";
        return;
      }

      if (!result.ok) {
        $w("#searchOutput").text = "Backend error: " + result.error;
        return;
      }

      $w("#searchOutput").text =
        typeof result.raw === "string"
          ? result.raw.slice(0, 2000)
          : JSON.stringify(result.raw, null, 2);

    } catch (err) {
      console.error("❌ Frontend error:", err);
      $w("#searchOutput").text = "Frontend exception.";
    }
  });
});
