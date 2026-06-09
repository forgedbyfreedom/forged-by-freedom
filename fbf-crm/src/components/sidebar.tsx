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
  { href: "/reports", label: "Reports", icon: BarChart3 },
];

export function Sidebar({ email }: { email?: string | null }) {
  const pathname = usePathname();
  return (
    <aside className="flex w-full shrink-0 flex-col border-b bg-card md:h-screen md:w-60 md:border-b-0 md:border-r">
      <div className="flex items-center justify-between px-4 py-4 md:py-6">
        <div>
          <div className="text-base font-semibold tracking-tight">FBF CRM</div>
          {email && <div className="truncate text-xs text-muted-foreground">{email}</div>}
        </div>
      </div>
      <nav className="flex flex-row gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:overflow-visible md:px-2 md:pb-0">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium",
                active ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/60",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <form action="/auth/signout" method="post" className="mt-auto hidden p-2 md:block">
        <button
          type="submit"
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted/60"
        >
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </form>
    </aside>
  );
}
