import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const backendDir = path.resolve(__dirname, "../../backend");
const databaseUrl =
  process.env.DATABASE_URL ?? "postgresql+psycopg://micar:micar@localhost:5433/micar";
// This reserved account is removed before and after every test that may provision it.
const testEmail = "browser-e2e@example.com";

function runDatabaseStep(script: string): void {
  execFileSync("uv", ["run", "python", "-c", script, testEmail], {
    cwd: backendDir,
    env: { ...process.env, DATABASE_URL: databaseUrl },
    stdio: "pipe",
  });
}

function removeTestUser(): void {
  runDatabaseStep(`
import sys
from sqlalchemy import delete, select
from micar.models import AuditEvent, User, session_scope
with session_scope() as session:
    user = session.execute(select(User).where(User.email == sys.argv[1])).scalar_one_or_none()
    if user is not None:
        session.execute(delete(AuditEvent).where(AuditEvent.actor_id == user.id))
        session.delete(user)
`);
}

function promoteTestUser(): void {
  runDatabaseStep(`
import sys
from sqlalchemy import select
from micar.models import User, UserRole, session_scope
with session_scope() as session:
    user = session.execute(select(User).where(User.email == sys.argv[1])).scalar_one()
    user.role = UserRole.ADMIN.value
`);
}

async function signIn(page: Page, email: string): Promise<void> {
  await page.goto("/sign-in");
  await page.getByPlaceholder("dev@example.com").fill(email);
  await page.getByRole("button", { name: "Anmelden (Dev)" }).click();
  await expect(page).toHaveURL(/\/mandates$/);
}

test.beforeEach(() => {
  removeTestUser();
});

test.afterEach(() => {
  removeTestUser();
});

test("redirects an unauthenticated visitor to sign-in", async ({ page }) => {
  await page.goto("/mandates");

  await expect(page).toHaveURL(/\/sign-in$/);
  await expect(page.getByRole("heading", { name: "MiCAR Authorization Co-Pilot" })).toBeVisible();
});

test("rejects an invalid development email claim without a server error", async ({ page }) => {
  await signIn(page, "invalid-browser@example.test");

  await expect(page.getByText('backend 401: {"detail":"invalid sub claim email"}')).toBeVisible();
  await expect(page.getByText("backend 500")).toHaveCount(0);
});

test("keeps the audit screen restricted for a lawyer account", async ({ page }) => {
  await signIn(page, testEmail);
  await expect(page.getByRole("link", { name: "Audit-Protokoll" })).toHaveCount(0);

  await page.goto("/audit");
  await expect(page.getByText("Das Audit-Protokoll ist Administratoren vorbehalten.")).toBeVisible();
});

test("shows redacted audit events to an administrator", async ({ page }) => {
  await signIn(page, testEmail);
  promoteTestUser();

  await page.goto("/mandates");
  await page.getByRole("link", { name: "Audit-Protokoll" }).click();
  await expect(page).toHaveURL(/\/audit$/);

  const table = page.getByRole("table");
  await expect(table.getByText("user.provisioned")).toBeVisible();
  await expect(table.getByText('"user_id"')).toBeVisible();
  await expect(table).not.toContainText(testEmail);
});
