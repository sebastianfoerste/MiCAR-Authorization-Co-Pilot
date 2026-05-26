import Link from "next/link";
import { revalidatePath } from "next/cache";

import { backendFetch, backendJSON } from "@/lib/backend";
import type { MandateOut, SectionOut } from "@/lib/types";

type JSONSchema = {
  type?: string;
  properties?: Record<string, JSONSchemaProperty>;
  required?: string[];
  $defs?: Record<string, JSONSchema>;
};

type JSONSchemaProperty = {
  type?: string | string[];
  title?: string;
  description?: string;
  enum?: string[];
  items?: JSONSchemaProperty;
  format?: string;
  minimum?: number;
  maximum?: number;
};

function inputForProperty(
  name: string,
  prop: JSONSchemaProperty,
  required: boolean,
  current: unknown,
) {
  const types = Array.isArray(prop.type) ? prop.type : [prop.type ?? "string"];
  const isOptional = types.includes("null");
  const primary = types.find((t) => t !== "null") ?? "string";
  const baseClasses =
    "mt-1 w-full rounded border border-neutral-300 px-3 py-2 text-sm";

  if (primary === "boolean") {
    return (
      <label className="flex items-start gap-2">
        <input
          type="checkbox"
          name={name}
          defaultChecked={current === true}
          className="mt-1"
        />
        <span className="text-sm">
          {prop.title ?? name}
          {required && !isOptional && " *"}
          {prop.description && (
            <span className="block text-xs text-neutral-500">{prop.description}</span>
          )}
        </span>
      </label>
    );
  }

  if (primary === "array") {
    // Comma-separated entry — adequate for Phase 2; richer UI later.
    const val = Array.isArray(current) ? current.join(", ") : "";
    return (
      <label className="block">
        <span className="text-sm font-medium">
          {prop.title ?? name}
          {required && !isOptional && " *"}
        </span>
        <input
          name={name}
          defaultValue={val}
          data-shape="array"
          className={baseClasses}
          placeholder="komma-getrennt"
        />
        {prop.description && (
          <span className="mt-1 block text-xs text-neutral-500">{prop.description}</span>
        )}
      </label>
    );
  }

  if (prop.enum) {
    return (
      <label className="block">
        <span className="text-sm font-medium">
          {prop.title ?? name}
          {required && !isOptional && " *"}
        </span>
        <select name={name} defaultValue={(current as string) ?? ""} className={baseClasses}>
          {!required && <option value="">Keine Auswahl</option>}
          {prop.enum.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </label>
    );
  }

  const inputType =
    primary === "integer" || primary === "number"
      ? "number"
      : prop.format === "date"
        ? "date"
        : prop.format === "email"
          ? "email"
          : "text";

  return (
    <label className="block">
      <span className="text-sm font-medium">
        {prop.title ?? name}
        {required && !isOptional && " *"}
      </span>
      <input
        name={name}
        type={inputType}
        defaultValue={(current as string | number | undefined)?.toString() ?? ""}
        data-shape={primary}
        className={baseClasses}
      />
      {prop.description && (
        <span className="mt-1 block text-xs text-neutral-500">{prop.description}</span>
      )}
    </label>
  );
}

function parseFormData(schema: JSONSchema, formData: FormData): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [name, prop] of Object.entries(schema.properties ?? {})) {
    const types = Array.isArray(prop.type) ? prop.type : [prop.type ?? "string"];
    const primary = types.find((t) => t !== "null") ?? "string";
    const raw = formData.get(name);
    if (primary === "boolean") {
      out[name] = raw === "on";
      continue;
    }
    if (primary === "array") {
      const s = String(raw ?? "").trim();
      out[name] = s ? s.split(",").map((x) => x.trim()).filter(Boolean) : [];
      continue;
    }
    if (raw === null || raw === "") {
      // optional field left blank
      if (types.includes("null")) out[name] = null;
      continue;
    }
    if (primary === "integer" || primary === "number") {
      const n = Number(raw);
      out[name] = Number.isNaN(n) ? null : n;
      continue;
    }
    out[name] = String(raw);
  }
  return out;
}

export default async function SectionEditor({
  params,
}: {
  params: Promise<{ id: string; key: string }>;
}) {
  const { id, key } = await params;
  let mandate: MandateOut | null = null;
  let section: SectionOut | null = null;
  let schema: JSONSchema | null = null;
  let error: string | null = null;
  try {
    mandate = await backendJSON<MandateOut>(`/mandates/${id}`);
    schema = await backendJSON<JSONSchema>(`/mandates/${id}/intake/${key}/schema`);
    section = await backendJSON<SectionOut>(`/mandates/${id}/intake/${key}`);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  async function save(formData: FormData) {
    "use server";
    const liveSchema = await backendJSON<JSONSchema>(`/mandates/${id}/intake/${key}/schema`);
    const answers = parseFormData(liveSchema, formData);
    await backendFetch(`/mandates/${id}/intake/${key}`, {
      method: "PUT",
      body: JSON.stringify({ answers }),
    });
    revalidatePath(`/mandates/${id}/intake/${key}`);
    revalidatePath(`/mandates/${id}/intake`);
  }

  if (error || !mandate || !schema) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Link href={`/mandates/${id}/intake`} className="text-sm text-neutral-600 underline">
          ← Intake
        </Link>
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          {error ?? "Sektion nicht gefunden."}
        </div>
      </main>
    );
  }

  const required = new Set(schema.required ?? []);
  const props = schema.properties ?? {};
  const current = section?.answers ?? {};

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <Link href={`/mandates/${id}/intake`} className="text-sm text-neutral-600 underline">
        ← Intake
      </Link>

      <header className="mt-2 border-b border-neutral-200 pb-4">
        <h1 className="text-xl font-semibold tracking-tight">{key}</h1>
        <p className="text-sm text-neutral-600">
          {mandate.name} · {section?.is_complete ? "vollständig" : "in Bearbeitung"}
        </p>
      </header>

      {section && section.errors.length > 0 && (
        <div className="mt-4 rounded border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
          <strong>Validierungsmeldungen:</strong>
          <ul className="mt-1 list-disc pl-5">
            {section.errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <form action={save} className="mt-6 space-y-4">
        {Object.entries(props).map(([name, prop]) => (
          <div key={name}>{inputForProperty(name, prop, required.has(name), current[name])}</div>
        ))}
        <button
          type="submit"
          className="mt-4 rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white"
        >
          Speichern
        </button>
      </form>
    </main>
  );
}
