import Link from "next/link";
import { revalidatePath } from "next/cache";

import { backendFetch, backendJSON } from "@/lib/backend";
import type { MandateOut } from "@/lib/types";

type AgentRunOut = {
  id: number;
  mandate_id: number | null;
  agent_key: string;
  status: string;
  trigger: string;
  result_summary: string | null;
  created_at: string;
  completed_at: string | null;
  finding_count: number;
  action_count: number;
};

type AgentStepOut = {
  id: number;
  step_key: string;
  status: string;
  input_summary: string | null;
  output: Record<string, unknown> | null;
  created_at: string;
};

type AgentFindingOut = {
  id: number;
  severity: string;
  title: string;
  body: string;
  evidence: Record<string, unknown> | null;
  status: string;
  created_at: string;
};

type AgentActionOut = {
  id: number;
  action_type: string;
  status: string;
  title: string;
  payload: Record<string, unknown> | null;
  created_at: string;
  decided_by: number | null;
  decided_at: string | null;
  decision_note: string | null;
};

type AgentRunDetailOut = {
  run: AgentRunOut;
  steps: AgentStepOut[];
  findings: AgentFindingOut[];
  actions: AgentActionOut[];
};

type PageProps = { params: Promise<{ id: string; runId: string }> };

function severityClasses(severity: string): string {
  if (severity === "high") return "bg-red-50 text-red-800";
  if (severity === "medium") return "bg-amber-50 text-amber-900";
  return "bg-blue-50 text-blue-800";
}

function actionStatusLabel(status: string): string {
  if (status === "approved") return "angenommen";
  if (status === "rejected") return "abgelehnt";
  return "vorgeschlagen";
}

function formatJson(value: Record<string, unknown> | null): string {
  if (!value) return "Keine strukturierten Daten.";
  return JSON.stringify(value, null, 2);
}

