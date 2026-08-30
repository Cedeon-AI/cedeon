import type { CreateClientConfig } from "./generated/client.gen";

/**
 * Browser requests go to the same origin under /api (Next rewrites to the API).
 * Cookies are the session; always send them.
 */
export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: "/api",
  credentials: "same-origin",
});
