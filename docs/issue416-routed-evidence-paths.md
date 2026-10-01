# Issue #416 Slice 4 — bounded routed-evidence paths

New Quillan routed page evidence uses the bounded leaf:

```text
<observation_id>.<image-extension>
```

The observation ID is fixed at `obs_` plus 32 lowercase hexadecimal
characters. With the longest supported image suffix, the writer leaf is bounded
at 41 characters and does not grow with `student_id`, `source_filename`, or
`source_scan_id`.

The containing issuance directory remains unchanged.

Readers accept both the new bounded leaf and the released legacy leaf:

```text
response_<student_id>_pg_<logical_page>__<observation_id>.<ext>
```

Legacy paths are read-only compatibility. Existing evidence and observations
are not renamed or rewritten.

Contextual evidence verification, observation discovery, Academic Result
student-work resolution, and existing persisted-result models resolve the exact
persisted path against one of those two canonical forms.

Post-dispatch failure preservation also accepts both filename families. New
bounded evidence no longer encodes student identity in its leaf; student and
page identity remain in structured observation/review records.

This slice does not yet add legacy idempotent replay through
`persist_quillan_page_observation(...)`; transaction-level replay compatibility
is a separate #416 boundary.
