# Release Checklist

Classification: **acceptance procedure**.

- [ ] Source commit and required baseline recorded.
- [ ] Version is 0.8.9 in runtime, CLI, distribution, docs, wheel, and sdist.
- [ ] Released Core 0.5.0 wheel filename, origin, hash, and import path recorded.
- [ ] Full pytest, Ruff, mypy, ordinary validation, docs, CLI drift, and hard
      cutover gates pass with every skip and warning reconciled.
- [ ] Windows and Ubuntu CI pass on Python 3.11, 3.12, 3.13, and 3.14.
- [ ] Wheel and sdist pass Twine, content, metadata, privacy, and checksum checks.
- [ ] Separate clean wheel and sdist installs pass the installed workflow.
- [ ] Synthetic visual matrix passes and evidence stays outside the repository.
- [ ] Owner physical acceptance is recorded for the exact wheel and commit.
- [ ] Owner release authorization is explicit.
- [ ] Before authorization: no tag, GitHub Release, upload, publication,
      deployment, or issue closure.

Use [the acceptance matrix](releases/v0.8.9_acceptance_matrix.md) for evidence.
