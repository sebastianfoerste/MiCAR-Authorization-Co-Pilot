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
- A curator verification endpoint for fetched anchor fingerprints.
- Eighteen authored structural templates: nine CASP, five ART and four EMT.
- Manual public-source text ingestion for supplementary anchors, fingerprinted
  change triage and source verification.
- Pending-change propagation from amended official MiCAR fingerprints to
  affected rendered clauses.
- Clause-level review with provenance display and approved DOCX package export.
- An administrator-only view of redacted operational audit events.
- Automated browser regression checks for malformed development identity
  handling and role-gated audit visibility.

External ESMA, EBA and BaFin entries are discovery pointers until a curator
loads and verifies public source text. Authority-specific automated feeds and
complete supplementary-source coverage remain future work. This is therefore
a drafting prototype across three MiCAR tracks.

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
9. An export package contains only latest, lawyer-approved clauses whose cited
   sources are still verified.

## Next Delivery Stages

1. Perform substantive legal review of all 18 structural templates against the
   intended filing strategy and competent-authority expectations for each matter.
2. Select, ingest and review the supplementary Level 2 and Level 3 materials
   required for each track, beginning with sources needed by live template use.
3. Add authority-specific automated monitoring only after stable official
   source endpoints and change-review responsibilities are defined.
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
