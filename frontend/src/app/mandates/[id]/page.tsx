import Link from "next/link";
import { revalidatePath } from "next/cache";

import { backendFetch, backendJSON } from "@/lib/backend";
import { STATE_LABELS_DE, type IntakeListOut, type MandateOut } from "@/lib/types";

const TRANSITIONS: Record<string, { to: string; label: string }[]> = {
  draft: [{ to: "intake", label: "Intake starten" }],
  intake: [
    { to: "ready_to_generate", label: "Bereit zur Erstellung" },
    { to: "draft", label: "Zurück zu Entwurf" },
  ],
  ready_to_generate: [
    { to: "generated", label: "Paket erstellen (Phase 3)" },
    { to: "intake", label: "Zurück zu Intake" },
  ],
  generated: [{ to: "in_review", label: "In Prüfung" }],
  in_review: [
    { to: "approved", label: "Freigeben" },
    { to: "ready_to_generate", label: "Erneut erzeugen" },
  ],
  approved: [{ to: "filed", label: "Eingereicht markieren" }],
};

export default async function MandatePage({
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

  async function transition(formData: FormData) {
    "use server";
    const to_state = String(formData.get("to_state"));
    await backendFetch(`/mandates/${id}/transition`, {
      method: "POST",
      body: JSON.stringify({ to_state }),
    });
    revalidatePath(`/mandates/${id}`);
  }

  if (error || !mandate) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Link href="/mandates" className="text-sm text-neutral-600 underline">
          ← Mandate
        </Link>
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          {error ?? "Mandat nicht gefunden."}
        </div>
      </main>
    );
  }

  const stateActions = TRANSITIONS[mandate.state] ?? [];
  const completedSections = intake?.sections.filter((s) => s.is_complete).length ?? 0;
  const totalSections = intake?.sections.length ?? 0;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <Link href="/mandates" className="text-sm text-neutral-600 underline">
        ← Mandate
      </Link>

      <header className="mt-2 border-b border-neutral-200 pb-4">
        <h1 className="text-xl font-semibold tracking-tight">{mandate.name}</h1>
        <p className="text-sm text-neutral-600">
          {mandate.client_label ?? "Keine Angabe"} · Track {mandate.track.toUpperCase()} ·{" "}
          <span className="font-medium">{STATE_LABELS_DE[mandate.state]}</span>
        </p>
      </header>

      <section className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded border border-neutral-200 p-4">
          <h2 className="text-sm font-semibold">Intake</h2>
          <p className="mt-1 text-2xl font-medium">
            {completedSections} / {totalSections}
          </p>
          <p className="text-xs text-neutral-500">vollständige Sektionen</p>
          <Link
            href={`/mandates/${id}/intake`}
            className="mt-3 inline-block text-sm text-blue-700 underline"
          >
            Intake öffnen →
          </Link>
        </div>

        <div className="rounded border border-neutral-200 p-4">
          <h2 className="text-sm font-semibold">Zustandswechsel</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {stateActions.length === 0 && (
              <span className="text-xs text-neutral-500">Keine Aktionen verfügbar.</span>
            )}
            {stateActions.map((a) => (
              <form key={a.to} action={transition}>
                <input type="hidden" name="to_state" value={a.to} />
                <button
                  type="submit"
                  className="rounded border border-neutral-900 px-3 py-1.5 text-xs hover:bg-neutral-900 hover:text-white"
                >
                  {a.label}
                </button>
              </form>
            ))}
          </div>
        </div>
      </section>

      {intake?.blocking && intake.blocking.length > 0 && (
        <section className="mt-6 rounded border border-amber-300 bg-amber-50 p-4">
          <h3 className="text-sm font-semibold text-amber-900">
            Blockierend für &bdquo;Bereit zur Erstellung&ldquo;
          </h3>
          <ul className="mt-2 list-disc pl-5 text-xs text-amber-900">
            {intake.blocking.slice(0, 10).map((b) => (
              <li key={b}>{b}</li>
            ))}
            {intake.blocking.length > 10 && (
              <li>… und {intake.blocking.length - 10} weitere.</li>
            )}
          </ul>
        </section>
      )}
    </main>
  );
}
