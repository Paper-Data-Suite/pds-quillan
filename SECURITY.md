# Security Policy

## Project Status

Quillan is the Paper Data Suite module for writing-response template generation, paper/scanned submission workflows, essay tagging, standards-aligned review, feedback, and publication of writing-related academic results.

The current supported pre-1.0 release line is `0.10.x`. Quillan `0.10.1` is the current patch-release candidate.

Quillan is local-first, teacher-controlled educational software. It is not:

* a hosted service;
* an institutional identity provider;
* a gradebook;
* an autonomous grading system;
* a legal-compliance certification;
* a production authorization provider; or
* a substitute for school or district security controls.

`main` is the active development branch and is not itself a supported release artifact.

Pre-1.0 support does not imply long-term support, permanent API compatibility, permanent workspace compatibility, or backports to earlier development versions.

## Supported Versions

Security and maintenance fixes target the current supported Quillan release line.

| Version                            | Status                                                     |
| ---------------------------------- | ---------------------------------------------------------- |
| `main`                             | Development only; not a supported release artifact         |
| latest released `0.10.x`           | Supported                                                  |
| older superseded `0.10.x` releases | Upgrade recommended; fixes may require the latest `0.10.x` |
| `<=0.9.x`                          | Unsupported unless explicitly documented otherwise         |

There is no guaranteed vulnerability-response SLA, maintenance window, or backport period.

Because Quillan remains pre-1.0, security, compatibility, or integrity fixes may require upgrading to the latest supported release.

## Student Data and Privacy

Quillan may process highly sensitive educational records.

Do not commit, upload, publish, attach, or otherwise expose real classroom data in this repository, public issues, pull requests, discussions, screenshots, CI logs, examples, or other public development artifacts.

Do not publicly post:

* real class rosters;
* real student names;
* real student IDs or other identifiers;
* real student writing;
* scanned or photographed student work;
* submission metadata tied to real students;
* teacher comments or feedback tied to identifiable students;
* rubric ratings;
* standards ratings;
* grades or grade-like records;
* review decisions;
* scan-review findings;
* handwritten or typed student responses;
* generated response forms containing real identifiers;
* parent or guardian contact information;
* exported student reports;
* exported class reports containing identifiable records;
* feedback PDFs or Markdown files from real classroom use;
* multi-student feedback print packets or sharing bundles;
* assembled submission files from real classroom use;
* PDS2 source or routed scan pages from real classroom use;
* local production workspace folders;
* production Academic Work Registrations;
* production Academic Result Manifests;
* production Publication Records;
* production publication artifacts;
* credentials, access tokens, secrets, private keys, or private configuration;
* private school or district documents;
* diagnostic output containing identifiable classroom information; or
* screenshots or logs containing sensitive local paths, identifiers, or records.

Repository examples, fixtures, screenshots, demonstrations, and tests must use synthetic data.

Synthetic data should use clearly fictional:

* names;
* identifiers;
* writing;
* assignments;
* rubric content where appropriate;
* ratings;
* scores;
* feedback; and
* publication records.

Do not lightly alter or pseudonymize real classroom records and then treat them as synthetic fixtures.

Before committing generated files, logs, screenshots, fixtures, reports, scans, manifests, or diagnostic output, verify that they contain no copied classroom data or identifying metadata.

## Local-First Data Handling

Quillan is designed around local, teacher-controlled storage.

Local-first operation reduces unnecessary remote data handling, but does not make data safe merely because it is stored locally.

Student writing, submission metadata, scans, review artifacts, feedback, standards observations, generated reports, Academic Result Manifests, publication-related state, and other workspace data must be protected with deployment-appropriate controls.

Users should consider:

* operating-system account security;
* filesystem permissions;
* full-disk encryption;
* removable-media encryption;
* secure backup destinations;
* protection of externally synchronized folders;
* controlled access to shared or network storage;
* retention and disposal practices;
* secure handling of exported reports; and
* deliberate review before sharing records outside the local workspace.

Users remain responsible for complying with applicable school, district, state, and federal requirements when handling educational records.

## Repository and Workspace Separation

A production Quillan or Paper Data Suite workspace must not be stored inside this source repository.

Repository ignore rules are a development safeguard, not a privacy boundary.

Do not rely on `.gitignore` to protect classroom data.

Before committing changes:

1. inspect the staged file list;
2. review generated files, scans, reports, and logs;
3. verify that no production workspace data is present; and
4. confirm that all fixtures and examples are synthetic.

## Quillan Security Boundaries

