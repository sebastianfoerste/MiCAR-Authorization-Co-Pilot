import Link from "next/link";
import type { ReactNode } from "react";

import { BackendError, backendJSON, type UserOut } from "@/lib/backend";

type AnchorSourceOut = {
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
  review_note: string | null;
  body: string | null;
  body_char_count: number;
};

type PageProps = { params: Promise<{ id: string }> };

function canCurate(user: UserOut | null): boolean {
  return user?.role === "curator" || user?.role === "admin";
}

function authorityLabel(authority: string): string {
  if (authority === "eu_regulation") return "EU-Verordnung";
  if (authority === "eu_directive") return "EU-Richtlinie";
  if (authority === "esma") return "ESMA";
  if (authority === "eba") return "EBA";
  if (authority === "eba_esma") return "EBA / ESMA";
  if (authority === "bafin") return "BaFin";
  if (authority === "national_law") return "Nationales Recht";
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

function dateTimeLabel(value: string | null): string {
  if (!value) return "Keine Angabe";
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded border border-neutral-200 bg-white p-3">
      <dt className="text-xs uppercase tracking-wide text-neutral-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-neutral-900">{value || "Keine Angabe"}</dd>
    </div>
  );
}

export default async function AnchorSourcePage({ params }: PageProps) {
  const { id } = await params;
  let user: UserOut | null = null;
  let source: AnchorSourceOut | null = null;
  let error: string | null = null;

  try {
    user = await backendJSON<UserOut>("/me");
    if (!canCurate(user)) {
      error = "Die Quellenprüfung ist Kuratoren und Administratoren vorbehalten.";
    } else {
      source = await backendJSON<AnchorSourceOut>(`/anchors/${id}/source`);
    }
  } catch (e) {
    if (e instanceof BackendError && e.status === 404) {
      error = "Quelle nicht gefunden.";
    } else {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="border-b border-neutral-200 pb-4">
        <Link href="/anchors" className="text-sm text-neutral-600 underline">
          Zurück zur Anchor-Bibliothek
        </Link>
        <h1 className="mt-3 text-xl font-semibold tracking-tight">Quellenprüfung</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Volltext, Fingerprint und Review-Metadaten für amtliche Quellen.
        </p>
      </header>

      {error && (
        <div className="mt-6 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          {error}
        </div>
      )}

      {source && (
        <article className="mt-6 space-y-6">
          <section className="rounded border border-neutral-200 bg-neutral-50 p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-neutral-500">
                  {authorityLabel(source.authority)} · {source.level.replace("_", " ")}
                </p>
                <h2 className="mt-1 font-mono text-base font-semibold">
                  {source.citation_canonical}
                </h2>
              </div>
              <span
                className={`inline-flex rounded px-2 py-0.5 text-xs ${sourceStatusClasses(source.source_status)}`}
              >
                {sourceStatusLabel(source.source_status)}
              </span>
            </div>
            {source.binding_force_note && (
              <p className="mt-3 text-sm italic text-neutral-600">{source.binding_force_note}</p>
            )}
          </section>

          <dl className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="Fassung" value={source.version} />
            <Field label="Zeichen im Quellentext" value={source.body_char_count.toLocaleString("de-DE")} />
            <Field label="Abruf" value={dateTimeLabel(source.source_retrieved_at)} />
            <Field label="Review" value={dateTimeLabel(source.reviewed_at)} />
            <Field
              label="URL"
              value={
                source.url ? (
                  <a href={source.url} target="_blank" rel="noreferrer" className="text-blue-700 underline">
                    {source.url}
                  </a>
                ) : null
              }
            />
            <Field
              label="Fingerprint"
              value={
                source.source_fingerprint ? (
                  <span className="font-mono text-xs">{source.source_fingerprint}</span>
                ) : null
              }
            />
          </dl>

          {source.review_note && (
            <section className="rounded border border-green-200 bg-green-50 p-4">
              <h2 className="text-sm font-semibold text-green-950">Review-Notiz</h2>
              <p className="mt-1 text-sm text-green-900">{source.review_note}</p>
            </section>
          )}

          <section>
            <h2 className="text-sm font-semibold text-neutral-900">Amtlicher Quellentext</h2>
            {source.body ? (
              <pre className="mt-2 max-h-[42rem] overflow-auto whitespace-pre-wrap rounded border border-neutral-200 bg-white p-4 text-sm leading-6 text-neutral-900">
                {source.body}
              </pre>
            ) : (
              <p className="mt-2 rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                Für diesen Anchor ist noch kein amtlicher Quellentext gespeichert.
              </p>
            )}
          </section>
        </article>
      )}
    </main>
  );
}
