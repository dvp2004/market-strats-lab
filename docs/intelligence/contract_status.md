# Intelligence Contract Status

Versioned MI design and preregistration contracts are preserved as historical evidence. A field
such as `design_only: true`, `not_implemented`, or `not_started` records the status when that
contract was frozen; it must not be read as the current repository implementation status.

The current machine-readable mapping is
`configs/intelligence/mi_current_status_v1.yaml`. It records the SHA-256 identity of every migrated
configuration and each corresponding implementation file. Hashes use text bytes with LF line
endings so identities remain stable across Git checkouts on Windows and Linux.

The consolidation review establishes:

- the MI-2 prospective source adapter is implemented and covered by portable tests;
- the MI-2 prospective snapshot runner is implemented and covered by portable tests;
- the scorecard contract's three parent-configuration hashes are resolved;
- no current prospective scorecard evaluator exists;
- real prospective observation has not started;
- no technical family is qualified;
- portfolio influence remains zero.

The historical model-identity hashes embedded in frozen contracts are not silently replaced with
post-migration file hashes. The current mapping records the consolidated file identities without
claiming that a package-path migration re-froze the research model.
