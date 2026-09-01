import type { AuthConfigResponse } from "@/lib/api/generated/types.gen";
import { apiInternalUrl } from "@/lib/api-internal";

export type SignupMode = AuthConfigResponse["signup_mode"];

/** How registration is gated (ADR-0028). Resolved server-side so /register renders
 *  the right form with no flash. The API enforces the mode regardless. */
export async function getSignupMode(): Promise<SignupMode> {
  try {
    const res = await fetch(`${apiInternalUrl()}/auth/config`, { cache: "no-store" });
    if (!res.ok) return "open";
    return ((await res.json()) as AuthConfigResponse).signup_mode;
  } catch {
    return "open";
  }
}
