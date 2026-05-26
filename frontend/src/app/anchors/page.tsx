import Link from "next/link";

import { backendJSON } from "@/lib/backend";

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

type SearchParams = Promise<{ q?: string; level?: string; authority?: string }>;

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
  query.set("limit", "200");

  let data: AnchorListOut = { items: [], total: 0 };
  let error: string | null = null;
  try {
    data = await backendJSON<AnchorListOut>(`/anchors?${query.toString()}`);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

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

      <form method="get" className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-4">
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
        <button
          type="submit"
          className="sm:col-span-4 sm:w-auto sm:justify-self-start rounded bg-neutral-900 px-4 py-2 text-sm text-white"
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
