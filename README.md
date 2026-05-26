# MiCAR Authorization Co-Pilot

Internal prototype for producing review-gated MiCAR authorisation drafting
materials. The present implementation supports CASP, asset-referenced token
(ART) and e-money token (EMT) intake workflows with structural draft templates
for all documents declared in the three track catalogues.

The application does not certify current BaFin practice and does not produce a
filing-ready application without lawyer review. Regulatory text must be fetched
from an official source and approved in the anchor library before any external
model synthesis can run.

For scope, current limits and the next implementation stages, see
[`docs/PLAN.md`](docs/PLAN.md).

## Stack

- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic and Postgres 16.
- Frontend: Next.js 15 App Router, React 19, strict TypeScript and Auth.js v5.
- Drafting: local deterministic stub mode by default; Anthropic integration behind explicit controls.

## Quick Start

```bash
make install
make install-frontend
make db-up

cp .env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
# Set the same JWT_SHARED_SECRET in both files.
# Set AUTH_SECRET in frontend/.env.local.
# For a disposable local environment only, set ALLOW_UNRESTRICTED_DEV_AUTH=true
# in backend/.env, or provide USER_EMAIL_ALLOWLIST.

make migrate
cd backend && uv run python -m micar.anchors.ingest seed
cd backend && uv run python -m micar.anchors.ingest eurlex --regulation 2023/1114

make dev-backend
make dev-frontend
```

With `DEV_AUTH=true`, the local sign-in page permits development login. An
empty `USER_EMAIL_ALLOWLIST` is appropriate only for local development.
Docker exposes this project's Postgres instance on port `5433` by default;
set `MICAR_POSTGRES_PORT` and `DATABASE_URL` together to use another port.

## Safety Gates

The following controls are enforced in code:

- Login fails closed unless an email allowlist is configured or the explicit
  local-development override is enabled.
- Each mandate is accessible only to its owner or an admin user.
- Artifact downloads apply the same matter-level access check.
- An API key alone cannot activate external model processing.
- `EXTERNAL_LLM_PROCESSING_ENABLED=true` is required for outbound synthesis.
- External synthesis requires curator-verified source text for each cited anchor.
- Mandate facts are redacted before outbound processing unless
  `ALLOW_UNREDACTED_EXTERNAL_CLIENT_DATA=true` has expressly been configured.
- Changed supplementary source text creates a curator-visible review item and
  flags clauses that used the prior anchor.
- Failed citation verification prevents clause approval.
- Only the latest lawyer-approved clauses with currently verified sources can
  enter an export package.

The source workflow is:

```bash
# Create unverified pointers.
cd backend && uv run python -m micar.anchors.ingest seed

# Fetch official German MiCAR article text and fingerprints.
cd backend && uv run python -m micar.anchors.ingest eurlex --regulation 2023/1114

# A curator or admin reviews the fetched source and verifies its fingerprint
# through POST /anchors/{anchor_id}/verify.
```

ESMA, EBA and BaFin entries initially remain unverified discovery pointers.
A curator may load public official text in the anchor library UI or through
`POST /anchors/{anchor_id}/source-text`. The application calculates a source
fingerprint and places new or changed text in the pending change queue.
Verification through `POST /anchors/{anchor_id}/verify` releases that source;
rejecting a pending change marks it unavailable.

## Drafting Workflow

1. Create a mandate in the CASP, ART or EMT track.
2. Complete every fact-only intake section and mark the mandate ready for generation.
3. Generate structural drafts. Each latest document appears in the mandate review panel.
4. Verify every cited source in the anchor library. A source refresh requires renewed review.
5. Move the mandate into review and approve or reject each latest clause.
6. Create and download the package only after all displayed clauses are approved.

The templates are drafting structures. Bracketed review instructions identify
points requiring a lawyer's factual and legal completion before approval.

## Commands

```bash
make test
make lint
make typecheck
make build-frontend
make migrate
make dev-backend
make dev-frontend
```

## Current Status

- Implemented: authentication bridge, owner-scoped mandates, CASP, ART and EMT intake, 18 track templates, official MiCAR article refresh, manual supplementary-source ingestion, source-change review queue, document review cockpit and approved DOCX package generation.
- Implemented safety work: outbound-processing gate, reversible redaction, verified-source approval and export gate, source-change flagging, citation-failed approval block and persisted template records.
- Outstanding production work: authority-specific automated supplementary feeds, Level 2 and Level 3 reviewed source coverage, production deployment, operational audit review and browser-level end-to-end checks.

No client matter should be processed externally until the required professional,
confidentiality and processing approvals have been documented.
