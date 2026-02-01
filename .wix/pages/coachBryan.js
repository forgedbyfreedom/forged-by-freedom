import { askCoach } from "backend/aiQuery";

$w.onReady(() => {

  // Click search button
  $w("#searchButton").onClick(runSearch);

  // Press ENTER in input triggers search
  // Using multiple detection methods for compatibility
  $w("#searchInput").onKeyPress((event) => {
    // Check both event.key and event.keyCode for compatibility
    if (event.key === "Enter" || event.keyCode === 13) {
      runSearch();
    }
  });

  // Alternative: Also try onKeyDown if onKeyPress doesn't work
  // $w("#searchInput").onKeyDown((event) => {
  //   if (event.key === "Enter" || event.keyCode === 13) {
  //     runSearch();
  //   }
  // });

});

async function runSearch() {
  const question = ($w("#searchInput").value || "").trim();

  if (!question) {
    $w("#searchOutput").text = "Enter a question.";
    return;
  }

  // Disable button during search to prevent double-submit
  $w("#searchButton").disable();
  $w("#searchOutput").text = "Coach Bryan is thinking…";

  try {
    const res = await askCoach({ question });
    console.log("askCoach response:", res);

    if (res && res.status === "OK") {
      $w("#searchOutput").text = res.answer || "No answer returned.";
    } else {
      $w("#searchOutput").text = res?.message || "Unknown error. Try again.";
    }

  } catch (err) {
    console.error("AI Coach page error:", err);
    $w("#searchOutput").text = "Server error. Please try again in a moment.";
  } finally {
    $w("#searchButton").enable();
  }
}
