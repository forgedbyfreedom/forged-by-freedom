"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

// Subscribes to all crm_* table change events on Supabase Realtime and calls
// router.refresh() so the current server-rendered page re-fetches its data.
// Throttled to once per second to avoid thrash during bulk imports.
const TABLES = [
  "crm_clients",
  "crm_products",
  "crm_inventory_lots",
  "crm_orders",
  "crm_order_items",
  "crm_expenses",
  "crm_households",
];

export function RealtimeRefresher() {
  const router = useRouter();

  useEffect(() => {
    const supabase = createClient();
    let pending = false;
    let lastFired = 0;
    const MIN_INTERVAL_MS = 1000;

    const trigger = () => {
      const now = Date.now();
      const wait = Math.max(0, MIN_INTERVAL_MS - (now - lastFired));
      if (pending) return;
      pending = true;
      setTimeout(() => {
        lastFired = Date.now();
        pending = false;
        router.refresh();
      }, wait);
    };

    const channel = supabase.channel("fbf-crm-changes");
    for (const t of TABLES) {
      channel.on(
        "postgres_changes",
        { event: "*", schema: "public", table: t },
        trigger,
      );
    }
    channel.subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [router]);

  return null;
}
