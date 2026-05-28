import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const backendDir = path.resolve(__dirname, "../../backend");
const databaseUrl =
  process.env.DATABASE_URL ?? "postgresql+psycopg://micar:micar@localhost:5433/micar";
// This reserved account is removed before and after every test that may provision it.
const testEmail = "browser-e2e@example.com";
const jointGuidelineCitation = "EBA/ESMA, Browserprüfung gemeinsamer MiCAR-Leitlinien";

function runDatabaseStep(script: string, argument = testEmail): void {
  execFileSync("uv", ["run", "python", "-c", script, argument], {
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

function removeTestAnchor(): void {
  runDatabaseStep(
    `
import sys
from sqlalchemy import delete
from micar.models import Anchor, session_scope
with session_scope() as session:
    session.execute(delete(Anchor).where(Anchor.citation_canonical == sys.argv[1]))
`,
    jointGuidelineCitation,
  );
}

function insertTestAnchor(): void {
  runDatabaseStep(
    `
import sys
from datetime import UTC, datetime
from micar.models import Anchor, AnchorAuthority, AnchorLevel, SourceStatus, session_scope
with session_scope() as session:
    session.add(Anchor(
        level=AnchorLevel.LEVEL_3.value,
        authority=AnchorAuthority.EBA_ESMA.value,
        citation_canonical=sys.argv[1],
        url="https://www.eba.europa.eu/",
        version="browser-fixture",
        body="Amtlicher Testquellentext für die Browserprüfung. " * 20,
        binding_force_note="Level 3: Gemeinsame EBA/ESMA-Leitlinie.",
        source_fingerprint="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        source_retrieved_at=datetime(2026, 5, 28, 9, 0, tzinfo=UTC),
        source_status=SourceStatus.FETCHED_UNVERIFIED.value,
    ))
`,
    jointGuidelineCitation,
  );
}

async function signIn(page: Page, email: string): Promise<void> {
  await page.goto("/sign-in");
  await page.getByPlaceholder("dev@example.com").fill(email);
  await page.getByRole("button", { name: "Anmelden (Dev)" }).click();
  await expect(page).toHaveURL(/\/mandates$/);
}

test.beforeEach(() => {
  removeTestUser();
  removeTestAnchor();
});

test.afterEach(() => {
  removeTestUser();
  removeTestAnchor();
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

test("labels fetched joint EBA and ESMA sources in the anchor library", async ({ page }) => {
  await signIn(page, testEmail);
  insertTestAnchor();

  await page.goto("/anchors?authority=eba_esma&source_status=fetched_unverified");

  const item = page.getByRole("listitem").filter({ hasText: jointGuidelineCitation });
  await expect(item).toContainText("EBA / ESMA · level 3");
  await expect(item).toContainText("Text geladen, Prüfung ausstehend");
  await expect(item).toContainText("Fingerprint: abcdef123456...34567890");
  await expect(item).toContainText("Abruf:");
});
