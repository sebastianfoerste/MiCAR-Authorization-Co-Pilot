/**
 * Typed fetch wrapper to the FastAPI backend.
 *
 * Every call mints a fresh HS256 JWT signed with JWT_SHARED_SECRET and sends
 * it as Authorization: Bearer. Token lifetime is 5 minutes — short enough that
 * revocation by deleting the user row takes effect on next call.
 *
 * Server-only. Do not import from client components — the secret never leaves
 * the server process.
 */
import "server-only";

import { SignJWT } from "jose";

import { auth } from "../../auth";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8090";
const JWT_SHARED_SECRET = process.env.JWT_SHARED_SECRET ?? "";
const JWT_ISSUER = process.env.JWT_ISSUER ?? "micar-frontend";
const JWT_AUDIENCE = process.env.JWT_AUDIENCE ?? "micar-backend";

async function mintToken(email: string, name: string | null): Promise<string> {
  if (JWT_SHARED_SECRET.length < 32) {
    throw new Error("JWT_SHARED_SECRET must be configured with at least 32 characters");
  }
  const secret = new TextEncoder().encode(JWT_SHARED_SECRET);
  return await new SignJWT({ name })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(email)
    .setIssuer(JWT_ISSUER)
    .setAudience(JWT_AUDIENCE)
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(secret);
}

export class BackendError extends Error {
  constructor(public status: number, public body: string) {
    super(`backend ${status}: ${body}`);
  }
}

export async function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) throw new Error("not authenticated");
  const token = await mintToken(email, session.user?.name ?? null);

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${BACKEND_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    const body = await res.text();
    throw new BackendError(res.status, body);
  }
  return res;
}

export async function backendJSON<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await backendFetch(path, init);
  return (await res.json()) as T;
}

export type UserOut = {
  id: number;
  email: string;
  name: string | null;
  role: string;
  created_at: string;
  last_login_at: string | null;
};

export type MandateOut = {
  id: number;
  name: string;
  client_label: string | null;
  track: "casp" | "emt" | "art";
  state: string;
  target_filing_date: string | null;
  created_at: string;
  updated_at: string;
};
