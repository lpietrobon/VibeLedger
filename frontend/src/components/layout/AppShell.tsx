import {
  LayoutDashboard,
  TrendingDown,
  Repeat,
  Receipt,
  Wallet,
  MoreHorizontal,
  RefreshCw,
} from "lucide-react";
import type { ReactNode } from "react";

const NAV = [
  { to: "/", label: "Overview", short: "Overview", icon: LayoutDashboard },
  { to: "/spending", label: "Spending", short: "Spending", icon: TrendingDown },
  { to: "/recurring", label: "Recurring", short: "Recurring", icon: Repeat },
  { to: "/transactions", label: "Transactions", short: "Activity", icon: Receipt },
  { to: "/accounts", label: "Accounts", short: "Accounts", icon: Wallet },
  { to: "/more", label: "More", short: "More", icon: MoreHorizontal },
] as const;

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

function appHref(path: string) {
  return `${basePath}${path}`;
}

export function AppShell({ children }: { children: ReactNode }) {
  let pathname = window.location.pathname;
  if (basePath && pathname.startsWith(basePath)) {
    pathname = pathname.slice(basePath.length) || "/";
  }
  pathname = pathname.replace(/\/+$/, "") || "/";

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top bar */}
      <header
        className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75"
        style={{ paddingTop: "env(safe-area-inset-top)" }}
      >
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
          <a href={appHref("/")} className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-foreground text-background text-xs font-bold">
              V
            </span>
            <span className="text-[15px]">VibeLedger</span>
          </a>

          <nav className="ml-6 hidden items-center gap-1 md:flex">
            {NAV.map(({ to, label }) => {
              const active = to === "/" ? pathname === "/" : pathname.startsWith(to);
              return (
                <a
                  key={to}
                  href={appHref(to)}
                  className={
                    "rounded-md px-3 py-1.5 text-sm transition-colors " +
                    (active
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:text-foreground")
                  }
                >
                  {label}
                </a>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-xs text-muted-foreground sm:inline">
              Synced 2m ago
            </span>
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border text-muted-foreground hover:bg-secondary hover:text-foreground"
              aria-label="Sync"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 pb-24 pt-4 md:pb-10 md:pt-6">{children}</main>

      {/* Bottom nav (mobile) */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background/95 backdrop-blur md:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <ul className="mx-auto grid max-w-7xl grid-cols-6">
          {NAV.map(({ to, short, icon: Icon }) => {
            const active = to === "/" ? pathname === "/" : pathname.startsWith(to);
            return (
              <li key={to}>
                <a
                  href={appHref(to)}
                  className={
                    "flex flex-col items-center gap-0.5 px-0.5 py-2 text-[10px] " +
                    (active ? "text-foreground" : "text-muted-foreground")
                  }
                >
                  <Icon className={"h-5 w-5 " + (active ? "text-foreground" : "")} />
                  <span className="max-w-full truncate">{short}</span>
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
