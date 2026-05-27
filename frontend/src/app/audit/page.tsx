import Link from "next/link";

import { backendJSON, type UserOut } from "@/lib/backend";

type AuditEvent = {
  id: number;
  actor_id: number | null;
  mandate_id: number | null;
  kind: string;
  payload_redacted: Record<string, unknown> | null;
  occurred_at: string;
};

type AuditEventListOut = {
  items: AuditEvent[];
  total: number;
};

export default async function AuditPage() {
  let user: UserOut | null = null;
  let data: AuditEventListOut | null = null;
  let error: string | null = null;

  try {
    user = await backendJSON<UserOut>("/me");
    if (user.role === "admin") {
      data = await backendJSON<AuditEventListOut>("/audit-events?limit=100");
    }
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="flex items-baseline justify-between border-b border-neutral-200 pb-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Audit-Protokoll</h1>
          <p className="text-sm text-neutral-600">
            Redigierte Betriebsereignisse für Quellenprüfung und Freigaben
          </p>
        </div>
        <nav className="flex gap-4 text-sm">
          <Link href="/mandates" className="text-neutral-600 underline hover:text-neutral-900">
            Mandate
          </Link>
          <Link href="/anchors" className="text-neutral-600 underline hover:text-neutral-900">
            Anchor-Bibliothek
          </Link>
        </nav>
      </header>

      {error && (
        <div className="mt-6 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          Backend nicht erreichbar: <code>{error}</code>
        </div>
      )}

      {!error && user && user.role !== "admin" && (
        <div className="mt-6 rounded border border-neutral-300 bg-neutral-50 p-4 text-sm text-neutral-700">
          Das Audit-Protokoll ist Administratoren vorbehalten.
        </div>
      )}

      {data && (
        <section className="mt-8">
          <p className="mb-4 text-sm text-neutral-600">
            {data.total} Ereignisse, angezeigt werden die neuesten {data.items.length}.
          </p>
          {data.items.length === 0 ? (
            <div className="rounded border border-dashed border-neutral-300 p-10 text-center text-sm text-neutral-500">
              Noch keine protokollierten Ereignisse.
            </div>
          ) : (
            <div className="overflow-hidden rounded border border-neutral-200">
              <table className="w-full table-fixed text-left text-sm">
                <colgroup>
                  <col className="w-44" />
                  <col className="w-56" />
                  <col className="w-36" />
                  <col />
                </colgroup>
                <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Zeitpunkt</th>
                    <th className="px-4 py-3 font-medium">Ereignis</th>
                    <th className="px-4 py-3 font-medium">Mandat</th>
                    <th className="px-4 py-3 font-medium">Redigierte Daten</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200">
                  {data.items.map((event) => (
                    <tr key={event.id} className="align-top">
                      <td className="whitespace-nowrap px-4 py-3 text-neutral-600">
                        {new Date(event.occurred_at).toLocaleString("de-DE")}
                      </td>
                      <td className="px-4 py-3 font-medium">{event.kind}</td>
                      <td className="px-4 py-3 text-neutral-600">
                        {event.mandate_id ?? "allgemein"}
                      </td>
                      <td className="px-4 py-3">
                        <pre className="whitespace-pre-wrap break-all text-xs text-neutral-700">
                          {JSON.stringify(event.payload_redacted ?? {}, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
