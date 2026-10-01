# Issue #416 Slice 5 — legacy routed-evidence replay

Quillan's new routed-evidence writer uses a bounded observation-ID leaf, but an
existing workspace may contain the released legacy filename recorded in an
immutable response-page observation.

Replay now treats the persisted observation as authoritative when that
observation already exists.

For an existing observation, Quillan:

1. loads and validates the immutable observation;
2. permits only the routed-evidence path to differ from the current writer
   projection;
3. requires that persisted path to be either the bounded or released legacy
   canonical form;
4. verifies the exact persisted evidence hash and byte size;
5. verifies the replayed evidence bytes are identical; and
6. returns `status="existing"` with the persisted path.

Replay does not rename the legacy evidence, rewrite the observation, create a
bounded replacement, or migrate the workspace.

If a legacy observation exists and a second bounded evidence artifact also
exists, Quillan treats the state as contradictory rather than silently choosing
one copy.

Missing, changed, unsafe, or contradictory persisted evidence remains an
integrity failure.
