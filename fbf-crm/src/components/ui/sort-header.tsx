import Link from "next/link";
import { ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export function SortHeader<K extends string>({
  label,
  k,
  activeKey,
  activeDir,
  basePath,
  align = "left",
  extraParams,
}: {
  label: string;
  k: K;
  activeKey: K;
  activeDir: "asc" | "desc";
  basePath: string;
  align?: "left" | "right";
  extraParams?: Record<string, string | undefined>;
}) {
  const active = activeKey === k;
  const nextDir = active && activeDir === "desc" ? "asc" : "desc";
  const params = new URLSearchParams({ sort: k, dir: nextDir });
  if (extraParams) {
    for (const [key, v] of Object.entries(extraParams)) {
      if (v) params.set(key, v);
    }
  }
  return (
    <th className={cn("px-5 py-3 font-semibold", align === "right" ? "text-right" : "text-left")}>
      <Link
        href={`${basePath}?${params.toString()}`}
        className={cn(
          "inline-flex items-center gap-1 transition-colors hover:text-primary",
          active ? "text-primary" : "",
        )}
      >
        {label}
        {!active && <ArrowUpDown className="h-3 w-3 opacity-50" />}
        {active && activeDir === "asc" && <ArrowUp className="h-3 w-3" />}
        {active && activeDir === "desc" && <ArrowDown className="h-3 w-3" />}
      </Link>
    </th>
  );
}

export function parseSort<K extends string>(
  raw: string | undefined,
  dir: string | undefined,
  allowed: Record<K, true>,
  defaults: { sort: K; dir: "asc" | "desc" },
): { sort: K; dir: "asc" | "desc" } {
  const k = raw && (raw as K) in allowed ? (raw as K) : defaults.sort;
  const d: "asc" | "desc" = dir === "asc" ? "asc" : dir === "desc" ? "desc" : defaults.dir;
  return { sort: k, dir: d };
}
