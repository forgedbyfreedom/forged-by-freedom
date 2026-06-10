// Minimal CSV parser that handles quoted fields with commas/newlines inside.
// Returns rows of string fields. Skips fully-empty rows.
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      if (row.some((f) => f.trim() !== "")) rows.push(row);
      row = [];
      field = "";
    } else {
      field += c;
    }
  }
  if (field !== "" || row.length) {
    row.push(field);
    if (row.some((f) => f.trim() !== "")) rows.push(row);
  }
  return rows;
}

// Parse a money string like "+ $50.00", "-$12.34", "$5", "(1.50)" → cents (signed).
export function parseSignedMoneyCents(raw: string): number {
  if (!raw) return 0;
  let s = raw.trim();
  let negative = false;
  if (s.startsWith("(") && s.endsWith(")")) {
    negative = true;
    s = s.slice(1, -1);
  }
  if (s.startsWith("-")) {
    negative = true;
    s = s.slice(1);
  } else if (s.startsWith("+")) {
    s = s.slice(1);
  }
  s = s.replace(/[^0-9.]/g, "");
  if (!s) return 0;
  const n = parseFloat(s);
  if (!Number.isFinite(n)) return 0;
  const cents = Math.round(n * 100);
  return negative ? -cents : cents;
}

// Header-row sniffing: find the first row in `rows` containing any of the
// `needles` (case-insensitive). Returns the index, or -1.
export function findHeaderRowIndex(rows: string[][], needles: string[]): number {
  const want = needles.map((n) => n.toLowerCase());
  for (let i = 0; i < Math.min(rows.length, 20); i++) {
    const lc = rows[i].map((c) => c.toLowerCase().trim());
    if (want.every((n) => lc.includes(n))) return i;
  }
  return -1;
}
