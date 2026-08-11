export function str(fd: FormData, key: string): string | null {
  const v = fd.get(key);
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t === "" ? null : t;
}

export function int(fd: FormData, key: string): number {
  const v = fd.get(key);
  if (typeof v !== "string" || v.trim() === "") return 0;
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : 0;
}

export function moneyCents(fd: FormData, key: string): number {
  const v = fd.get(key);
  if (typeof v !== "string" || v.trim() === "") return 0;
  const n = parseFloat(v.replace(/[^0-9.\-]/g, ""));
  if (!Number.isFinite(n)) return 0;
  return Math.round(n * 100);
}

export function strs(fd: FormData, key: string): string[] {
  return fd
    .getAll(key)
    .filter((v): v is string => typeof v === "string");
}

export function ints(fd: FormData, key: string): number[] {
  return strs(fd, key).map((v) => {
    const n = parseInt(v, 10);
    return Number.isFinite(n) ? n : 0;
  });
}

export function moneyCentsAll(fd: FormData, key: string): number[] {
  return strs(fd, key).map((v) => {
    const n = parseFloat(v.replace(/[^0-9.\-]/g, ""));
    return Number.isFinite(n) ? Math.round(n * 100) : 0;
  });
}
