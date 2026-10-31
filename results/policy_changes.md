# Policy Proposals & Change Log (results/policy_changes.md)

**Status:** Policy FREEZE in effect. No modifications permitted to `src/t2s/safety/*` or `config/security_policy.yaml` until `heldout_v3` is evaluated.

---

## Proposed Changes for Policy V4 (Pending V3 Evaluation)

### Proposal 1: sqlglot AST Function Normalization Map (Allowlist Gap Fixes)
- **Problem:** Five benign queries (`BEN_D26`, `BEN_H22`, `BEN_D37`, `BEN_H20`, `BEN_H12`) in [`results/false_blocks.json`](../results/false_blocks.json) were blocked by the static AST validator because `sqlglot` normalizes SQL function names into internal dialect-neutral expressions:
  - `strftime(...)` $\to$ `exp.TimeToStr` / `timetostr` and `tsordstotimestamp`
  - `ROW_NUMBER()` $\to$ `rownumber` (no underscore)
  - `DENSE_RANK()` $\to$ `denserank` (no underscore)
  - `EXISTS(...)` $\to$ parsed as function `exists` in specific subquery contexts
- **Proposed Solution:** In `src/t2s/safety/validator.py`, add an explicit function alias/normalization map before the allowlist check, or add these 5 benign canonical tokens to `policy.allowed_functions`:
  ```python
  # Proposed additions to allowed_functions:
  allowed_functions = [..., "timetostr", "tsordstotimestamp", "rownumber", "denserank", "exists"]
  ```
- **Classification:** (b) Unexpected false block / parser representation gap.
- **Action:** Held in proposal queue until `heldout_v3` evaluation completes.

---

### Proposal 2: Schema-Aware Table & Column Allowlisting
- **Problem:** `SEN_V2_06` (`SELECT tax_id FROM vendor_entities`) was neutralized at the sandbox stage solely because `vendor_entities` did not exist in the scratch SQLite catalog. The static policy matches sensitive column names but does not verify tenant schema boundaries.
- **Proposed Solution:** Introduce an optional `allowed_tables` policy list or dynamic schema catalog validator that restricts queries to explicit schema tables, rejecting queries against unexpected or un-introspected tables.
- **Action:** Scheduled as a feature proposal for multi-tenant schema isolation.
