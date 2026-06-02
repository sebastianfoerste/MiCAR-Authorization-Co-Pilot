# Legal control map

This note maps the prototype's legal and professional risks to concrete workflow controls. It is intended for reviewers who want to understand whether the repository reflects legal-engineering judgment rather than autonomous legal advice.

| Risk | Workflow control | Evidence in repository |
| --- | --- | --- |
| Hallucinated or unsupported regulatory basis | Only curator-verified source text can support approval or external synthesis. | Anchor ingestion, fingerprint review and citation verification gates. |
| Confidential client facts leaving the local environment | External processing is disabled by default and mandate facts are redacted before outbound processing. | `EXTERNAL_LLM_PROCESSING_ENABLED` and redaction controls. |
| Unreviewed legal output reaching a client or regulator | Only lawyer-approved clauses with currently verified sources can enter an export package. | Review cockpit, clause approval status and export package gate. |
| Changed source law invalidating previous drafting | Source refreshes generate curator-visible review items and flag clauses using old anchors. | Source-change queue and fingerprint comparison workflow. |
| Agent action being treated as legal judgment | Agents may create findings and proposals, but they cannot approve clauses, verify sources or export packages. | Supervised agent layer and documented review notes for proposed actions. |
| Poor auditability of consequential decisions | Operational events are persisted with redacted payloads and review states. | Admin audit protocol and mandate-level event records. |

## Intended reviewer takeaway

The system is deliberately constrained. It treats automation as a way to structure intake, source discipline, review status and export readiness. It does not replace legal judgment, and it does not treat generated text as filing-ready without human approval.
