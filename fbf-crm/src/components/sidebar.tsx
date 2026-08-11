"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Package,
  Boxes,
  ShoppingCart,
  Receipt,
  BarChart3,
  Upload,
  History,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/clients", label: "Clients", icon: Users },
  { href: "/products", label: "Products", icon: Package },
  { href: "/inventory", label: "Inventory", icon: Boxes },
  { href: "/orders", label: "Orders", icon: ShoppingCart },
  { href: "/expenses", label: "Expenses", icon: Receipt },
  { href: "/import", label: "Import", icon: Upload },
  { href: "/reports", label: "Reports", icon: BarChart3 },
  { href: "/audit", label: "Audit Log", icon: History },
];

export function Sidebar({ email }: { email?: string | null }) {
  const pathname = usePathname();

  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-border bg-surface md:h-screen md:w-64 md:border-b-0 md:border-r">
      {/* Brand */}
      <div className="border-b border-border px-5 py-5">
        <div className="fbf-eyebrow mb-1">Forged by Freedom</div>
        <div className="fbf-title-gradient text-xl font-black tracking-tight">FBF CRM</div>
        {email && (
          <div className="mt-2 truncate text-[11px] text-subtle">{email}</div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex flex-row gap-1 overflow-x-auto p-3 md:flex-col md:overflow-visible">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "group relative flex shrink-0 items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-surface-2 text-foreground"
                  : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
              )}
            >
              {active && (
                <span
                  aria-hidden
                  className="absolute left-0 top-1/2 hidden h-5 w-[3px] -translate-y-1/2 rounded-r bg-primary shadow-fbf-glow-sm md:block"
                />
              )}
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors",
                  active ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
                )}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Sign out */}
      <form action="/auth/signout" method="post" className="mt-auto hidden border-t border-border p-3 md:block">
        <button
          type="submit"
          className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
        >
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </form>
    </aside>
  );
}
