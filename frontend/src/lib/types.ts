// Shared TS types mirrored from backend Pydantic schemas. Hand-written
// because the surface is small and the change rate is low; we revisit a
// generator if the gap becomes painful.

export type Track = "casp" | "emt" | "art";

export type TrackOut = {
  code: Track;
  label_de: string;
  required_section_keys: string[];
};

export type MandateState =
  | "draft"
  | "intake"
  | "ready_to_generate"
  | "generated"
  | "in_review"
  | "approved"
  | "filed";

export type MandateOut = {
  id: number;
  name: string;
  client_label: string | null;
  track: Track;
  state: MandateState;
  target_filing_date: string | null;
  created_at: string;
  updated_at: string;
};

export type SectionOut = {
  section_key: string;
  answers: Record<string, unknown> | null;
  is_complete: boolean;
  errors: string[];
  validated_at: string | null;
};

export type IntakeListOut = {
  track: Track;
  sections: SectionOut[];
  is_ready_for_generation: boolean;
  blocking: string[];
};

export const STATE_LABELS_DE: Record<MandateState, string> = {
  draft: "Entwurf",
  intake: "Intake",
  ready_to_generate: "Bereit zur Erstellung",
  generated: "Erstellt",
  in_review: "In Prüfung",
  approved: "Freigegeben",
  filed: "Eingereicht",
};