Quillan must preserve the distinction between technical accessibility and authorization, and between educational evidence and educational conclusions.

The following distinctions are security- and integrity-sensitive:

```text
filesystem access != authorization

student identity != permission to disclose student work

scan presence != valid assembled submission

submission assembled != review complete

review complete != feedback exported

feedback exported != manifest generated

manifest generated != publication authorized

publication authorized != Meridian ingestion

publication discovery != permission to read referenced artifacts

standards alignment != proficiency

standards rating != Grade

native review state != calculated Meridian proficiency

successful parsing != trusted provenance

hash agreement != confidentiality

package installation != deployment authorization
```

Quillan integrations must not silently collapse these distinctions.

## Producer Ownership and Publication Boundaries

Quillan owns its canonical writing-workflow and academic-result records.

Core owns shared registration, publication, discovery, authorization, and related cross-module infrastructure according to documented Paper Data Suite contracts.

Quillan must not:

* write Meridian-native records;
* treat Meridian as an extension of Quillan storage;
* bypass Core publication authority;
* mutate another module's canonical records;
* reinterpret Core-owned registration or publication state; or
* treat publication as evidence that another consumer has successfully ingested the result.

The intended handoff is:

```text
Quillan producer-native state
-> immutable Quillan Academic Result Manifest
-> Core Academic Work / Publication state
-> authorized compatible consumer discovery
```

A successful Quillan publication means that the result has been published through Core and is available for authorized compatible discovery.

It does not prove that Meridian or another consumer has:

* discovered the publication;
* authorized access;
* opened the manifest;
* imported evidence;
* associated standards evidence;
* calculated proficiency;
* calculated a Grade; or
* generated a report.

## Academic Result Manifest Security

Quillan Academic Result Manifests are immutable producer-owned records.

They may contain or reference sensitive educational information and must be protected accordingly.

Manifest generation and publication are distinct operations.

Preserve:

```text
manifest generation != publication

publication != artifact authorization

manifest authorization != permission to read every referenced file
```

A manifest may reference:

* student evidence;
* feedback;
* scans;
* assembled submissions;
* source pages;
* routed evidence;
* or other producer-owned artifacts.

A consumer's permission to inspect a manifest does not automatically grant permission to open all referenced artifacts.

Artifact access must continue to honor the relevant authorization boundary.

## Meridian Handoff Boundary

Quillan provides an explicit teacher-facing workflow for making Academic Results available to Meridian through Core.

Quillan does not directly push records into Meridian and does not depend on Meridian for canonical Quillan operation.

The security boundary is:

```text
Quillan
  -> producer-native state
  -> immutable Academic Result Manifest
  -> Core Publication Record

Meridian
  -> Core publication discovery
  -> authorization
  -> exact manifest verification
  -> Quillan public reader
  -> Meridian-owned evidence projection
```

Quillan must not infer Meridian authorization, ingestion, policy, proficiency, grading, reporting, or disclosure decisions.

Meridian remains responsible for its own consumer-side authorization and interpretation layers.

## Standards and Educational Interpretation

Quillan may record standards-related assignment configuration, observations, and ratings.

These records must not be overstated.

Preserve the following distinctions:

```text
assignment Focus Standard
!= evidence that every submission demonstrates the standard

standard applicability
!= evidence presence

evidence presence
!= observation rating

observation rating
!= calculated proficiency

overall native standard rating
!= Meridian proficiency

unrated
!= low proficiency

producer-declared standards alignment
!= consumer-approved standards evidence association
```

Quillan must not silently transform a native standards rating into a Grade, proficiency conclusion, or downstream policy decision.

Those calculations, where supported, belong to the explicitly authorized consumer responsible for them.

## Review and Feedback Boundaries

Teacher review state is canonical Quillan workflow state.

Quillan must not infer completion or educational meaning from incidental file presence alone.

Preserve distinctions such as:

```text
scan received
!= valid submission

assembled submission
!= review started

review started
!= review complete

review complete
!= feedback exported

feedback exported
!= student receipt

teacher feedback
!= final Grade
```

A generated feedback artifact may contain sensitive student writing, teacher comments, standards information, and other education records.

Protect exported feedback accordingly.

Assignment-level feedback batches are sensitive teacher-facing containers.
The combined print packet must never be sent wholesale to one student, and the
sharing ZIP must be opened so its individual PDFs can be distributed to the
correct students. Both artifact types remain inside the teacher-controlled PDS
workspace and must not be committed to this repository.

## Scan and Paper-Workflow Security

