import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const AccountsPage = lazy(() => import("@/routes/accounts"));
const AddAccountPage = lazy(() => import("@/routes/add-account"));
const InsightsPage = lazy(() => import("@/routes/insights"));
const MorePage = lazy(() => import("@/routes/more"));
const OverviewPage = lazy(() => import("@/routes/index"));
const RecurringPage = lazy(() => import("@/routes/recurring"));
const RulesPage = lazy(() => import("@/routes/rules"));
const SpendingPage = lazy(() => import("@/routes/spending"));
const TransactionsPage = lazy(() => import("@/routes/transactions"));
const TransfersPage = lazy(() => import("@/routes/transfers"));

const queryClient = new QueryClient();

function currentPath() {
  const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");
  let pathname = window.location.pathname;
  if (basePath && pathname.startsWith(basePath)) {
    pathname = pathname.slice(basePath.length) || "/";
  }
  return pathname.replace(/\/+$/, "") || "/";
}

const ROUTES: Record<string, React.ComponentType> = {
  "/": OverviewPage,
  "/spending": SpendingPage,
  "/transactions": TransactionsPage,
  "/accounts": AccountsPage,
  "/more": MorePage,
  "/rules": RulesPage,
  "/transfers": TransfersPage,
  "/recurring": RecurringPage,
  "/add-account": AddAccountPage,
  "/insights": InsightsPage,
};

export default function App() {
  const Page = ROUTES[currentPath()] ?? OverviewPage;

  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<div className="min-h-screen bg-background" />}>
        <Page />
      </Suspense>
    </QueryClientProvider>
  );
}
