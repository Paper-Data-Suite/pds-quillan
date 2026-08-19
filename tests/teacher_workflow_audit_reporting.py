"""Reporting helpers for the Quillan v0.10.0 teacher-workflow audit."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable

METRICS_BEGIN = "=== QUILLAN TEACHER WORKFLOW AUDIT METRICS BEGIN ==="
METRICS_END = "=== QUILLAN TEACHER WORKFLOW AUDIT METRICS END ==="


@dataclass(frozen=True, slots=True)
class AuditProvenance:
    """Environment facts captured by the audit runner."""

    git_sha: str
    quillan_version: str
    python_version: str
    pds_core_version: str
    operating_system: str
    generated_at_utc: str


def parse_metric_rows(output: str) -> tuple[dict[str, Any], ...]:
    """Parse JSON metric rows emitted by the menu-density contract."""
    if METRICS_BEGIN not in output or METRICS_END not in output:
        raise ValueError("teacher-workflow audit metric markers were not found")
    body = output.split(METRICS_BEGIN, 1)[1].split(METRICS_END, 1)[0]
    rows: list[dict[str, Any]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("label"), str):
            raise ValueError("invalid teacher-workflow audit metric row")
        rows.append(parsed)
    if not rows:
        raise ValueError("teacher-workflow audit emitted no metric rows")
    labels = [row["label"] for row in rows]
    if len(labels) != len(set(labels)):
        raise ValueError("teacher-workflow audit metric labels are not unique")
    return tuple(rows)


def render_teacher_workflow_audit_report(
    rows: Iterable[dict[str, Any]], provenance: AuditProvenance
) -> str:
    """Render the committed issue #379 audit artifact from executed measurements."""
    materialized = tuple(rows)
    by_label = {str(row["label"]): row for row in materialized}
    required = {
        "assignment creation",
        "repeated assignment creation",
        "class-set student handoff",
        "complete individual review",
        "student selection",
        "plain-paper creation",
        "evidence opening",
        "minimum requirements",
        "review units",
        "observations",
        "ratings",
        "feedback composition",
        "feedback export",
        "assignment-report export",
        "Core scan review",
        "route selection/correction",
        "post-dispatch review",
        "successful retry",
        "partial scan intake",
        "workflow-state changes",
    }
    missing = sorted(required - by_label.keys())
    if missing:
        raise ValueError(f"required audit metrics are missing: {', '.join(missing)}")

    initial = by_label["assignment creation"]
    repeated = by_label["repeated assignment creation"]
    selection = by_label["student selection"]
    handoff = by_label["class-set student handoff"]
    complete_review = by_label["complete individual review"]

    marginal_second = {
        key: int(repeated[key]) - int(initial[key])
        for key in ("prompt_count", "screen_count", "menu_transition_count")
    }
    marginal_handoff = {
        key: int(handoff[key]) - int(selection[key])
        for key in (
            "prompt_count",
            "screen_count",
            "menu_transition_count",
            "context_reselection_count",
            "student_selection_count",
            "backtracking_count",
        )
    }

    lines: list[str] = [
        "# Quillan v0.10.0 Teacher-Workflow Audit",
        "",
        "Issue: #379 — Audit assignment creation and class-set review journeys",
        "",
        "## Baseline provenance",
        "",
        f"- Audited Git SHA: `{provenance.git_sha}`",
        f"- Quillan version: `{provenance.quillan_version}`",
        f"- Python version: `{provenance.python_version}`",
        f"- Installed `pds-core` version: `{provenance.pds_core_version}`",
        f"- Audit operating system: `{provenance.operating_system}`",
        f"- Audit generated at (UTC): `{provenance.generated_at_utc}`",
        "- Data policy: synthetic repository fixtures only; no real student or school data.",
        "",
        "Commands used:",
        "",
        "```text",
        "python scripts/capture_teacher_workflow_audit.py",
        'python -m pytest -m "menu_density_workflow or menu_density_contract" -q -s',
        "```",
        "",
        "The capture script sets `QUILLAN_TEACHER_WORKFLOW_AUDIT=1` only for the",
        "subprocess that executes the recorder-backed workflow matrix. The audited SHA",
        "is read from `git rev-parse HEAD`; it is not hard-coded in the reporting code.",
        "",
        "## Methodology",
        "",
        "The audit reuses Quillan's existing `MenuScreenRecorder` and menu-density",
        "acceptance tests. Each measured row comes from an executed teacher-facing",
        "workflow with deterministic synthetic responses. The recorder captures",
        "clear-delimited screens plus every prompt and scripted teacher response.",
        "",
        "The report deliberately preserves the numerical baseline here rather than",
        "asserting today's counts as permanent test invariants. Later v0.10.0 issues",
        "are expected to reduce interaction cost while retaining scenario validity,",
        "recorder integrity, teacher judgment, and evidence/history protections.",
        "",
        "Metric definitions:",
        "",
        "- **Prompt/input count:** explicit calls for teacher input, including pauses.",
        "- **Screen count:** clear-delimited teacher-facing screen segments.",
        "- **Menu-transition count:** changes between adjacent recorded screen headings.",
        "- **Context selection count:** class + assignment + student selection prompts.",
        "- **Context reselection count:** repeated selection of a context kind already",
        "  established earlier in the same measured journey.",
        "- **Repeated-configuration count:** reusable assignment-configuration prompts",
        "  encountered again in a repeated-assignment journey.",
        "- **Backtracking count:** explicit `B` responses used to return toward parent",
        "  menus. Not every back action is removable; findings distinguish routine",
        "  throughput friction from intentional safety/navigation boundaries.",
        "- **Pause count:** `Press Enter...` interactions.",
        "- **Next-student cost:** reported as the marginal interaction added by the",
        "  class-set handoff journey over selecting one student from the same entry path.",
        "- **Next-incomplete-stage cost:** qualitative plus stage-path counts because",
        "  Quillan currently exposes progress but has no direct `Continue Review` route.",
        "- **Export/recovery cost:** relevant executed export/recovery workflow counts;",
        "  uninstrumented exceptional paths are documented qualitatively rather than",
        "  assigned manufactured counts.",
        "",
        "## Scenario matrix",
        "",
        "| Journey | Synthetic mode/state | Starting point | Intended end state |",
        "| --- | --- | --- | --- |",
        "| Initial assignment creation | roster + Core standards profile | Assignment Management | saved assignment |",
        "| Repeated similar assignment | same class/profile/configuration | Assignment Management | second saved assignment |",
        "| Printable-response preparation | printable response packet | Printable Response Pages | installed packet/routes |",
        "| Scan intake and routing | complete + partial retained scans | scan intake | routed/attention state |",
        "| Routed submission review | assembled digital evidence | Review Student Work | selected review-ready student |",
        "| Plain-paper recovery | no digital evidence | selected student | explicit plain-paper submission/review record |",
        "| Complete individual review | review-ready synthetic submission | selected student | evidence/status/requirements/observations/ratings/feedback completed and feedback exported |",
        "| Individual review stage decomposition | review-ready synthetic submission | selected student | representative stage action completed |",
        "| Class-set handoff | two roster students with different states | first selected student | second selected student |",
        "| Feedback export | ready-for-export review | selected student | feedback export created |",
        "| Assignment report export | assignment dashboard | reports menu | class summary export created |",
        "| Recovery | Core scan review / route correction / post-dispatch failure | attention state | corrected or safely returned |",
        "",
        "Additional automated repository tests cover missing assignment-creation",
        "standards-profile prerequisites, routed evidence awaiting assembly, and",
        "missing/stale feedback-export state. Those paths are used as qualitative",
        "recovery evidence here because they are not currently density-instrumented.",
        "",
        "## Quantitative results",
        "",
        "| Workflow | Prompts | Screens | Transitions | Context selections | Reselections | Repeated config | Back | Pauses |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in materialized:
        lines.append(
            "| {label} | {prompt_count} | {screen_count} | {menu_transition_count} | "
            "{context_selection_count} | {context_reselection_count} | "
            "{repeated_configuration_count} | {backtracking_count} | {pause_count} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "### Key derived baselines",
            "",
            f"- Initial assignment creation: **{initial['prompt_count']} prompts / "
            f"{initial['screen_count']} screens / {initial['menu_transition_count']} transitions**.",
            f"- Two substantially similar assignments in one session: **{repeated['prompt_count']} prompts / "
            f"{repeated['screen_count']} screens**, including **{repeated['repeated_configuration_count']} "
            "repeated configuration decisions** and "
            f"**{repeated['context_reselection_count']} context reselection**.",
            f"- Marginal second similar assignment within that measured session: **{marginal_second['prompt_count']} "
            f"additional prompts / {marginal_second['screen_count']} additional screens / "
            f"{marginal_second['menu_transition_count']} additional transitions**. This subtraction is a",
            "  descriptive comparison, not an independent workflow measurement.",
            f"- Single-student selection journey: **{selection['prompt_count']} prompts / "
            f"{selection['screen_count']} screens**.",
            f"- Two-student class-set handoff journey: **{handoff['prompt_count']} prompts / "
            f"{handoff['screen_count']} screens**. Relative to the single-student path, reaching the second",
            f"  student adds **{marginal_handoff['prompt_count']} prompts / {marginal_handoff['screen_count']} screens / "
            f"{marginal_handoff['menu_transition_count']} transitions**, plus **{marginal_handoff['context_reselection_count']} "
            "context reselection** and **1 additional student selection**.",
            f"- One continuous complete individual-review journey: **{complete_review['prompt_count']} prompts / "
            f"{complete_review['screen_count']} screens / {complete_review['menu_transition_count']} transitions** from "
            "evidence opening through explicit minimum-requirement disposition, observations, ratings, feedback completion, and Markdown export.",
            f"- One student feedback-export journey: **{by_label['feedback export']['prompt_count']} prompts / "
            f"{by_label['feedback export']['screen_count']} screens**.",
            f"- One assignment-report export journey: **{by_label['assignment-report export']['prompt_count']} prompts / "
            f"{by_label['assignment-report export']['screen_count']} screens**.",
            "",
            "### Review-stage paths",
            "",
            "The `complete individual review` row above is the single end-to-end teacher-facing",
            "baseline. The rows below are additional stage decompositions; they are not additive",
            "estimates and should not be summed to reconstruct the complete-review cost.",
            "",
            "| Stage | Prompts | Screens | Transitions |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for label in (
        "evidence opening",
        "minimum requirements",
        "review units",
        "observations",
        "ratings",
        "feedback composition",
        "workflow-state changes",
        "feedback export",
    ):
        row = by_label[label]
        lines.append(
            f"| {label} | {row['prompt_count']} | {row['screen_count']} | {row['menu_transition_count']} |"
        )

    lines.extend(
        [
            "",
            "### Recovery paths",
            "",
            "| Recovery workflow | Prompts | Screens | Transitions | Backtracking |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in (
        "partial scan intake",
        "Core scan review",
        "route selection/correction",
        "post-dispatch review",
        "successful retry",
        "partial scan intake",
        "workflow-state changes",
        "plain-paper creation",
    ):
        row = by_label[label]
        lines.append(
            f"| {label} | {row['prompt_count']} | {row['screen_count']} | "
            f"{row['menu_transition_count']} | {row['backtracking_count']} |"
        )

    lines.extend(
        [
            "",
            "## Journey observations",
            "",
            "1. **Assignment reuse is manual.** The second similar assignment traverses the",
            "   same configuration sequence as the first. The recorder identifies ten reusable",
            "   configuration decisions that are entered again in the two-assignment journey.",
            "2. **Class and assignment context is established before student review, but student",
            "   handoff still round-trips through the assignment dashboard.** After backing out",
            "   of one student's review, the teacher chooses `Select student/submission` again",
            "   and re-enters the student picker. There is no next/previous or next-needing-review",
            "   action on the selected-student screen.",
            "3. **A complete ordinary review requires repeated returns to the selected-student",
            "   action menu.** The end-to-end recorder stays on one student but still traverses",
            f"   **{complete_review['prompt_count']} prompts / {complete_review['screen_count']} screens** while moving through",
            "   evidence, requirements, observations, ratings, feedback, and export.",
            "4. **Progress state exists but next action is interpretive.** The selected-student",
            "   summary reports observations, ratings, feedback, exports, warnings, submission",
            "   validity, and assembly state. The teacher must map that status to one of the",
            "   numbered review actions; no direct `Continue Review` path exists.",
            "5. **Submission modes converge at review but have different preparation/recovery",
            "   costs.** Printable responses add packet generation and scan-routing work; routed",
            "   evidence may require assembly; plain paper requires an explicit teacher-created",
            "   submission record before review actions become available.",
            "6. **Exports are split by scope.** Student feedback is exported from the selected",
            "   student menu; class/standards/performance reports are reached from the assignment",
            "   dashboard. Existing behavior does not batch per-student feedback exports.",
            "7. **Recovery messaging is generally actionable but can be navigation-heavy.** Core",
            "   scan review and route correction expose explicit resolution paths; post-dispatch",
            "   failures expose retry/status/resolution actions; missing digital evidence offers",
            "   explicit plain-paper creation rather than silently fabricating evidence.",
            "8. **Diagnostics are already relatively compact once context is established.** The",
            "   full diagnostic dashboard is a short local path, so #390 should focus on safe",
            "   diagnostic events/attention integration rather than duplicating private content.",
            "",
            "## Friction findings",
            "",
            "| Finding | Classification | Evidence | Teacher-effort consequence | Safety note |",
            "| --- | --- | --- | --- | --- |",
            f"| Similar assignments repeat setup | high-frequency workflow friction | repeated-assignment journey: {repeated['repeated_configuration_count']} repeated configuration decisions | repeated entry of stable review configuration | copying/presets must still require explicit review before save |",
            "| Student handoff returns through parent dashboard/picker | class-set throughput friction | class-set handoff adds 3 prompts and 3 screens over single selection | repeated navigation across every class set | preserve explicit student identity in active header |",
            "| Student context must be selected again during handoff | context/reselection friction | handoff reselection count = 1 | avoidable routine reselection | never infer a different student without visible selection/navigation |",
            f"| Complete review is split across stage submenus | high-frequency workflow friction | complete individual review: {complete_review['prompt_count']} prompts / {complete_review['screen_count']} screens | repeated menu traversal within every fully reviewed submission | preserve explicit teacher decisions at each judgment-bearing stage |",
            "| Progress is visible but no next action is computed for the teacher | discoverability/guidance friction | selected-student summary + separate stage actions | teacher interprets stage and chooses menu entry | guidance must not invent completion or judgment |",
            "| Per-student feedback export is isolated | export/reporting friction | feedback export is a separate selected-student journey | repeated export work for a completed class set | batch scope/overwrite must remain explicit |",
            "| Scan/route recovery requires several focused screens | error-recovery friction | Core scan review and route-correction rows | extra work when intake is ambiguous | correction history/evidence must remain preserved |",
            "| Missing digital evidence offers explicit plain-paper creation | intentional safety/confirmation step | plain-paper creation workflow | one extra explicit recovery action | prevents silent substitution of physical evidence state |",
            "| Assignment overwrite/publication remain explicit | intentional safety/confirmation step | existing assignment/publication contracts and menus | confirmation cost is intentional | do not optimize away overwrite or publication consent |",
            "| Later suite attention/provider integration is not part of this audit | future integration concern | Phase 1 dependency boundary | no immediate teacher action change | #391–#392 remain blocked on shared Core provider/inventory APIs |",
            "",
            "No correctness, privacy, or evidence-integrity defect requiring an emergency",
            "follow-up was discovered by this workflow audit.",
            "",
            "## Phase 1 mapping and improvement targets",
            "",
            "- **#380 — Safe assignment copying:** provide a teacher-invoked way to start from an",
            "  existing assignment so stable configuration is not re-entered. Target: eliminate",
            "  the current repeated entry of reusable configuration while preserving editable",
            "  identity/prompt fields and explicit save/overwrite confirmation.",
            "- **#381 — Reusable review configuration:** extract reusable review configuration so",
            "  the ten repeated configuration decisions measured in the similar-assignment",
            "  journey can be intentionally reused rather than retyped.",
            "- **#382 — Recent class/assignment context:** retain visibly identified active class",
            "  and assignment context during routine review. Target: moving among students in one",
            "  assignment must not require class or assignment reselection.",
            "- **#383 — Deterministic review work queue:** surface students needing work and the",
            "  reason they need work from persisted state already shown in dashboards. Do not",
            "  infer teacher judgments or reorder nondeterministically.",
            "- **#384 — Next/previous/next-needing-review navigation:** remove the measured parent",
            "  dashboard/student-picker round trip for routine handoff. Target: no context",
            "  reselection solely to move to an adjacent/next-needing-review student.",
            "- **#385 — `Continue Review` guidance:** translate persisted progress into a direct",
            "  route to the earliest incomplete mechanical stage. It must never mark a stage",
            "  complete or choose a rating/applicability/feedback decision for the teacher.",
            "- **#386 — Compact routine review screen:** keep the useful current status summary but",
            "  prioritize routine next actions and class-set navigation. Less-common evidence/page",
            "  management and diagnostic actions must remain reachable.",
            "- **#387 — Batch feedback export:** remove repeated per-student export traversal for a",
            "  completed class set. Preserve explicit batch scope, readiness reporting, overwrite",
            "  policy, and per-student export provenance.",
            "- **#388 — Class summary/review-completion views:** surface review completion plus",
            "  current/stale/missing export state together so teachers can identify attention",
            "  without entering each student record.",
            "- **#389 — Guided Meridian sharing/publication:** connect completed review context to",
            "  the existing explicit academic-result publication flow. Publication must remain a",
            "  teacher-controlled action; completion must never imply automatic sharing.",
            "- **#390 — Privacy-conscious diagnostics:** add diagnostic/attention events that expose",
            "  operational state and next-action categories without student writing, teacher",
            "  feedback text, private notes, or other unnecessary educational content.",
            "",
            "## Confirmed safety properties to preserve",
            "",
            "- Assignment creation and overwrite are explicit teacher actions.",
            "- Standards, Focus Standards, requirements, observations, applicability, ratings,",
            "  rationales, feedback, and completion remain teacher-entered/teacher-confirmed.",
            "- Missing digital evidence is not silently replaced; plain-paper state is explicit.",
            "- Scan correction and post-dispatch recovery retain evidence/history rather than",
            "  deleting inconvenient records.",
            "- Feedback export does not rescore work or generate AI feedback.",
            "- Academic-result publication remains separate and explicit; review completion alone",
            "  does not publish or share a result.",
            "- Repository audit fixtures contain synthetic identities/content only.",
            "",
            "## Validation gates",
            "",
            "After generating this report, validate with:",
            "",
            "```text",
            "python -m pytest -ra",
            "python -m ruff check .",
            "python -m mypy . --no-incremental",
            "python scripts/check_documentation.py",
            "python scripts/verify_release_compatibility.py",
            "python -m pytest tests/test_pds2_only_repository_contract.py -q",
            "git diff --check",
            "```",
            "",
        ]
    )
    return "\n".join(lines)
