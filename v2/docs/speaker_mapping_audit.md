# Speaker Mapping camelCase Normalization Audit

**Date:** 2026-03-25
**Scope:** All `.py` files in `v2/backend/src/`, all `.ts/.tsx` files in `v2/frontend/src/`, and `prompts.yaml`

## Summary

| Category | Count |
|----------|-------|
| Real issues (BUG/WARN) | 5 |
| False positives (OK) | Many |
| Models correctly camelCase | Yes (Pydantic + TS SpeakerMappingEntry) |

The Pydantic `SpeakerMappingEntry` and `TopCandidate` models in `models.py` are correctly camelCase. The TypeScript `SpeakerMappingEntry` and `TopCandidate` interfaces in `models.ts` are correctly camelCase. The `recording_service.py` `assign_speaker()` function writes camelCase keys. The `speaker_processor.py` writes camelCase keys into speaker_mapping dicts.

However, there are a few issues found:

---

## Findings

### 1. profile_store.py returns snake_case internal dict keys consumed by speaker_processor.py

**File:** `/home/cbird/repos/quickscribe/v2/backend/src/app/services/profile_store.py`
**Lines:** 100-101, 197-239
**Severity:** OK (internal plumbing, not persisted to speaker_mapping)

The `get_profiles()` function returns dicts with `"participant_id"` and `"display_name"` keys (lines 100-101). The `find_best_match()` function returns dicts with `"participant_id"`, `"display_name"`, `"top_candidates"` keys (lines 204-239). These are **internal** Python dicts read from the SQLite `speaker_profiles` table columns, not speaker_mapping JSON fields. They are consumed by `speaker_processor.py` which correctly translates them to camelCase (`p["participant_id"]` -> `"participantId"`, `p["display_name"]` -> `"displayName"`) when building the speaker_mapping entries (lines 226-228, 551-553).

**Verdict:** OK -- these are SQLite column reads, not speaker_mapping fields. The translation to camelCase happens correctly at the boundary.

---

### 2. prompts.yaml uses `"name"` and `"reasoning"` in infer_speaker_names prompt

**File:** `/home/cbird/repos/quickscribe/v2/backend/src/app/services/prompts.yaml`
**Lines:** 193-194
**What:** The LLM prompt asks for `{"name": "<inferred name>", "reasoning": "<reasoning>"}` format.
**Severity:** WARN

The `infer_speaker_names` prompt instructs the LLM to return `"name"` and `"reasoning"` fields. The `ai_service.infer_speakers()` function (line 126) returns this raw dict. However, this function is currently **not called from any route or service** -- there is no router endpoint that invokes it, and no code in the codebase consumes its output. If it were to be used in the future, the consumer would need to map `"name"` to `"displayName"` before writing to speaker_mapping.

**Verdict:** WARN -- dead code, but if reactivated without a mapping layer, the `"name"` field would be inconsistent with the camelCase convention.

---

### 3. Frontend Participant model uses `display_name` (snake_case)

**File:** `/home/cbird/repos/quickscribe/v2/frontend/src/types/models.ts`
**Lines:** 149, 372, 385
**Severity:** OK -- these are on `Participant`, `CreateParticipantRequest`, and `UpdateParticipantRequest` interfaces, NOT on `SpeakerMappingEntry`.

The `Participant` interface has `display_name: string` (line 149). The `CreateParticipantRequest` has `display_name: string` (line 372). The `UpdateParticipantRequest` has `display_name?: string` (line 385). These match the SQLite `participants` table column name and the backend Pydantic `Participant` model. These are **not** speaker_mapping fields.

**Verdict:** OK -- Participant model fields, matching SQLite schema.

---

### 4. Frontend `AssignSpeakerRequest` uses `participant_id` and `use_for_training`

**File:** `/home/cbird/repos/quickscribe/v2/frontend/src/types/models.ts`
**Lines:** 408-409
**What:** `participant_id: string` and `use_for_training?: boolean`
**Severity:** OK -- these are API request body fields matching the backend `SpeakerAssignment` Pydantic model (models.py lines 306-309), NOT speaker_mapping entry fields. The backend model also uses `participant_id` and `use_for_training` as these are Python function parameters, not JSON keys stored in speaker_mapping.

