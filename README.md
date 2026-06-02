# MiCAR Authorization Co-Pilot

Technical prototype for producing review-gated MiCAR authorisation drafting
materials. The present implementation supports CASP, asset-referenced token
(ART) and e-money token (EMT) intake workflows with structural draft templates
for all documents declared in the three track catalogues.

The application does not certify current BaFin practice and does not produce a
filing-ready application without lawyer review. Regulatory text must be fetched
from an official source and approved in the anchor library before any external
model synthesis can run.

The architecture is transferable beyond MiCAR: verified sources, scoped access,
redaction, audit trails, agent findings and human-approved export gates are the
same controls an AI-native SaaS legal function needs for product launches,
privacy reviews, customer commitments and evidence-backed approvals.

For scope, current limits and the next implementation stages, see
[`docs/PLAN.md`](docs/PLAN.md). For a reviewer-friendly launch runbook, see
[`docs/launch-readiness.md`](docs/launch-readiness.md).

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
cd backend && uv run python -m micar.anchors.ingest eurlex-level2

# Fetch official German PDF text and fingerprints for the EBA and joint
# EBA/ESMA guidelines cited by live templates.
cd backend && uv run python -m micar.anchors.ingest eba-guidelines

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
- Changed official MiCAR or supplementary source text creates a curator-visible
  review item and flags clauses that used the prior anchor.
- Failed citation verification prevents clause approval.
- Clauses rendered from a superseded template version must be regenerated before approval or export.
- Only the latest lawyer-approved clauses with currently verified sources can
  enter an export package.
- Supervised agents can create findings and proposed actions, but they do not
  verify sources, approve clauses, mutate templates, or create packages.
- Agent action proposals must be accepted or rejected with a documented review
  note before they count as a human decision.
- Administrators can review redacted operational events in the audit protocol.

The source workflow is:

```bash
# Create unverified pointers.
cd backend && uv run python -m micar.anchors.ingest seed

# Fetch official German MiCAR article text and fingerprints.
cd backend && uv run python -m micar.anchors.ingest eurlex --regulation 2023/1114

# Fetch official German text and fingerprints for the adopted Level 2
# instruments cited by the live CASP, ART and EMT templates.
cd backend && uv run python -m micar.anchors.ingest eurlex-level2

# Fetch official German PDF text and fingerprints for the EBA and joint
# EBA/ESMA guidelines cited by live templates.
cd backend && uv run python -m micar.anchors.ingest eba-guidelines

# A curator or admin reviews the fetched source and verifies its fingerprint
# through POST /anchors/{anchor_id}/verify.
```

If a later official MiCAR or Level 2 refresh produces a different stored
fingerprint, the application marks that source unverified, places the change
in the pending queue and flags rendered clauses citing it. The initial
official load remains an unverified source import requiring curator review.

ESMA, EBA, joint EBA/ESMA and BaFin entries initially remain unverified
discovery pointers. The five EBA and joint EBA/ESMA guidelines used by live
templates can be loaded from their official PDFs through `eba-guidelines`;
they still require curator verification before approval or external synthesis.
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

## Agent Layer

The app includes a supervised deterministic agent layer for mandate operations.
Agents run from the mandate cockpit and persist an auditable `agent_run` with
steps, findings and proposed actions. Each run can be opened from the mandate
page to inspect evidence and decide action proposals with a review note.

Implemented agents:

- Readiness Agent: calculates intake, draft, source, review and export gates.
- Citation Auditor Agent: checks rendered clauses against anchors, source status and template freshness.
- Draft QA Agent: flags empty drafts, missing citations, review markers and technical placeholders.
- Source Monitor Agent: summarizes source-change and source-verification queues.
- Package Review Agent: prepares an export-readiness memo without creating the package.
- Template Improvement Agent: flags catalogue gaps and review instructions that should become structured QA tasks.

The current runtime is local and deterministic by design. External LLM-backed
agent reasoning should remain an explicit, review-gated extension after
confidentiality, processing and tracing controls have been documented.

## Commands

```bash
make test
make e2e
make lint
make typecheck
make build-frontend
make migrate
make dev-backend
make dev-frontend
```

For the one-time browser runtime setup required by `make e2e`, run:

```bash
cd frontend && npx playwright install chromium
```

## Current Status

- Implemented: authentication bridge, owner-scoped mandates, CASP, ART and EMT intake, 22 track templates, official MiCAR article refresh, official refresh for nine adopted Level 2 instruments used by live templates, official PDF refresh for five EBA and joint EBA/ESMA guidelines used by live templates, manual supplementary source ingestion, source-change review queue, redacted admin audit view, document review cockpit, supervised mandate agents and approved DOCX package generation.
- Implemented safety work: outbound-processing gate, reversible redaction, verified-source approval and export gate, official and supplementary source-change flagging, citation-failed approval block, audit payload minimisation, persisted template records and automated browser checks for identity, audit access, source review and full CASP drafting flow.
- Outstanding production work: curator verification and substantive legal review of the newly linked Level 2 instruments and Level 3 guidelines, additional authority-specific monitoring, production deployment hardening and optional LLM-backed agent reasoning under explicit confidentiality and tracing controls.

No client matter should be processed externally until the required professional,
confidentiality and processing approvals have been documented.

## License

MIT. The prototype is for supervised legal workflow automation only and does not provide legal advice, legal representation or filing-ready regulatory conclusions.
