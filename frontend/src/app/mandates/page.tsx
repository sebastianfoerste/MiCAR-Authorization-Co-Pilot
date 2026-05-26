import Link from "next/link";

import { backendJSON, type MandateOut, type UserOut } from "@/lib/backend";
import { signOut } from "../../../auth";

async function logout() {
  "use server";
  await signOut({ redirectTo: "/sign-in" });
}

export default async function MandatesPage() {
  let user: UserOut | null = null;
  let mandates: MandateOut[] = [];
  let error: string | null = null;
  try {
    user = await backendJSON<UserOut>("/me");
    mandates = await backendJSON<MandateOut[]>("/mandates");
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="flex items-baseline justify-between border-b border-neutral-200 pb-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Mandate</h1>
          <p className="text-sm text-neutral-600">
            MiCAR Authorization Co-Pilot: {user ? `angemeldet als ${user.email}` : "Login läuft..."}
          </p>
        </div>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/anchors" className="text-neutral-600 underline hover:text-neutral-900">
            Anchor-Bibliothek
          </Link>
          <Link href="/mandates/new" className="rounded bg-neutral-900 px-3 py-1.5 text-white">
            Neues Mandat
          </Link>
          <form action={logout}>
            <button className="text-neutral-600 underline hover:text-neutral-900">
              Abmelden
            </button>
          </form>
        </nav>
      </header>

      {error && (
        <div className="mt-6 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          Backend nicht erreichbar: <code>{error}</code>
        </div>
      )}

      <section className="mt-8">
        {mandates.length === 0 ? (
          <div className="rounded border border-dashed border-neutral-300 p-10 text-center text-sm text-neutral-500">
            Noch keine Mandate. Lege ein Mandat für CASP, ART oder EMT an.
          </div>
        ) : (
          <ul className="divide-y divide-neutral-200">
            {mandates.map((m) => (
              <li key={m.id} className="py-3">
                <div className="flex items-baseline justify-between">
                  <Link href={`/mandates/${m.id}`} className="font-medium text-blue-700 underline">
                    {m.name}
                  </Link>
                  <span className="text-xs uppercase tracking-wide text-neutral-500">
                    {m.track} · {m.state}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
