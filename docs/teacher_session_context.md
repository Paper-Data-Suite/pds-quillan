# Teacher session context

Issue: #382 — recent class/assignment context and active-context headers

## Scope

Quillan's interactive teacher menu keeps a small, process-local navigation context so
routine review work can remain inside one class and assignment. The context contains
only the resolved workspace root, exact `class_id`, and exact `assignment_id`.
It never contains a student identity, student writing, review content, ratings,
feedback, or derived judgments.

The context is convenience state, not an authoritative record. It is never serialized,
written to the Paper Data Suite workspace, registered with Core, or exposed as a new
CLI contract. Direct CLI commands remain stateless and continue to require their
existing explicit identifiers.

## Identity and validation rules

Assignment context always implies class context. Changing the class clears the prior
assignment unless a new exact class/assignment pair is committed atomically. A change
in the canonically resolved workspace clears both class and assignment context.

Remembered identifiers are revalidated before assignment-local review work is entered.
Quillan uses canonical roster-backed class discovery and canonical assignment discovery,
matching only exact `class_id` and `assignment_id` values. Assignment titles are display
metadata only and are never used as a fallback identity. If a remembered class or
assignment is removed, malformed, moved to another class, or otherwise no longer
canonical, Quillan clears the stale portion of context and asks the teacher to select
again rather than substituting another record.

## Teacher-facing behavior

The first assignment-review entry in a fresh menu session still asks for class and
assignment. A valid active assignment can then be reused without repeating either
selector. If the assignment is cleared while the class remains active, review entry
asks only for the assignment in that class.

The Review Student Work menu exposes `C. Manage active context`, with explicit actions
to:

1. switch assignment within the current class;
2. switch class and assignment as one committed pair;
3. clear only the assignment while retaining the class; and
4. clear class and assignment context.

Canceling a switch preserves the previous context. Back, Main Menu, refresh actions,
and ordinary workflow completion also preserve context. Quitting Quillan ends the
session and therefore discards it.

Teacher-facing assignment-local screens render a bounded `Active context` block with
the exact class and assignment IDs. A current assignment title is shown when canonical
lookup succeeds; the exact assignment ID remains visible even when title lookup is
unavailable.

## Workspace behavior

The session stores the canonical resolved workspace path only to detect workspace
changes. Rebinding to the same canonical path preserves class/assignment context.
Rebinding to a different canonical path clears it. Workspace files are never changed
by this comparison.

## Selection ownership boundaries

Only selections that establish an operating review target update active context.
Source-only/reference-only selection remains independent. In particular:

- **Copy Writing Assignment** continues to ask for its source assignment explicitly;
- **Save Review Preset from Assignment** continues to ask for its source assignment
  explicitly;
- diagnostic/reference-only pickers do not replace active review context; and
- scan routing does not guess context from routed artifacts.

After scan intake, an explicit **Review student work** action for one exact routed
class/assignment target may activate that exact pair before entering review. Merely
routing scans—or displaying one or more affected targets—does not change context.

## Out of scope

This issue does not add a deterministic work queue, next/previous-student navigation,
`Continue Review` guidance, compact-review redesign, automatic publication, automatic
scoring, or automatic teacher judgments. Those remain separate Phase 1 work items.
