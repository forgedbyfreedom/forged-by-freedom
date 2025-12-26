// src/fbfAnswer.js

/**
 * Build a fully formatted Forged by Freedom answer in your house style.
 *
 * Option B: neutral explanation, then "Coach Bryan" close.
 */

export async function buildFbfAnswer({ question, matches, technicalText, coachLine }) {
  // 1. Build podcast quote section
  const topQuotes = (matches || [])
    .filter(m => m.quote && m.podcastTitle)
    .slice(0, 3); // at least 3 when available

  const quotesBlock = topQuotes.length
    ? topQuotes.map((m, i) => {
        const ep = m.episodeTitle || m.episodeSubject || "Unknown Episode";
        const sp = m.speaker || "Unknown Speaker";
        return `"${m.quote.trim()}"
— ${m.podcastTitle.trim()}, Episode: ${ep.trim()}, Speaker: ${sp.trim()}`;
      }).join("\n\n")
    : `No direct podcast matches were found for this exact question, but the answer below is based on your uploaded transcripts and medical references.`;

  // 2. Technical / medical breakdown (neutral, factual)
  const technicalBlock = technicalText?.trim()
    ? technicalText.trim()
    : "Technical explanation not available. (Need to wire LLM / medical content here.)";

  // 3. Coach Bryan closer
  const coachBlock = coachLine?.trim()
    ? coachLine.trim()
    : `You know what to do with this. Execute the plan, adjust based on feedback, and stop negotiating with your excuses.
— Coach Bryan, Forged by Freedom Strength & Nutrition`;

  // 4. Final formatted answer
  const final = `
🔹 QUESTION
${question.trim()}

🔹 PERSPECTIVES FROM THE PODCASTS
${quotesBlock}

🔹 WHY THIS WORKS (TECHNICAL BREAKDOWN)
${technicalBlock}

🔹 EXECUTION ORDERS
- Apply the protocol that aligns with your current phase (cut, recomp, or blast).
- Track biofeedback: sleep, digestion, pumps, mood, HR, BP, and performance.
- Adjust one variable at a time: dose, timing, or volume — never everything at once.

const coachBlock = `
=== COACH BRYAN — FORGED BY FREEDOM ===
No excuses. Discipline over everything!

— Coach Bryan, Forged by Freedom Strength & Nutrition`;
🔹 COACH BRYAN (FORGED BY FREEDOM)
${coachBlock}
  `.trim();

  return final;
}

