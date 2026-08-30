import { cookies } from "next/headers";
import type { MeResponse } from "@/lib/api/generated/types.gen";

const API_INTERNAL_URL = process.env.CEDEON_API_INTERNAL_URL ?? "http://localhost:8000";

export type Session = MeResponse;

/** Resolve the current session server-side by asking the API, forwarding cookies. */
export async function getSession(): Promise<Session | null> {
  const cookieHeader = (await cookies()).toString();
  if (!cookieHeader) return null;
  try {
    const res = await fetch(`${API_INTERNAL_URL}/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as Session;
  } catch {
    return null;
  }
}
