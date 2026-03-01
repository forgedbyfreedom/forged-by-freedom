// ═══════════════════════════════════════════════════════════
//  AI COACH — Page Code (paste into Wix page { } panel)
// ═══════════════════════════════════════════════════════════
import { askCoach } from "backend/aiQuery";

$w.onReady(() => {
  // Element ID must match the HtmlComponent ID in Wix editor (check Properties panel)
  const htmlComp = $w("#html2");
  console.log("AI Coach page code loaded, htmlComp type:", htmlComp.type);

  htmlComp.onMessage(async (event) => {
    let msg;
    try {
      msg = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
    } catch (e) {
      return;
    }

    if (msg.type === "search") {
      await handleSearch(msg.question);
    } else if (msg.type === "bloodwork") {
      await handleBloodwork(msg.labText);
    } else if (msg.type === "openRecompProtocol") {
      // Navigate to the FBF Recomp Protocol page on the Wix site
      import("wix-location").then(loc => loc.to("/fbf-recomp-protocol"));
    }
  });
});

async function handleSearch(question) {
  try {
    const res = await askCoach({ question });
    if (res && res.status === "OK") {
      sendToHtml({ type: "searchResult", answer: res.answer || "No answer returned." });
    } else {
      sendToHtml({ type: "searchResult", error: res?.message || "Unknown error. Try again." });
    }
  } catch (err) {
    console.error("AI Coach error:", err);
    sendToHtml({ type: "searchResult", error: "Server error. Please try again in a moment." });
  }
}

async function handleBloodwork(labText) {
  const question = `Please analyze my bloodwork results. For each marker, tell me: the value, standard lab range, enhanced athlete acceptable range, and your assessment (normal/watch/intervene/red flag). Flag anything concerning, explain which compounds could cause abnormal values, and provide the intervention ladder (lifestyle → supplements with doses → pharmaceuticals with doses → discontinuation thresholds). Here are my results:\n\n${labText}`;

  try {
    const res = await askCoach({ question });
    if (res && res.status === "OK") {
      sendToHtml({ type: "bloodworkResult", answer: res.answer || "No answer returned." });
    } else {
      sendToHtml({ type: "bloodworkResult", error: res?.message || "Analysis failed. Try again." });
    }
  } catch (err) {
    console.error("Bloodwork error:", err);
    sendToHtml({ type: "bloodworkResult", error: "Server error. Please try again in a moment." });
  }
}

function sendToHtml(data) {
  $w("#html2").postMessage(JSON.stringify(data));
}
