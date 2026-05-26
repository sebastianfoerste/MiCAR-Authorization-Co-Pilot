import { signIn } from "../../../../auth";

export default function SignInPage() {
  const devEnabled = process.env.DEV_AUTH === "true";
  const resendEnabled = !!process.env.RESEND_API_KEY;

  async function devSubmit(formData: FormData) {
    "use server";
    const email = String(formData.get("email") ?? "");
    await signIn("dev", { email, redirectTo: "/mandates" });
  }

  async function magicSubmit(formData: FormData) {
    "use server";
    const email = String(formData.get("email") ?? "");
    await signIn("resend", { email, redirectTo: "/mandates" });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">MiCAR Authorization Co-Pilot</h1>
      <p className="mt-2 text-sm text-neutral-600">
        Internes Werkzeug. Zugang über E-Mail-Adresse aus dem Allowlist-Eintrag der Kanzlei.
      </p>

      {resendEnabled && (
        <form action={magicSubmit} className="mt-8 space-y-3">
          <label className="block text-sm font-medium">E-Mail (Magic-Link)</label>
          <input
            type="email"
            name="email"
            required
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
            placeholder="vorname.nachname@gunnercooke.com"
          />
          <button
            type="submit"
            className="w-full rounded bg-neutral-900 px-3 py-2 text-sm font-medium text-white"
          >
            Link senden
          </button>
        </form>
      )}

      {devEnabled && (
        <form action={devSubmit} className="mt-8 space-y-3 border-t border-neutral-200 pt-6">
          <label className="block text-sm font-medium">Dev-Sign-in</label>
          <p className="text-xs text-neutral-500">
            DEV_AUTH=true: keine E-Mail-Verifikation. Nur für lokale Entwicklung.
          </p>
          <input
            type="email"
            name="email"
            required
            className="w-full rounded border border-neutral-300 px-3 py-2 text-sm"
            placeholder="dev@example.com"
          />
          <button
            type="submit"
            className="w-full rounded border border-neutral-900 px-3 py-2 text-sm font-medium"
          >
            Anmelden (Dev)
          </button>
        </form>
      )}

      {!devEnabled && !resendEnabled && (
        <p className="mt-8 rounded border border-amber-300 bg-amber-50 p-4 text-sm">
          Kein Auth-Provider konfiguriert. Setze DEV_AUTH=true oder RESEND_API_KEY in
          frontend/.env.local.
        </p>
      )}
    </main>
  );
}
