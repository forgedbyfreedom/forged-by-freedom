// Format a value as a CSV field — quote when needed, escape inner quotes.
export function csvField(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (/[,"\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function csvRow(values: unknown[]): string {
  return values.map(csvField).join(",");
}

export function moneyDollars(cents: number | null | undefined): string {
  return ((cents || 0) / 100).toFixed(2);
}

export function csvResponse(filename: string, body: string): Response {
  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