**Verdict:** OK -- API request schema, matches backend Pydantic model.

---

### 5. Frontend pages send `participant_id` and `use_for_training` in API calls

**File:** `/home/cbird/repos/quickscribe/v2/frontend/src/pages/RecordingDetailPage.tsx`
**Lines:** 152, 162, 167, 181, 194, 206
**File:** `/home/cbird/repos/quickscribe/v2/frontend/src/pages/SpeakerReviewsPage.tsx`
**Lines:** 161-162
**Severity:** OK -- these are API request bodies matching `AssignSpeakerRequest`, not speaker_mapping field access.

**Verdict:** OK -- API call payloads.

---

### 6. Frontend `SpeakerDropdown.tsx` uses `p.display_name` on Participant objects

**File:** `/home/cbird/repos/quickscribe/v2/frontend/src/components/recordings/SpeakerDropdown.tsx`
**Lines:** 33, 43, 126, 129
**Severity:** OK -- accessing `Participant.display_name`, not a speaker_mapping field.

**Verdict:** OK.

---

### 7. Backend `SpeakerAssignment` model uses `participant_id`, `manually_verified`, `use_for_training`

**File:** `/home/cbird/repos/quickscribe/v2/backend/src/app/models.py`
**Lines:** 307-309
**Severity:** OK -- this is an API request schema, not SpeakerMappingEntry. These are Python parameter names for the `assign_speaker()` function.

**Verdict:** OK.

---

### 8. Backend `recording_service.py` docstring mentions snake_case

**File:** `/home/cbird/repos/quickscribe/v2/backend/src/app/services/recording_service.py`
**Line:** 476
**What:** Docstring says "set the participant_id and display_name" -- referring to the function's behavior, but the actual code on lines 505-506 correctly writes `"participantId"` and `"displayName"`.
**Severity:** OK -- docstring language, not code. The actual JSON keys written are camelCase.

**Verdict:** OK -- cosmetic only.

---

### 9. No `normalizeMappingEntry` function found

Searched for `normalizeMappingEntry`, `normalize_mapping`, and `normalize_speaker` across the entire v2 codebase. Only references found:
- A comment in `models.py` line 69 referencing the migration script `normalize_speaker_mappings.py`
- The migration tool itself at `v2/tools/normalize_speaker_mappings.py`

**Verdict:** OK -- no runtime normalization function exists that should have been removed.

---

## Real Issues Summary

| # | File | Line(s) | Issue | Severity |
|---|------|---------|-------|----------|
| 1 | `prompts.yaml` | 193-194 | `infer_speaker_names` prompt returns `"name"` and `"reasoning"` instead of `"displayName"` | WARN |

All other findings are false positives -- they are either SQLite column names, Participant model fields, API request schemas, or internal Python variable names that do not represent speaker_mapping JSON keys.

## Conclusion

The speaker_mapping normalization is **effectively complete**. All code paths that read/write speaker_mapping JSON use camelCase keys consistently:

- `speaker_processor.py` builds entries with `participantId`, `displayName`, `topCandidates`, `identificationStatus`, `similarity`, `identifiedAt`, `suggestedParticipantId`, `embedding`
- `recording_service.py` writes `participantId`, `displayName`, `manuallyVerified`, `identificationStatus`, `useForTraining`
- `participant_service.py` reads `participantId` when clearing deleted participants (line 168)
- Frontend `SpeakerMappingEntry` interface uses only camelCase fields
- Frontend `TopCandidate` interface uses only camelCase fields
- Pydantic `SpeakerMappingEntry` and `TopCandidate` use only camelCase field names with no `Field(alias=...)` or `populate_by_name`

The only actionable item is the `infer_speaker_names` prompt which uses `"name"` and `"reasoning"` -- but this code path is currently dead (no caller). If reactivated, it would need a mapping layer to convert `"name"` to `"displayName"`.
