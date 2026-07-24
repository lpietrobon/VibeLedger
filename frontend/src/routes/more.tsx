import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { ChevronRight, RefreshCw, Tag, Filter, Repeat, Plus } from "lucide-react";
import { syncAllAccounts } from "@/lib/api/client";

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

const ITEMS = [
  { label: "Recurring & subscriptions", icon: Repeat, hint: "Review cadence", href: "/recurring" },
  { label: "Category rules", icon: Tag, hint: "Create & apply", href: "/rules" },
  { label: "Transfer detection", icon: Filter, hint: "Confirm pairs", href: "/transfers" },
  { label: "Add account", icon: Plus, hint: "Connect a bank", href: "/add-account" },
];

export default function MorePage() {
  const [syncStatus, setSyncStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [syncMessage, setSyncMessage] = useState("");

  const runSync = async () => {
    setSyncStatus("running");
    setSyncMessage("");
    try {
      const result = await syncAllAccounts();
      setSyncStatus("success");
      setSyncMessage(result.summary);
    } catch (error) {
      setSyncStatus("error");
      setSyncMessage(error instanceof Error ? error.message : "Sync failed");
    }
  };

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">More</h1>
        <p className="text-sm text-muted-foreground">Settings and tools</p>
      </div>
      <Section title="Manage">
        <ul className="-mx-4 -mb-4 divide-y divide-border">
          <li>
            <button
              type="button"
              onClick={runSync}
              disabled={syncStatus === "running"}
              className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-secondary/60 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className={"h-4 w-4 text-muted-foreground " + (syncStatus === "running" ? "animate-spin" : "")} />
              <span className="flex-1 font-medium">Sync accounts</span>
              <span
                className={
                  "text-xs " +
                  (syncStatus === "error"
                    ? "text-red-600"
                    : syncStatus === "success"
                      ? "text-emerald-700"
                      : "text-muted-foreground")
                }
              >
                {syncStatus === "running" ? "Syncing..." : syncMessage || "Pull Plaid data"}
              </span>
            </button>
          </li>
          {ITEMS.map(({ label, icon: Icon, hint, href }) => (
            <li key={label}>
              <a
                href={`${basePath}${href}`}
                className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/60"
              >
                <Icon className="h-4 w-4 text-muted-foreground" />
                <span className="flex-1 font-medium">{label}</span>
                <span className="text-xs text-muted-foreground">{hint}</span>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </a>
            </li>
          ))}
        </ul>
      </Section>
    </AppShell>
  );
}
