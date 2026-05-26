import Link from "next/link";
import { revalidatePath } from "next/cache";

import { backendFetch, backendJSON, type UserOut } from "@/lib/backend";

type AnchorOut = {
  id: number;
  level: string;
  authority: string;
  citation_canonical: string;
  url: string | null;
  version: string;
  effective_from: string | null;
  effective_to: string | null;
  title_or_excerpt: string | null;
  binding_force_note: string | null;
  source_fingerprint: string | null;
  source_status: string;
  source_retrieved_at: string | null;
  reviewed_at: string | null;
};

type AnchorListOut = { items: AnchorOut[]; total: number };

type AnchorChangeOut = {
  id: number;
  anchor_id_new: number | null;
  kind: string;
  detected_at: string;
  source_url: string | null;
  summary: string | null;
  triage_status: string;
};

type SearchParams = Promise<{ q?: string; level?: string; authority?: string; source_status?: string }>;

const LEVELS = [
  { value: "", label: "Alle Level" },
  { value: "level_1", label: "Level 1 (Verordnung / Richtlinie)" },
  { value: "level_2", label: "Level 2 (RTS / ITS / Delegierter RA)" },
  { value: "level_3", label: "Level 3 (ESMA / EBA / BaFin)" },
];

const AUTHORITIES = [
  { value: "", label: "Alle Quellen" },
  { value: "eu_regulation", label: "EU-Verordnung" },
  { value: "eu_directive", label: "EU-Richtlinie" },
  { value: "esma", label: "ESMA" },
  { value: "eba", label: "EBA" },
  { value: "bafin", label: "BaFin" },
  { value: "national_law", label: "Nationales Recht" },
];

const SOURCE_STATUSES = [
  { value: "", label: "Alle Prüfstände" },
  { value: "seed_unverified", label: "Seed, nicht geprüft" },
  { value: "fetched_unverified", label: "Text geladen, Prüfung offen" },
  { value: "verified", label: "Quelle geprüft" },
  { value: "rejected", label: "Quelle zurückgewiesen" },
];

function authorityBadge(authority: string): string {
  if (authority.startsWith("eu_")) return "EU";
  if (authority === "esma") return "ESMA";
  if (authority === "eba") return "EBA";
  if (authority === "bafin") return "BaFin";
  return authority;
}

function sourceStatusLabel(status: string): string {
  if (status === "verified") return "Quelle geprüft";
  if (status === "fetched_unverified") return "Text geladen, Prüfung ausstehend";
  if (status === "rejected") return "Quelle zurückgewiesen";
  return "Seed, nicht geprüft";
}

function sourceStatusClasses(status: string): string {
  if (status === "verified") return "bg-green-50 text-green-800";
  if (status === "rejected") return "bg-red-50 text-red-800";
  return "bg-amber-50 text-amber-900";
}

