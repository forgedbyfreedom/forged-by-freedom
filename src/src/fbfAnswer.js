// fbfAnswer.js
export function formatAnswer({ question, podcastQuotes = [], medical = "", coach = "" }) {
  let quoteSection = "";
  if (podcastQuotes.length > 0) {
    quoteSection = "=== PODCAST SUPPORT ===\n" +
      podcastQuotes.map(q => `"${q.quote}"\n— ${q.show}, Episode: ${q.episode}, Speaker: ${q.speaker}`).join("\n\n") +
      "\n\n";
  }

  let medicalSection = "";
  if (medical) {
    medicalSection = "=== MEDICAL / TECHNICAL BREAKDOWN ===\n" + medical + "\n\n";
  }

  const coachSection = `=== COACH BRYAN — FORGED BY FREEDOM ===
${coach || "No excuses. Discipline over everything!"}
`;

  return {
    question,
    answer: `${quoteSection}${medicalSection}${coachSection}`
  };
}