Quillan may process scans, PDFs, generated forms, PDS2 pages, QR-coded pages, and routed physical-work evidence.

Security-sensitive scan processing should:

* reject unsafe path traversal;
* avoid silently reading outside intended workspace roots;
* preserve source provenance;
* avoid overwriting canonical source evidence without an explicit contract;
* distinguish retained source evidence from derived files;
* avoid assuming that machine-readable identity proves educational authorship;
* preserve scan-review and ambiguity states;
* avoid silently selecting among conflicting or duplicate physical evidence;
* fail safely when routing or identity cannot be established; and
* prevent sensitive page images from appearing unnecessarily in logs or diagnostics.

A QR code, page identifier, student identifier, or routed page reference does not by itself establish authorization to disclose the page contents.

## Identity Boundaries

Student identity should use documented Core and Quillan identity contracts.

Do not infer identity from:

* display-name similarity;
* filename similarity;
* handwritten names alone;
* scan order;
* directory position;
* fuzzy text matching;
* feedback filename;
* or other incidental characteristics.

Identity resolution must preserve the exact authority and provenance defined by the relevant workflow.

Knowing a student ID does not itself authorize access to that student's writing or feedback.

## Authorization

Quillan may participate in authorization-gated publication and artifact workflows.

The following must not be treated as authorization by themselves:

* possession of a path;
* possession of a student ID;
* possession of an assignment ID;
* possession of a publication ID;
* knowledge of a manifest path;
* knowledge of a digest;
* filesystem readability;
* publication discovery;
* package installation;
* producer-profile compatibility;
* matching student identity;
* manifest validity; or
* a caller-supplied purpose string.

Where authorization is required, missing authorization must fail closed.

## Paths and Filesystem Safety

Quillan persists and reads potentially sensitive records and artifacts from Paper Data Suite workspaces.

Filesystem-sensitive implementation should:

* reject traversal outside intended roots;
* use documented Core workspace/path services where appropriate;
* avoid treating string-prefix comparison as filesystem containment;
* avoid unsafe following of links or filesystem redirection;
* avoid destructive overwrite unless explicitly permitted;
* preserve immutable or revisioned records where required;
* avoid exposing unnecessary absolute paths;
* guard staged or temporary writes;
* clean incomplete state safely where possible; and
* treat filesystem state as potentially changing between validation and mutation.

A valid or readable path does not itself establish permission to access the referenced content.

## Integrity, Hashes, and Provenance

Quillan uses SHA-256 and other exact identity mechanisms in publication, artifacts, source provenance, and release qualification.

A matching digest demonstrates agreement with the expected bytes.

It does not provide:

* encryption;
* confidentiality;
* access control;
* proof of educational correctness;
* proof of authorship;
* proof of legal authority;
* proof that the source was trustworthy; or
* a digital signature unless an explicitly documented signed-verification mechanism is used.

Do not describe ordinary hash verification as stronger assurance than it provides.

## Backups and External Storage

Quillan data stored inside the canonical Paper Data Suite workspace is included in suite-level whole-workspace backup according to the suite backup contract.

Backups may contain the same sensitive information as the live workspace.

When production data or backups are placed in:

* OneDrive;
* Google Drive;
* Dropbox;
* network shares;
* removable drives;
* institutionally managed storage; or
* other externally synchronized locations,

provider-specific synchronization, encryption, remote access, sharing, retention, account compromise, and recovery behavior belong to that external storage system.

Quillan does not make a storage location appropriate merely because it is technically accessible.

Use only teacher-controlled or institutionally approved storage suitable for the data involved.

## Dependencies and Security Updates

Dependencies should remain minimal and deliberate.

Security-related dependency changes should be:

* reviewed before merge;
* tested against supported environments;
* evaluated for behavioral and packaging impact;
* reflected in compatibility/release qualification where required; and
* documented when they materially change security-sensitive behavior.

Do not assume that an older checkout or previously working dependency combination remains supported.

The currently qualified Quillan release must be evaluated against the Core dependency boundary and exact release-qualification procedures documented by the project.

## Release and Artifact Integrity

Supported release artifacts should be produced and distributed through the documented Quillan release process.

Where exact wheel identity, checksums, compatibility verification, or installed-wheel acceptance are part of release qualification:

* verify the expected artifact;
* fail closed on mismatches;
* do not silently substitute a source checkout;
* do not treat a broad dependency range as proof that every matching version was release-qualified;
* distinguish development source from supported release artifacts; and
* preserve exact candidate/release identity during qualification.

A package that imports successfully is not necessarily the package that was qualified.

