# MiCAR Authorization Co-Pilot: Implementation Plan

## Objective

Provide an internal, review-gated drafting workbench for MiCAR authorisation
matters. The application should reduce repeated assembly work while preserving
lawyer control over legal conclusions, source currency and every client-facing
deliverable.

## Verified Current Scope

The codebase currently contains:

- A FastAPI and Postgres backend with a Next.js frontend.
- Owner-scoped mandates and an admin override.
- A nine-section CASP intake workflow, a six-section ART workflow and a
  five-section EMT workflow.
- A MiCAR anchor library with official German article refresh from the
  Publications Office CELEX source.
- An official German-text refresh for nine adopted Level 2 instruments tied
  to live CASP, ART and EMT templates: CASP authorisation, complaints,
  conflicts and market-abuse procedures, ART authorisation, ART/EMT
  whitepaper format and conditional ART/EMT liquidity management.
- A curator verification endpoint for fetched anchor fingerprints.
- Twenty-two authored structural templates: nine CASP, six ART and seven EMT,
  including standalone EMT recovery and redemption plans and conditional ART/EMT
  liquidity management templates.
- Official discovery pointers for the EBA ART governance, recovery-plan and
  redemption-plan guidelines, EBA liquidity stress-testing guidelines and the
  joint EBA/ESMA suitability guidelines cited by live templates, with an
  official PDF refresh command for those five guideline texts.
- Manual public-source text ingestion for supplementary anchors, fingerprinted
  change triage and source verification.
- Pending-change propagation from amended official MiCAR fingerprints to
  affected rendered clauses.
- Clause-level review with provenance display and approved DOCX package export.
- An administrator-only view of redacted operational audit events.
- Automated browser regression checks for malformed development identity
  handling and role-gated audit visibility.

The nine Level 2 entries are required citations in the affected templates and
are fetched from the official Publications Office source. The five linked EBA
and EBA/ESMA guideline entries are fetched from official EBA-hosted PDFs. All
freshly loaded official text remains unavailable for approval or external
synthesis until a curator verifies the stored text and fingerprint. Other ESMA,
EBA and BaFin entries remain discovery pointers until a curator loads and
verifies public source text. This is therefore a drafting prototype across
three MiCAR tracks.

## Control Model

Client confidentiality and source provenance are product requirements:

1. Mandates and artifacts are available to their owner and admin users only.
2. Authentication denies new users unless an allowlist or explicit local
   development override is configured.
3. External model processing is disabled by default.
4. When enabled, every cited anchor must carry reviewed official text.
5. Facts sent externally are redacted by default and locally restored in output.
6. Identifiable outbound facts require an express configuration approval.
7. Citation failures prevent clause approval.
8. Source changes flag affected clauses for regeneration and renewed review.
9. Superseded template versions require regeneration before approval or export.
10. An export package contains only latest, lawyer-approved clauses whose cited
   sources are still verified.

## Next Delivery Stages

1. Curator-review the fetched Level 2 source texts and fetched EBA and EBA/ESMA
   guideline texts required by live templates.
2. Perform substantive legal review of each affected template against its
   adopted RTS, ITS and reviewed guideline requirements.
3. Add further authority-specific automated monitoring only after stable
   official source endpoints and change-review responsibilities are defined.
4. Add production authentication, deployment configuration and browser-level
   coverage for complete drafting and package-review workflows before live
   mandate use.

## Verification Standard

Run:

```bash
make test
make e2e
make lint
make typecheck
make build-frontend
```

For any real drafting exercise, review the source fingerprint status and open
the official source links before approving generated language. The target
quality level is an associate draft for partner review, never an autonomous
filing.
