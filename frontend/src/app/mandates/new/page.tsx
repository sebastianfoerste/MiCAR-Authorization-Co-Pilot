import { redirect } from "next/navigation";

import { backendFetch, backendJSON } from "@/lib/backend";
import type { MandateOut, TrackOut } from "@/lib/types";

async function create(formData: FormData) {
  "use server";
  const payload = {
    name: String(formData.get("name") ?? "").trim(),
    client_label: (formData.get("client_label") as string)?.trim() || null,
    track: String(formData.get("track") ?? ""),
    target_filing_date: (formData.get("target_filing_date") as string) || null,
    redact_client_identifiers: formData.get("redact_client_identifiers") === "on",
  };
  const res = await backendFetch("/mandates", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const m = (await res.json()) as MandateOut;
  redirect(`/mandates/${m.id}`);
}

export default async function NewMandatePage() {
  let tracks: TrackOut[] = [];
  let error: string | null = null;
  try {
    tracks = await backendJSON<TrackOut[]>("/mandates/tracks");
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-xl font-semibold tracking-tight">Neues Mandat</h1>
      <p className="mt-1 text-sm text-neutral-600">
        Pflichtfelder mit *. Track entscheidet das Schema und das Template-Set.
      </p>

      {error && (
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          Backend: <code>{error}</code>
        </div>
      )}

      <form action={create} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium">Mandatsname *</span>
          <input
            name="name"
            required
            className="mt-1 w-full rounded border border-neutral-300 px-3 py-2 text-sm"
            placeholder="z. B. Project Cobalt, CASP-Antrag"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium">Mandanten-Label (intern)</span>
          <input
            name="client_label"
            className="mt-1 w-full rounded border border-neutral-300 px-3 py-2 text-sm"
            placeholder="z. B. Cobalt Holdings B.V."
          />
          <p className="mt-1 text-xs text-neutral-500">
            Wird in LLM-Aufrufen je nach Redaktionsmodus durch Platzhalter ersetzt.
          </p>
        </label>

        <label className="block">
          <span className="text-sm font-medium">Track *</span>
          <select
            name="track"
            required
            className="mt-1 w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          >
            {tracks.map((t) => (
              <option key={t.code} value={t.code}>
                {t.label_de}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium">Anvisiertes Einreichungsdatum</span>
          <input
            type="date"
            name="target_filing_date"
            className="mt-1 w-full rounded border border-neutral-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            name="redact_client_identifiers"
            defaultChecked
            className="mt-1"
          />
          <span className="text-sm">
            Mandanten-Identifikatoren vor LLM-Aufrufen durch Platzhalter ersetzen
            (BRAO § 43e / § 203 StGB)
          </span>
        </label>

        <button
          type="submit"
          className="mt-4 rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white"
        >
          Mandat anlegen
        </button>
      </form>
    </main>
  );
}