## Reporting a Vulnerability

Do not disclose sensitive vulnerability details in a public GitHub issue.

For suspected security vulnerabilities, use GitHub Private Vulnerability Reporting for this repository when available.

A private vulnerability report should contain only the minimum information necessary to reproduce and assess the problem:

* affected Quillan version, branch, or commit;
* affected component or workflow;
* concise description;
* reproduction steps;
* expected behavior;
* observed behavior;
* potential impact;
* prerequisites or required permissions;
* suggested mitigation, if known; and
* current disclosure status.

Do not include real student data, production workspace contents, real scans, real writing, credentials, private school or district material, or unrelated sensitive information.

If GitHub Private Vulnerability Reporting is unexpectedly unavailable, do not disclose exploit details publicly. Open only a non-sensitive issue stating that a private security-reporting channel is needed.

## Reporting Non-Sensitive Security or Privacy Concerns

Public GitHub Issues may be used for non-sensitive:

* security-hardening suggestions;
* privacy-design questions;
* synthetic-data concerns;
* documentation gaps;
* dependency-maintenance concerns;
* workflow-integrity questions; and
* data-safety issues that can be described without exploit-sensitive or private information.

Do not include real student records, credentials, scans, production workspace contents, or sensitive deployment information in a public issue.

## Security-Sensitive Areas

Reports are particularly appropriate for demonstrated problems involving:

* unauthorized access to student writing;
* unauthorized access to feedback or reports;
* publication-authorization bypass;
* manifest-access bypass;
* artifact-access bypass;
* fail-open authorization behavior;
* path traversal;
* workspace escape;
* unintended overwrite or deletion;
* unsafe scan or PDF handling;
* incorrect physical-page routing;
* identity confusion that exposes another student's work;
* inappropriate cross-student data association;
* unsafe temporary-file handling;
* publication or manifest integrity failures;
* digest-verification bypass;
* package or release-artifact substitution;
* source-checkout shadowing that defeats installed-package verification;
* command injection;
* CI credential disclosure;
* unintended filesystem mutation during read-only or diagnostic operations;
* sensitive student data appearing in logs, diagnostics, screenshots, or exceptions;
* incorrect cross-module writes;
* publication state being treated as authorization;
* standards ratings being silently promoted to Grades or proficiency;
* review state being inferred incorrectly from file presence; or
* any workflow that collapses a documented privacy, provenance, ownership, or authorization boundary.

## Good-Faith Security Research

Good-faith security testing should:

* use synthetic data;
* use systems, accounts, workspaces, and files you are authorized to access;
* minimize access to unrelated information;
* stop if real sensitive data is encountered;
* avoid persisting sensitive data;
* avoid modifying or destroying data unnecessarily;
* avoid disrupting classroom or institutional systems;
* report vulnerabilities privately;
* allow maintainers a reasonable opportunity to investigate and correct the issue before public disclosure; and
* comply with applicable law and organizational policy.

Do not test against students, teachers, schools, districts, accounts, systems, or records you do not have permission to access.

This policy does not authorize activity against third-party systems.

## Out of Scope

The following are not security vulnerabilities by themselves:

* disagreement with an explicitly configured teacher review;
* disagreement with a rubric or standards interpretation;
* disagreement with future grading policy;
* an `unrated` native state;
* unsupported deployment configurations;
* unsupported historical versions;
* missing product features;
* expected differences between Quillan-native ratings and downstream Meridian calculations;
* a publication that has not yet been ingested by Meridian;
* a workflow requiring explicit teacher confirmation; or
* hypothetical vulnerabilities unsupported by demonstrable repository behavior.

Security reports should identify a concrete confidentiality, integrity, authorization, provenance, availability, or unsafe-execution concern.

## Scope

This policy applies to the `pds-quillan` repository, supported Quillan package artifacts, and Quillan-owned workflows and records.

PDS Core remains responsible for its documented shared infrastructure and contracts.

Other Paper Data Suite modules remain responsible for their own canonical records, authorization requirements, policies, outputs, and security-sensitive workflows.

Quillan must preserve those ownership boundaries when integrating with Core, Meridian, or any other module.

## Compliance

Quillan and Paper Data Suite are software tools, not legal determinations that a particular deployment satisfies FERPA, state student-privacy laws, district policy, records-retention requirements, accessibility requirements, or other institutional obligations.

Teachers, administrators, developers, and deploying organizations remain responsible for determining and following the requirements applicable to their use.

This policy describes repository security intent and supported project practices. It is not legal advice.
