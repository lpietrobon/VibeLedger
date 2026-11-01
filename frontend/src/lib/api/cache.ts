import type { QueryClient } from "@tanstack/react-query";

/** Every cached screen is a projection of the same ledger. */
export function invalidateLedger(client: QueryClient) {
  return client.invalidateQueries();
}