export default async function AgentRunPage({ params }: PageProps) {
  const { id, runId } = await params;
  let mandate: MandateOut | null = null;
  let detail: AgentRunDetailOut | null = null;
  let error: string | null = null;

  try {
    mandate = await backendJSON<MandateOut>(`/mandates/${id}`);
    detail = await backendJSON<AgentRunDetailOut>(`/mandates/${id}/agent-runs/${runId}`);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  async function decideAction(formData: FormData) {
    "use server";
    const actionId = String(formData.get("action_id"));
    const decision = String(formData.get("decision"));
    const reviewNote = String(formData.get("review_note") ?? "").trim();
    await backendFetch(`/mandates/${id}/agent-actions/${actionId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, review_note: reviewNote }),
    });
    revalidatePath(`/mandates/${id}/agent-runs/${runId}`);
    revalidatePath(`/mandates/${id}`);
  }

  if (error || !mandate || !detail) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-10">
        <Link href={`/mandates/${id}`} className="text-sm text-neutral-600 underline">
          Zurück zum Mandat
        </Link>
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          {error ?? "Agentenlauf nicht gefunden."}
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <Link href={`/mandates/${id}`} className="text-sm text-neutral-600 underline">
        Zurück zum Mandat
      </Link>

      <header className="mt-2 border-b border-neutral-200 pb-4">
        <p className="text-xs uppercase tracking-wider text-neutral-500">{mandate.name}</p>
        <h1 className="text-xl font-semibold tracking-tight">Agentenlauf</h1>
        <p className="mt-1 text-sm text-neutral-600">
          {detail.run.agent_key} · {detail.run.status} · {detail.run.created_at.slice(0, 16).replace("T", " ")}
        </p>
        <p className="mt-2 text-sm text-neutral-700">{detail.run.result_summary ?? "Keine Zusammenfassung."}</p>
      </header>

      <section className="mt-6 rounded border border-neutral-200 bg-white p-4">
        <h2 className="text-base font-semibold">Findings</h2>
        {detail.findings.length > 0 ? (
          <ul className="mt-3 space-y-3">
            {detail.findings.map((finding) => (
              <li key={finding.id} className="rounded border border-neutral-200 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-medium">{finding.title}</h3>
                    <p className="mt-1 text-sm text-neutral-700">{finding.body}</p>
                  </div>
                  <span className={`rounded px-2 py-0.5 text-xs ${severityClasses(finding.severity)}`}>
                    {finding.severity}
                  </span>
                </div>
                {finding.evidence && (
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer text-blue-700">Evidenz anzeigen</summary>
                    <pre className="mt-2 overflow-auto rounded bg-neutral-50 p-2">
                      {formatJson(finding.evidence)}
                    </pre>
                  </details>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 rounded border border-dashed border-neutral-300 p-4 text-sm text-neutral-500">
            Keine Findings in diesem Lauf.
          </p>
        )}
      </section>

      <section className="mt-6 rounded border border-neutral-200 bg-white p-4">
        <h2 className="text-base font-semibold">Vorschläge</h2>
        {detail.actions.length > 0 ? (
          <ul className="mt-3 space-y-3">
            {detail.actions.map((action) => (
              <li key={action.id} className="rounded border border-neutral-200 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-medium">{action.title}</h3>
                    <p className="mt-1 text-xs text-neutral-500">
                      {action.action_type} · {actionStatusLabel(action.status)}
                    </p>
                  </div>
                  <span className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700">
                    {actionStatusLabel(action.status)}
                  </span>
                </div>
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer text-blue-700">Payload anzeigen</summary>
                  <pre className="mt-2 overflow-auto rounded bg-neutral-50 p-2">
                    {formatJson(action.payload)}
                  </pre>
                </details>
                {action.status === "proposed" ? (
                  <form action={decideAction} className="mt-3 space-y-2 rounded bg-neutral-50 p-3">
                    <input type="hidden" name="action_id" value={action.id} />
                    <label className="block text-xs font-medium text-neutral-900">
                      Review-Notiz zur Agentenentscheidung
                      <textarea
                        required
                        minLength={20}
                        name="review_note"
                        rows={2}
                        placeholder="Entscheidung fachlich geprüft; Vorschlag wird nicht automatisch ausgeführt."
                        className="mt-1 block w-full rounded border border-neutral-300 bg-white px-2 py-1 font-normal"
                      />
                    </label>
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        name="decision"
                        value="approved"
                        className="rounded border border-green-700 px-2 py-1 text-xs text-green-800"
                      >
                        Vorschlag annehmen
                      </button>
                      <button
                        type="submit"
                        name="decision"
                        value="rejected"
                        className="rounded border border-red-700 px-2 py-1 text-xs text-red-800"
                      >
                        Vorschlag ablehnen
                      </button>
                    </div>
                  </form>
                ) : (
                  <p className="mt-3 rounded bg-neutral-50 p-2 text-xs text-neutral-600">
                    Entscheidung: {actionStatusLabel(action.status)}
                    {action.decision_note ? ` · ${action.decision_note}` : ""}
                  </p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 rounded border border-dashed border-neutral-300 p-4 text-sm text-neutral-500">
            Keine Vorschläge in diesem Lauf.
          </p>
        )}
      </section>

      <section className="mt-6 rounded border border-neutral-200 bg-white p-4">
        <h2 className="text-base font-semibold">Schritte</h2>
        <ul className="mt-3 space-y-2">
          {detail.steps.map((step) => (
            <li key={step.id} className="rounded border border-neutral-200 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{step.step_key}</span>
                <span className="text-xs text-neutral-500">{step.status}</span>
              </div>
              <p className="mt-1 text-xs text-neutral-600">{step.input_summary ?? "Keine Zusammenfassung."}</p>
              <details className="mt-2 text-xs">
                <summary className="cursor-pointer text-blue-700">Output anzeigen</summary>
                <pre className="mt-2 overflow-auto rounded bg-neutral-50 p-2">
                  {formatJson(step.output)}
                </pre>
              </details>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
