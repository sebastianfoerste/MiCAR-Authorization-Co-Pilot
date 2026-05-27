import { defineConfig } from "@playwright/test";
import path from "node:path";

const backendDir = path.resolve(__dirname, "../backend");
const browserSharedSecret = "browser-e2e-shared-secret-00000000000001";
const databaseUrl =
  process.env.DATABASE_URL ?? "postgresql+psycopg://micar:micar@localhost:5433/micar";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  outputDir: "test-results",
  use: {
    baseURL: "http://localhost:3011",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run uvicorn micar.app:app --host 127.0.0.1 --port 8091",
      cwd: backendDir,
      env: {
        ...process.env,
        ALLOW_UNRESTRICTED_DEV_AUTH: "true",
        CORS_ALLOW_ORIGINS: "http://localhost:3011",
        DATABASE_URL: databaseUrl,
        JWT_SHARED_SECRET: browserSharedSecret,
      },
      url: "http://127.0.0.1:8091/healthz",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npx next dev -p 3011",
      cwd: __dirname,
      env: {
        ...process.env,
        AUTH_SECRET: "browser-e2e-auth-secret-000000000000000001",
        BACKEND_URL: "http://127.0.0.1:8091",
        DEV_AUTH: "true",
        JWT_SHARED_SECRET: browserSharedSecret,
      },
      url: "http://localhost:3011/sign-in",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
