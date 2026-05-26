/**
 * Auth.js v5 configuration.
 *
 * Phase 0 ships two providers:
 *   - Credentials (dev): when DEV_AUTH=true, type an email to sign in. No
 *     verification. Strictly for local boot.
 *   - Resend (production magic-link): activated when RESEND_API_KEY is set.
 *     Requires a database adapter to be wired in v2.
 *
 * Session strategy is JWT — we mint a separate HS256 token in
 * `src/lib/backend.ts` to call the FastAPI backend.
 */
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Resend from "next-auth/providers/resend";

const devAuthEnabled = process.env.DEV_AUTH === "true";
const resendKey = process.env.RESEND_API_KEY;

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    ...(devAuthEnabled
      ? [
          Credentials({
            id: "dev",
            name: "Dev sign-in",
            credentials: {
              email: { label: "Email", type: "email" },
            },
            authorize: async (credentials) => {
              const email = credentials?.email;
              if (typeof email !== "string" || !email.includes("@")) return null;
              return { id: email, email, name: email.split("@")[0] };
            },
          }),
        ]
      : []),
    ...(resendKey
      ? [
          Resend({
            apiKey: resendKey,
            from: process.env.EMAIL_FROM ?? "noreply@localhost",
          }),
        ]
      : []),
  ],
  session: { strategy: "jwt" },
  pages: { signIn: "/sign-in" },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.email = user.email;
        token.name = user.name ?? null;
      }
      return token;
    },
    async session({ session, token }) {
      if (token.email) session.user = { ...session.user, email: token.email as string };
      if (token.name) session.user = { ...session.user, name: token.name as string };
      return session;
    },
  },
});
