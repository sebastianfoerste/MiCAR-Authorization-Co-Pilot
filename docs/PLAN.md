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
- A nine-section CASP intake workflow.
- A MiCAR anchor library with official German article refresh from the
  Publications Office CELEX source.
- A curator verification endpoint for fetched anchor fingerprints.
- One authored CASP template: governance under Articles 67, 68 and 73 MiCAR.
- Local structural draft rendering and DOCX package export.

EMT and ART are stubs. External ESMA, EBA and BaFin entries are discovery
pointers pending source ingestion and review. This is therefore a drafting
prototype, with a narrow CASP use case.

## Control Model

Client confidentiality and source provenance are product requirements:

1. Mandates and artifacts are available to their owner and admin users only.
2. Authentication denies new users unless an allowlist or explicit local
   development override is configured.
3. External model processing is disabled by default.
4. When enabled, every cited anchor must carry reviewed official text.
5. Facts sent externally are redacted by default and locally restored in output.
6. Identifiable outbound facts require an express configuration approval.
7. Citation failures prevent package export.
8. All generated clauses remain subject to lawyer review.

## Next Delivery Stages

1. Author and review the remaining CASP templates, beginning with the
   authorisation application and programme of operations.
2. Add reviewed ingestion for ESMA, EBA and BaFin materials, including source
   supersession handling and operator-visible update queues.
3. Add an artifact review page showing generation status, citation failures and
   source provenance before download.
4. Implement EMT and ART only after their source and template sets have passed
   legal review.
5. Add production authentication, deployment configuration, audit review UI and
   browser-level end-to-end checks before live mandate use.

## Verification Standard

Run:

```bash
make test
make lint
make typecheck
make build-frontend
```

For any real drafting exercise, review the source fingerprint status and open
the official source links before approving generated language. The target
quality level is an associate draft for partner review, never an autonomous
filing.