export default async function AnchorsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const params = await searchParams;
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.level) query.set("level", params.level);
  if (params.authority) query.set("authority", params.authority);
  if (params.source_status) query.set("source_status", params.source_status);
  query.set("limit", "200");

  let user: UserOut | null = null;
  let data: AnchorListOut = { items: [], total: 0 };
  let changes: AnchorChangeOut[] = [];
  let error: string | null = null;
  try {
    user = await backendJSON<UserOut>("/me");
    data = await backendJSON<AnchorListOut>(`/anchors?${query.toString()}`);
    if (user.role === "curator" || user.role === "admin") {
      changes = await backendJSON<AnchorChangeOut[]>("/anchors/changes");
    }
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  async function verifySource(formData: FormData) {
    "use server";
    const anchorId = String(formData.get("anchor_id"));
    const fingerprint = String(formData.get("fingerprint"));
    await backendFetch(`/anchors/${anchorId}/verify`, {
      method: "POST",
      body: JSON.stringify({ expected_fingerprint: fingerprint }),
    });
    revalidatePath("/anchors");
  }

  async function loadSupplementarySource(formData: FormData) {
    "use server";
    const anchorId = String(formData.get("anchor_id"));
    await backendFetch(`/anchors/${anchorId}/source-text`, {
      method: "POST",
      body: JSON.stringify({
        source_url: String(formData.get("source_url") ?? "").trim(),
        version: String(formData.get("version") ?? "").trim(),
        source_text: String(formData.get("source_text") ?? "").trim(),
      }),
    });
    revalidatePath("/anchors");
  }

  async function rejectChange(formData: FormData) {
    "use server";
    const changeId = String(formData.get("change_id"));
    await backendFetch(`/anchors/changes/${changeId}/triage`, {
      method: "POST",
      body: JSON.stringify({ decision: "rejected" }),
    });
    revalidatePath("/anchors");
  }

  const canCurate = user?.role === "curator" || user?.role === "admin";

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="border-b border-neutral-200 pb-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Anchor-Bibliothek</h1>
            <p className="text-sm text-neutral-600">
              {data.total} Einträge · Offizielle Texte werden erst nach dokumentierter
              Prüfung für externe Synthese freigegeben.
            </p>
          </div>
          <Link href="/mandates" className="text-sm text-neutral-600 underline">
            Mandate
          </Link>
        </div>
      </header>

      {canCurate && changes.length > 0 && (
        <section className="mt-6 rounded border border-amber-300 bg-amber-50 p-4">
          <h2 className="text-sm font-semibold text-amber-950">Offene Quellenänderungen</h2>
          <p className="mt-1 text-xs text-amber-900">
            Eine Änderung wird durch Verifikation des zugehörigen Anchors freigegeben.
            Zurückweisung sperrt die Quelle.
          </p>
          <ul className="mt-3 divide-y divide-amber-200">
            {changes.map((change) => (
              <li key={change.id} className="flex items-center justify-between gap-4 py-2 text-xs">
                <span>
                  Änderung {change.id} · Anchor {change.anchor_id_new ?? "keine Angabe"} ·{" "}
                  {change.kind}
                </span>
                <form action={rejectChange}>
                  <input type="hidden" name="change_id" value={change.id} />
                  <button type="submit" className="rounded border border-amber-800 px-2 py-1">
                    Zurückweisen
                  </button>
                </form>
              </li>
            ))}
          </ul>
        </section>
      )}

      <form method="get" className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-5">
        <input
          name="q"
          defaultValue={params.q ?? ""}
          placeholder="Volltext (Zitat oder Body)…"
          className="sm:col-span-2 rounded border border-neutral-300 px-3 py-2 text-sm"
        />
        <select
          name="level"
          defaultValue={params.level ?? ""}
          className="rounded border border-neutral-300 px-3 py-2 text-sm"
        >
          {LEVELS.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
        <select
          name="authority"
          defaultValue={params.authority ?? ""}
          className="rounded border border-neutral-300 px-3 py-2 text-sm"
        >
          {AUTHORITIES.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
        <select
          name="source_status"
          defaultValue={params.source_status ?? ""}
          className="rounded border border-neutral-300 px-3 py-2 text-sm"
        >
          {SOURCE_STATUSES.map((status) => (
            <option key={status.value} value={status.value}>
              {status.label}
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="sm:col-span-5 sm:w-auto sm:justify-self-start rounded bg-neutral-900 px-4 py-2 text-sm text-white"
        >
          Filtern
        </button>
      </form>

      {error && (
        <div className="mt-6 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          Backend nicht erreichbar: <code>{error}</code>
        </div>
      )}

      <ul className="mt-6 divide-y divide-neutral-200">
        {data.items.map((a) => (
          <li key={a.id} className="py-3">
            <div className="flex items-baseline justify-between gap-3">
              <div>
                <span className="text-xs uppercase tracking-wider text-neutral-500">
                  {authorityBadge(a.authority)} · {a.level.replace("_", " ")}
                </span>
                <div className="font-mono text-sm">{a.citation_canonical}</div>
                <span
                  className={`mt-1 inline-block rounded px-2 py-0.5 text-xs ${sourceStatusClasses(a.source_status)}`}
                >
                  {sourceStatusLabel(a.source_status)}
                </span>
              </div>
              {a.url && (
                <a
                  href={a.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-blue-700 underline"
                >
                  Quelle ↗
                </a>
              )}
            </div>
            {a.title_or_excerpt && (
              <p className="mt-1 text-sm text-neutral-700">{a.title_or_excerpt}</p>
            )}
            {a.binding_force_note && (
              <p className="mt-1 text-xs italic text-neutral-500">{a.binding_force_note}</p>
            )}
            {canCurate && a.source_status === "fetched_unverified" && a.source_fingerprint && (
              <form action={verifySource} className="mt-2">
                <input type="hidden" name="anchor_id" value={a.id} />
                <input type="hidden" name="fingerprint" value={a.source_fingerprint} />
                <button
                  type="submit"
                  className="rounded border border-green-700 px-2 py-1 text-xs text-green-800"
                >
                  Fingerprint prüfen und freigeben
                </button>
              </form>
            )}
            {canCurate && !a.authority.startsWith("eu_") && (
              <details className="mt-2 text-xs">
                <summary className="cursor-pointer text-blue-700">
                  Öffentlichen Quellentext laden
                </summary>
                <form action={loadSupplementarySource} className="mt-2 space-y-2 rounded bg-neutral-50 p-3">
                  <input type="hidden" name="anchor_id" value={a.id} />
                  <input
                    required
                    type="url"
                    name="source_url"
                    defaultValue={a.url ?? ""}
                    placeholder="https://..."
                    className="block w-full rounded border border-neutral-300 px-2 py-1"
                  />
                  <input
                    required
                    name="version"
                    defaultValue={a.version === "unverified" ? "" : a.version}
                    placeholder="Fassung oder Abrufdatum"
                    className="block w-full rounded border border-neutral-300 px-2 py-1"
                  />
                  <textarea
                    required
                    name="source_text"
                    rows={5}
                    placeholder="Öffentlichen amtlichen Quellentext einfügen"
                    className="block w-full rounded border border-neutral-300 px-2 py-1"
                  />
                  <button type="submit" className="rounded bg-neutral-900 px-2 py-1 text-white">
                    Als prüfbedürftige Quelle speichern
                  </button>
                </form>
              </details>
            )}
          </li>
        ))}
        {!error && data.items.length === 0 && (
          <li className="py-10 text-center text-sm text-neutral-500">
            Keine Treffer. Hast du das Seed schon geladen? <code>uv run python -m micar.anchors.ingest seed</code>
          </li>
        )}
      </ul>
    </main>
  );
}
