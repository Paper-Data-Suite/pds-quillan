# Quillan Installed Module Profile and Dispatch

Quillan's zero-argument provider is
`quillan.pds_module:get_module_profile` in `paper_data_suite.modules`. It returns
module ID `quillan`, display name `Quillan`, Core routing contract `1`, QR schema
`PDS2`, route-registration schema `1`, active-only dispatch, the response-page
handler, and the strict registration validator.

The provider creates no registry, resolves no workspace, reads no records, and
imports no CLI or legacy scan path. Calls return equivalent immutable profiles.

The validator is structural. The handler defends direct calls, checks canonical
roots, loads the exact immutable page context, requires lifecycle `issued`, validates
retained provenance, and returns `QuillanResponsePageDispatchResult`. Current roster
and assignment files are deliberately irrelevant.

Retained provenance is accepted only when Core's public filename and path helpers can
reconstruct the exact recorded event. The aware timestamp generates the filename;
the independently supplied `intake_date` selects the path bucket and may explicitly
override the timestamp's date. Source filenames must be free of control and Unicode
line-separator characters. The public result validator repeats the same pure check
without filesystem access. The handler authorizes the immutable route and `issued`
issuance first, then adds nonfollowing ordinary-file and link-chain checks. Structural
registration validation requires the canonical `rt_<32 lowercase hex>` route ID.

An `active` Core registration is structurally resolvable; it does not authorize a
prepared, cancelled, superseded, or invalidated physical issuance. QR text, fallback,
route IDs, filenames, module details, scan order, and caller values never supply
student identity, logical-page identity, continuation meaning, or submission
membership. #337 neither decodes pages nor writes evidence. #338 owns intake and
source-page enumeration; #339 owns observations and submission assembly.

#338 builds a fresh installed `ModuleRegistry` per top-level file operation and
one per folder operation, requires the installed `quillan` profile, and preserves
all other valid discovered profiles. Ordered requests carry the exact Core-parsed
locator, retained-source object, and physical page number. Foreign module results
are never inspected by Quillan intake.
