import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AccountsPage from "@/routes/accounts";
import AddAccountPage from "@/routes/add-account";
import MorePage from "@/routes/more";
import OverviewPage from "@/routes/index";
import RecurringPage from "@/routes/recurring";
import RulesPage from "@/routes/rules";
import SpendingPage from "@/routes/spending";
import TransactionsPage from "@/routes/transactions";
import TransfersPage from "@/routes/transfers";

const queryClient = new QueryClient();

function currentPath() {
  const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");
  let pathname = window.location.pathname;
  if (basePath && pathname.startsWith(basePath)) {
    pathname = pathname.slice(basePath.length) || "/";
  }
  return pathname.replace(/\/+$/, "") || "/";
}

export default function App() {
  const path = currentPath();

  let page = <OverviewPage />;
  if (path === "/spending") page = <SpendingPage />;
  if (path === "/transactions") page = <TransactionsPage />;
  if (path === "/accounts") page = <AccountsPage />;
  if (path === "/more") page = <MorePage />;
  if (path === "/rules") page = <RulesPage />;
  if (path === "/transfers") page = <TransfersPage />;
  if (path === "/recurring") page = <RecurringPage />;
  if (path === "/add-account") page = <AddAccountPage />;

  return <QueryClientProvider client={queryClient}>{page}</QueryClientProvider>;
}
