import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { ExternalLink, RefreshCw, Link2, CheckCircle2 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { createConnectSession, getConnectStatus, syncAllAccounts } from "@/lib/api/client";
import type { ConnectSession } from "@/lib/api/types";

export default function AddAccountPage() {
  const [session, setSession] = useState<ConnectSession | null>(null);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [syncText, setSyncText] = useState<string | null>(null);

  const createSession = useMutation({
    mutationFn: createConnectSession,
    onSuccess: (data) => {
      setSession(data);
      setStatusText(null);
    },
  });

  const checkStatus = useMutation({
    mutationFn: () => getConnectStatus(session!.session_token),
    onSuccess: (data) =>
      setStatusText(
        data.status === "completed"
          ? `Linked! Plaid item ${data.item_id}. Sync below to pull data.`
          : `Session status: ${data.status}. Finish Plaid Link, then re-check.`,
      ),
  });

  const sync = useMutation({
    mutationFn: syncAllAccounts,
    onSuccess: (data) => setSyncText(data.summary),
  });

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Add a bank account</h1>
        <p className="text-sm text-muted-foreground">
          Connect a new bank through Plaid, then sync balances and transactions.
        </p>
      </div>

      <Section title="Connect">
        <ol className="mb-4 space-y-1 text-sm text-muted-foreground">
          <li>1. Generate a secure link (valid 20 minutes).</li>
          <li>2. Open Plaid Link and connect your bank.</li>
          <li>3. Sync to pull the new account's data.</li>
        </ol>

        <button
          onClick={() => createSession.mutate()}
          disabled={createSession.isPending}
          className="inline-flex h-10 items-center gap-2 rounded-md bg-foreground px-4 text-sm font-medium text-background hover:bg-foreground/90 disabled:opacity-60"
        >
          <Link2 className="h-4 w-4" />
          {createSession.isPending ? "Generating…" : "Generate secure link"}
        </button>
        {createSession.isError ? (
          <p className="mt-2 text-sm text-red-600">{(createSession.error as Error).message}</p>
        ) : null}

        {session ? (
          <div className="mt-4 space-y-3 rounded-md border border-border p-3">
            <a
              href={session.connect_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-10 items-center gap-2 rounded-md bg-sky-600 px-4 text-sm font-medium text-white hover:bg-sky-700"
            >
              <ExternalLink className="h-4 w-4" />
              Open Plaid Link
            </a>
            <p className="text-xs text-muted-foreground">
              Opens in a new tab · link expires {new Date(session.expires_at).toLocaleTimeString()}
            </p>
            <div className="break-all rounded bg-secondary/50 p-2 text-xs text-muted-foreground">
              {session.connect_url}
            </div>
            <p className="text-xs text-muted-foreground">
              OAuth banks need <code>PLAID_REDIRECT_URI</code> publicly reachable (see
              <code> scripts/connect_funnel.sh</code>). Sandbox and non-OAuth banks work over the tailnet directly.
            </p>
            <button
              onClick={() => checkStatus.mutate()}
              disabled={checkStatus.isPending}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-input px-3 text-sm font-medium hover:bg-secondary disabled:opacity-60"
            >
              <CheckCircle2 className="h-4 w-4" />
              I've finished — check status
            </button>
            {statusText ? <p className="text-sm text-foreground">{statusText}</p> : null}
          </div>
        ) : null}
      </Section>

      <Section title="Sync" className="mt-4">
        <p className="mb-3 text-sm text-muted-foreground">
          After linking, sync to pull balances and history (backfill can take a few minutes).
        </p>
        <button
          onClick={() => sync.mutate()}
          disabled={sync.isPending}
          className="inline-flex h-10 items-center gap-2 rounded-md border border-input px-4 text-sm font-medium hover:bg-secondary disabled:opacity-60"
        >
          <RefreshCw className={"h-4 w-4 " + (sync.isPending ? "animate-spin" : "")} />
          {sync.isPending ? "Syncing…" : "Sync all accounts"}
        </button>
        {syncText ? <p className="mt-2 text-sm text-emerald-700">{syncText}</p> : null}
        {sync.isError ? <p className="mt-2 text-sm text-red-600">{(sync.error as Error).message}</p> : null}
      </Section>
    </AppShell>
  );
}
