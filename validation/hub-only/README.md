# Hub-only live validation overlay

This overlay is for the explicitly authorized single-cluster test. It changes workload placement to `local-cluster` and disables the separate hub-role policy so one baseline policy manages the custom roles on that cluster. The original multi-cluster example is unchanged.

The placement retains the name `vm-rbac-spokes` because the original assignments reference it, but it selects the hub only in this test. The assignments remain disabled in stage one. The test environment runs ACM 5.1 development builds on OpenShift 5.0.1; it is not ACM 5.0 certification or a multi-cluster test.

Apply this directory's bootstrap separately. Point an Argo CD Application at `validation/hub-only` to render the source with PolicyGenerator. Live observations and limitations are recorded after testing.
