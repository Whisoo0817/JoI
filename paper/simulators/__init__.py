"""Service catalog + expression helpers shared by the IR and lowering stages.

`catalog.load_catalog()` reads files/service_list_ver*.json and backs the
`validate_ir_against_catalog` check in the IR-extract retry loop.
`expr` provides the canonical service/method name normalization used by both
the catalog and `paper.timeline_ir`.
"""
