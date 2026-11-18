# Companion example for Govern tenant VM access across clusters

This example accompanies [Govern VM access across clusters with ACM 5.0](../virtrbacblog_v2.md). Its product baseline is ACM 5.0. The generated policy starts with assignments disabled; it does not grant tenant access until you explicitly enable that policy and deploy the resulting change.

## Repository reference

The public [Full Admin Fleet Virtualization RBAC README](../examplefulladmin/README.md) documents the separate `examplefulladmin/` deployment. Its wildcard role and unscoped assignment grant cluster-admin-equivalent access. This companion directory implements the blog's namespace-scoped tenant model and uses different paths and role names.

## What was checked locally

On 10 November 2026, the example rendered successfully with Kustomize v5.8.1 and upstream PolicyGenerator v1.19.0. These describe the local authoring tools, not a Red Hat support certification for that combination.

Checks passed for all three MRA manifests against the upstream v1beta1 CRD, all five assignments having explicit namespaces, separate hub and spoke routing, no PolicySet placement binding, identical role definitions at both destinations, strict role-rule compliance, namespace coexistence, object retention, and the disabled assignment gate. The authorization script passed syntax validation.

The included `rendered/vm-rbac.yaml` is the first-stage output. Rebuild it whenever editing the source. The generated YAML is a build artifact; make permission changes in the source files.

## What must be validated on ACM 5.0 before publication or production use

No connected ACM environment was used. The following remain release gates for calling this a tested production implementation:

1. Record exact ACM, OpenShift, OpenShift Virtualization, GitOps, and build-tool versions. Verify the supported product combination.
2. Apply server-side validation against the installed CRDs. Confirm the feature configuration, governance add-ons, matching identities, and baseline roles.
3. Confirm cluster-set membership and PlacementDecision output; test first on one disposable managed cluster.
4. Confirm role and namespace policy compliance before enabling the assignment policy.
5. Run `python3 verify-access.py MANAGED_CONTEXT` on every target cluster with an authorized administrator identity. Record results. The script makes authorization queries; it does not perform VM operations.
6. Test real-user hub console access, CLI lifecycle operations, VM creation and modification with the intended storage/network workflow, and denied operations. Inspect audit records. A hidden button is insufficient evidence of denial.
7. Test revocation, including MRA deletion, downstream binding cleanup, and negative authorization checks. Verify access on previously targeted clusters after placement changes.
8. Test drift remediation on an example-owned custom role. Confirm no other policy or operator owns the same definition.
9. Replace deployment placeholders and review the AppProject and Argo CD controller permissions. Test both rollout stages through the intended GitOps delivery process.

Add a short tested-environment note and verified results to the blog after these pass. Do not invent console screenshots, timings, customer outcomes, or cluster-test results.

## Run the example

Follow the blog in order. Commands are run from this directory. Replace HUB and SPOKE with actual kubeconfig context names. The `default` managed cluster set must already exist and contain the hub and selected managed clusters; use a different set consistently if needed.

The plugin executable must be installed at:

```text
$KUSTOMIZE_PLUGIN_HOME/policy.open-cluster-management.io/v1/policygenerator/PolicyGenerator
```

Render with:

```bash
kustomize build --enable-alpha-plugins . > rendered/vm-rbac.yaml
```

The bundle does not include an executable plugin. Install a reviewed, pinned version in the build environment. Rendering policies does not require cluster credentials.

Apply bootstrap first. Deploy the initial policies, verify baseline compliance, then set `disabled: false` only for `vm-rbac-hub-assignments`, render again, and promote that reviewed output.

`application.yaml` and `appproject.yaml` use a placeholder repository URL. The Application also requires a reviewed commit SHA. Install them through your existing GitOps administration process after configuring the project and controller access. The Application reads only the `rendered` directory, so it does not ingest source templates or bootstrap resources.

The examples retain objects when policy is deleted. Follow the blog's explicit `mustnothave` transition for tenant revocation. Do not delete tenant namespaces as a shortcut for revoking permissions.
