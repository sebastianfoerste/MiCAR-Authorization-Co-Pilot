import Link from "next/link";

import { backendJSON } from "@/lib/backend";
import type { IntakeListOut, MandateOut } from "@/lib/types";

export default async function IntakePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let mandate: MandateOut | null = null;
  let intake: IntakeListOut | null = null;
  let error: string | null = null;
  try {
    mandate = await backendJSON<MandateOut>(`/mandates/${id}`);
    intake = await backendJSON<IntakeListOut>(`/mandates/${id}/intake`);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  if (error || !mandate || !intake) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Link href={`/mandates/${id}`} className="text-sm text-neutral-600 underline">
          ← Mandat
        </Link>
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          {error ?? "Intake konnte nicht geladen werden."}
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <Link href={`/mandates/${id}`} className="text-sm text-neutral-600 underline">
        ← {mandate.name}
      </Link>

      <header className="mt-2 border-b border-neutral-200 pb-4">
        <h1 className="text-xl font-semibold tracking-tight">Intake</h1>
        <p className="text-sm text-neutral-600">
          Sektion für Sektion. Eingaben werden auch im Entwurf gespeichert; vollständige
          Validierung beim Übergang in &bdquo;Bereit zur Erstellung&ldquo;.
        </p>
      </header>

      <ul className="mt-6 divide-y divide-neutral-200">
        {intake.sections.map((s) => (
          <li key={s.section_key} className="py-3">
            <div className="flex items-baseline justify-between">
              <div>
                <Link
                  href={`/mandates/${id}/intake/${s.section_key}`}
                  className="font-medium text-blue-700 underline"
                >
                  {s.section_key}
                </Link>
                {s.errors.length > 0 && (
                  <p className="mt-1 text-xs text-amber-700">
                    {s.errors.length} Validierungsmeldung(en).
                  </p>
                )}
              </div>
              <span
                className={
                  "rounded px-2 py-0.5 text-xs " +
                  (s.is_complete
                    ? "bg-emerald-100 text-emerald-900"
                    : "bg-neutral-100 text-neutral-700")
                }
              >
                {s.is_complete ? "vollständig" : "offen"}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
