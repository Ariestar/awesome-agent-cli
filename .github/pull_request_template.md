## Summary
<!-- Briefly describe the tool you are adding or the changes in this PR -->

- **Tool Name**: 
- **Binary**: 
- **Primary Category**: 
- **Homepage / Repo**: 

---

## Contribution Rules & Checklist

Please ensure your contribution satisfies the following requirements before submitting:

- [ ] **No manual README edits**: `README.md` is generated automatically by CI. Only add or edit files under `data/tools/<tool-name>.yaml`.
- [ ] **Exact file naming**: The YAML file must be named `data/tools/<tool-name>.yaml` and the `name` field inside must strictly match the filename (lowercase, kebab-case, no spaces or uppercase).
- [ ] **Allowed effects**: All items in `risk.effects` come strictly from the allowed whitelist:
  `cloud_mutation`, `container_mutation`, `delete_files`, `deployment`, `environment_mutation`, `execute_code`, `install_packages`, `network_access`, `read_files`, `read_processes`, `remote_read`, `remote_write`, `requires_auth`, `secret_exposure`, `vcs_mutation`, `write_files`.
- [ ] **Guardrails**: High-risk tools (`risk.level: high`) must define concrete `guardrails`.
- [ ] **Local validation passed**:
  ```bash
  python scripts/lint_registry.py
  python scripts/generate_readme.py
  ```
