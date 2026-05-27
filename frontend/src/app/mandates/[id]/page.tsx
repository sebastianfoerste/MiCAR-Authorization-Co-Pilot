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
  ready_to_generate: [{ to: "intake", label: "Zurück zu Intake" }],
  generated: [{ to: "in_review", label: "In Prüfung" }],
  in_review: [
    { to: "approved", label: "Freigeben" },
    { to: "ready_to_generate", label: "Intake erneut öffnen" },
  ],
  approved: [{ to: "filed", label: "Eingereicht markieren" }],
};

type CitationProvenance = {
  citation: string;
  anchor_id: number | null;
  source_status: string | null;
  url: string | null;
};

type ReviewUse = {
  id: number;
  clause_key: string;
  title: string;
  template_version: string;
  current_template_version: string | null;
  requires_regeneration: boolean;
  lawyer_review_status: string;
  flagged_by_change_id: number | null;
  rendered_prose: string | null;
  rendered_at: string | null;
  citations: CitationProvenance[];
};

type ArtifactOut = {
  id: number;
  kind: string;
  version: number;
  sha256: string | null;
  created_at: string;
};

function reviewStatusLabel(status: string): string {
  if (status === "approved") return "freigegeben";
  if (status === "rejected") return "zur Überarbeitung";
  if (status === "citation_failed") return "Zitationsfehler";
  return "Prüfung offen";
}

function sourceStatusLabel(status: string | null): string {
  if (status === "verified") return "Quelle geprüft";
  if (status === "fetched_unverified") return "Quellenprüfung offen";
  if (status === "rejected") return "Quelle zurückgewiesen";
  return "Seed, nicht geprüft";
}

export default async function MandatePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let mandate: MandateOut | null = null;
  let intake: IntakeListOut | null = null;
  let reviewUses: ReviewUse[] = [];
  let artifacts: ArtifactOut[] = [];
  let error: string | null = null;
  try {
    mandate = await backendJSON<MandateOut>(`/mandates/${id}`);
    intake = await backendJSON<IntakeListOut>(`/mandates/${id}/intake`);
    reviewUses = await backendJSON<ReviewUse[]>(`/mandates/${id}/renders`);
    artifacts = await backendJSON<ArtifactOut[]>(`/mandates/${id}/artifacts`);
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

  async function renderDrafts() {
    "use server";
    await backendFetch(`/mandates/${id}/render`, { method: "POST" });
    revalidatePath(`/mandates/${id}`);
  }

  async function reviewClause(formData: FormData) {
    "use server";
    const templateUseId = String(formData.get("template_use_id"));
    const decision = String(formData.get("decision"));
    await backendFetch(`/mandates/${id}/renders/${templateUseId}/review`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    });
    revalidatePath(`/mandates/${id}`);
  }

  async function packageApprovedDrafts() {
    "use server";
    await backendFetch(`/mandates/${id}/package`, { method: "POST" });
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

  const completedSections = intake?.sections.filter((s) => s.is_complete).length ?? 0;
  const totalSections = intake?.sections.length ?? 0;
  const exportReady =
    reviewUses.length > 0 &&
    reviewUses.every(
      (use) =>
        use.lawyer_review_status === "approved" &&
        !use.requires_regeneration &&
        use.flagged_by_change_id === null &&
        use.citations.every((citation) => citation.source_status === "verified"),
    );
  const stateActions = (TRANSITIONS[mandate.state] ?? []).filter(
    (action) => action.to !== "approved" || exportReady,
  );

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
          <h2 className="text-sm font-semibold">Workflow</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {stateActions.length === 0 &&
              mandate.state !== "ready_to_generate" &&
              mandate.state !== "in_review" && (
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
            {(mandate.state === "ready_to_generate" || mandate.state === "in_review") && (
              <form action={renderDrafts}>
                <button
                  type="submit"
                  className="rounded bg-neutral-900 px-3 py-1.5 text-xs text-white"
                >
                  {reviewUses.length ? "Entwürfe neu erzeugen" : "Entwürfe erzeugen"}
                </button>
              </form>
            )}
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

      {reviewUses.length > 0 && (
        <section className="mt-8">
          <div className="flex items-baseline justify-between">
            <div>
              <h2 className="text-base font-semibold">Dokumentenprüfung</h2>
              <p className="text-xs text-neutral-600">
                Je Template wird die neueste Fassung angezeigt. Quellenänderungen erzwingen
                eine erneute Erstellung und Freigabe. Neue Template-Fassungen ebenfalls.
              </p>
            </div>
            {exportReady && (
              <form action={packageApprovedDrafts}>
                <button type="submit" className="rounded bg-neutral-900 px-3 py-2 text-xs text-white">
                  Freigegebenes Paket erstellen
                </button>
              </form>
            )}
          </div>

          <ul className="mt-4 space-y-4">
            {reviewUses.map((use) => (
              <li key={use.id} className="rounded border border-neutral-200 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-sm font-medium">{use.title}</h3>
                    <p className="text-xs text-neutral-500">
                      Version {use.template_version} · {reviewStatusLabel(use.lawyer_review_status)}
                      {use.flagged_by_change_id && ` · Quellenänderung ${use.flagged_by_change_id}`}
                    </p>
                    {use.requires_regeneration && (
                      <p className="mt-1 text-xs text-amber-800">
                        Neue Template-Fassung {use.current_template_version ?? "verfügbar"}:
                        Entwurf erneut erzeugen.
                      </p>
                    )}
                  </div>
                  {mandate.state === "in_review" && (
                    <form action={reviewClause} className="flex gap-2">
                      <input type="hidden" name="template_use_id" value={use.id} />
                      <button
                        type="submit"
                        name="decision"
                        value="approved"
                        disabled={
                          use.lawyer_review_status === "citation_failed" ||
                          use.requires_regeneration ||
                          use.flagged_by_change_id !== null ||
                          use.citations.some((citation) => citation.source_status !== "verified")
                        }
                        className="rounded border border-green-700 px-2 py-1 text-xs text-green-800 disabled:opacity-40"
                      >
                        Freigeben
                      </button>
                      <button
                        type="submit"
                        name="decision"
                        value="rejected"
                        className="rounded border border-red-700 px-2 py-1 text-xs text-red-800"
                      >
                        Überarbeiten
                      </button>
                    </form>
                  )}
                </div>
                <pre className="mt-3 max-h-44 overflow-auto whitespace-pre-wrap rounded bg-neutral-50 p-3 text-xs">
                  {use.rendered_prose ?? "Kein Text gespeichert."}
                </pre>
                <ul className="mt-3 space-y-1 text-xs">
                  {use.citations.map((citation) => (
                    <li key={citation.citation} className="flex justify-between gap-3">
                      <span className="font-mono">{citation.citation}</span>
                      <span className="text-neutral-600">{sourceStatusLabel(citation.source_status)}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      {artifacts.length > 0 && (
        <section className="mt-8">
          <h2 className="text-base font-semibold">Exportierte Pakete</h2>
          <ul className="mt-3 divide-y divide-neutral-200 rounded border border-neutral-200 px-4">
            {artifacts.map((artifact) => (
              <li key={artifact.id} className="flex items-center justify-between py-3 text-sm">
                <span>
                  Paket v{artifact.version} · {artifact.created_at.slice(0, 10)}
                </span>
                <Link
                  href={`/mandates/${id}/artifacts/${artifact.id}/download`}
                  className="text-blue-700 underline"
                >
                  Herunterladen
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
