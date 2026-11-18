# Hub-only live validation overlay

This overlay is for the explicitly authorized single-cluster test. It changes workload placement to `local-cluster` and disables the separate hub-role policy so one baseline policy manages the custom roles on that cluster. The original multi-cluster example is unchanged.

The placement retains the name `vm-rbac-spokes` because the original assignments reference it, but it selects the hub only in this test. The current overlay is the restored stage-two configuration, with assignments enabled. The initial disabled-grant state is preserved in commit `5c84367`. The test environment runs ACM 5.1 development builds on OpenShift 5.0.1; it is not ACM 5.0 certification or a multi-cluster test.

Apply this directory's bootstrap separately. Point an Argo CD Application at `validation/hub-only` to render the source with PolicyGenerator. See [live results and limitations](results.md). The checker uses `--hub-only` because the separate hub fleet role grants namespace listing.
