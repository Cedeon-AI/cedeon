/**
 * The typed API surface for the web app. Generated from the FastAPI OpenAPI
 * document (`just gen-client`); do not hand-write request/response types.
 *
 * Browser calls go to same-origin `/api` with cookies (see runtime-config.ts).
 */
export * from "./generated";
export { client } from "./generated/client.gen";

export type ProblemDetail = {
  type: string;
  title: string;
  status: number;
  detail?: string;
  correlation_id?: string;
  errors?: { loc: (string | number)[]; msg: string; type: string }[];
};

/** Narrow an unknown thrown/returned error into a problem+json body if it looks like one. */
export function asProblem(value: unknown): ProblemDetail | null {
  if (value && typeof value === "object" && "title" in value && "status" in value) {
    return value as ProblemDetail;
  }
  return null;
}
