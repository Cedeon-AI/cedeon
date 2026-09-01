import { cookies } from "next/headers";
import type { MeResponse } from "@/lib/api/generated/types.gen";
import { apiInternalUrl } from "@/lib/api-internal";

export type Session = MeResponse;

/** Resolve the current session server-side by asking the API, forwarding cookies. */
export async function getSession(): Promise<Session | null> {
  const cookieHeader = (await cookies()).toString();
  if (!cookieHeader) return null;
  try {
    const res = await fetch(`${apiInternalUrl()}/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as Session;
  } catch {
    return null;
  }
}
