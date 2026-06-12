import Link from "next/link";
import { Trash2, ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { cn, formatMoney } from "@/lib/utils";
import {
  AddNewSection,
  ErrorBanner,
  Field,
  Input,
  SubmitButton,
  Textarea,
} from "@/components/ui/form-primitives";
import { addClient, deleteClient } from "./actions";

type SortKey =
  | "name"
  | "email"
  | "order_count"
  | "lifetime_revenue_cents"
  | "avg_order_cents"
  | "largest_order_cents"
  | "last_order_at";

const SORT_KEYS: Record<SortKey, true> = {
  name: true,
  email: true,
  order_count: true,
  lifetime_revenue_cents: true,
  avg_order_cents: true,
  largest_order_cents: true,
  last_order_at: true,
};

const DEFAULT_SORT: SortKey = "last_order_at";
const DEFAULT_DIR: "asc" | "desc" = "desc";

function SortHeader({
  label,
  k,
  activeKey,
  activeDir,
  align = "left",
}: {
  label: string;
  k: SortKey;
  activeKey: SortKey;
  activeDir: "asc" | "desc";
  align?: "left" | "right";
}) {
  const active = activeKey === k;
  const nextDir = active && activeDir === "desc" ? "asc" : "desc";
  const href = `/clients?sort=${k}&dir=${nextDir}`;
  return (
    <th
      className={cn(
        "px-5 py-3 font-semibold",
        align === "right" ? "text-right" : "text-left",
      )}
    >
      <Link
        href={href}
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

export default async function ClientsPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; sort?: string; dir?: string }>;
}) {
  const { error: errorParam, sort, dir } = await searchParams;

  const sortKey: SortKey = sort && sort in SORT_KEYS ? (sort as SortKey) : DEFAULT_SORT;
  const sortDir: "asc" | "desc" = dir === "asc" ? "asc" : DEFAULT_DIR;

  const supabase = await createClient();
  const { data, error } = await supabase
    .from("crm_clients_with_stats")
    .select(
      "id, name, email, phone, city, state, last_contact_at, order_count, lifetime_revenue_cents, largest_order_cents, avg_order_cents, last_order_at",
    )
    .order(sortKey, { ascending: sortDir === "asc", nullsFirst: false })
    .limit(200);

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Customer Records</div>
        <h1 className="text-3xl font-black tracking-tight">Clients</h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Searchable client list with product history, lifetime revenue, and last contact. Click
          any column header to sort.
        </p>
      </header>

      <ErrorBanner message={errorParam} />

      <AddNewSection title="Add New Client" defaultOpen={!!errorParam}>
        <form action={addClient} className="grid gap-4 md:grid-cols-2">
          <Field label="Name" required className="md:col-span-2">
            <Input name="name" required placeholder="Jane Doe" />
          </Field>
          <Field label="Email">
            <Input name="email" type="email" placeholder="jane@example.com" />
          </Field>
          <Field label="Phone">
            <Input name="phone" placeholder="+1 555 555 5555" />
          </Field>
          <Field label="Address Line 1" className="md:col-span-2">
            <Input name="address_line1" />
          </Field>
          <Field label="Address Line 2" className="md:col-span-2">
            <Input name="address_line2" />
          </Field>
          <Field label="City">
            <Input name="city" />
          </Field>
          <Field label="State / Region">
            <Input name="state" />
          </Field>
          <Field label="Postal Code">
            <Input name="postal_code" />
          </Field>
          <Field label="Country">
            <Input name="country" defaultValue="US" />
          </Field>
          <Field label="Last Contact" hint="Leave blank if unknown">
            <Input name="last_contact_at" type="date" />
          </Field>
          <Field label="Notes" className="md:col-span-2">
            <Textarea name="notes" placeholder="Anything worth remembering" />
          </Field>
          <div className="md:col-span-2">
            <SubmitButton>Add Client</SubmitButton>
          </div>
        </form>
      </AddNewSection>

      {error ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error.message}
        </div>
      ) : (
        <div className="fbf-card !p-0 overflow-hidden">
          {(data?.length || 0) === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No clients yet — add your first one above.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-surface-2 text-[11px] uppercase tracking-wider text-muted-foreground">
                    <SortHeader label="Name" k="name" activeKey={sortKey} activeDir={sortDir} />
                    <SortHeader label="Contact" k="email" activeKey={sortKey} activeDir={sortDir} />
                    <SortHeader
                      label="Orders"
                      k="order_count"
                      activeKey={sortKey}
                      activeDir={sortDir}
                      align="right"
                    />
                    <SortHeader
                      label="Lifetime"
                      k="lifetime_revenue_cents"
                      activeKey={sortKey}
                      activeDir={sortDir}
                      align="right"
                    />
                    <SortHeader
                      label="Avg"
                      k="avg_order_cents"
                      activeKey={sortKey}
                      activeDir={sortDir}
                      align="right"
                    />
                    <SortHeader
                      label="Largest"
                      k="largest_order_cents"
                      activeKey={sortKey}
                      activeDir={sortDir}
                      align="right"
                    />
                    <SortHeader
                      label="Last Order"
                      k="last_order_at"
                      activeKey={sortKey}
                      activeDir={sortDir}
                    />
                    <th className="px-5 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {data!.map((c) => (
                    <tr key={c.id} className="border-b border-border/60 transition-colors hover:bg-surface-2">
                      <td className="px-5 py-3">
                        <div className="font-semibold text-foreground">{c.name}</div>
                        {(c.city || c.state) && (
                          <div className="text-xs text-subtle">
                            {[c.city, c.state].filter(Boolean).join(", ")}
                          </div>
                        )}
                      </td>
                      <td className="px-5 py-3 text-muted-foreground">
                        <div>{c.email}</div>
                        <div className="text-xs">{c.phone}</div>
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums">{c.order_count || 0}</td>
                      <td className="px-5 py-3 text-right tabular-nums">
                        {formatMoney(c.lifetime_revenue_cents || 0)}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-muted-foreground">
                        {formatMoney(c.avg_order_cents || 0)}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-muted-foreground">
                        {c.largest_order_cents != null ? formatMoney(c.largest_order_cents) : "—"}
                      </td>
                      <td className="px-5 py-3 text-xs text-muted-foreground">
                        {c.last_order_at
                          ? new Date(c.last_order_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <form action={deleteClient}>
                          <input type="hidden" name="id" value={c.id} />
                          <button
                            type="submit"
                            aria-label="Delete client"
                            title="Delete (orders are kept, just unlinked)"
                            className="grid h-8 w-8 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground transition-colors hover:border-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </form>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
