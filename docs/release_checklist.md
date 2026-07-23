# Release Checklist

Classification: **acceptance procedure**.

Current exact candidate: implementation commit
`c3e57db5e0e175e61ce988e0681375d7b76ce861`; wheel SHA-256
`67536b7266770816e7d5732752167f1b77e23767ba48f34d98af48bbee7ade91`;
sdist SHA-256
`6ad8201224343f08edb7a6fc41d8ea6316a1ce4c95992eeeea9f96af94cb6dcd`.

- [x] Source commit and required baseline recorded.
- [x] Version is 0.8.9 in runtime, CLI, distribution, docs, wheel, and sdist.
- [x] Released Core 0.5.0 wheel filename, origin, hash, and import path recorded.
- [x] Full pytest, Ruff, mypy, ordinary validation, docs, CLI drift, and hard
      cutover gates pass with every skip and warning reconciled.
- [x] Windows and Ubuntu CI pass on Python 3.11, 3.12, 3.13, and 3.14.
- [x] Wheel and sdist pass Twine, content, metadata, privacy, and checksum checks.
- [x] Separate clean wheel and sdist installs pass the installed workflow.
- [ ] Current-candidate synthetic visual matrix passes and evidence stays outside
      the repository; earlier evidence is historical support only.
- [ ] Owner physical acceptance is recorded for the exact wheel and commit.
- [ ] Owner release authorization is explicit.
- [x] Before authorization: no tag, GitHub Release, upload, publication,
      deployment, or issue closure.

Use [the acceptance matrix](releases/v0.8.9_acceptance_matrix.md) for evidence.
