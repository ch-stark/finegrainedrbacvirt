# Companion example for Govern tenant VM access across clusters

This example accompanies [Govern VM access across clusters with ACM 5.0](../virtrbacblog_v2.md). Its product baseline is ACM 5.0. The generated policy starts with assignments disabled; it does not grant tenant access until you explicitly enable that policy and deploy the resulting change.

## Repository reference

The public [Full Admin Fleet Virtualization RBAC README](../examplefulladmin/README.md) documents the separate `examplefulladmin/` deployment. Its wildcard role and unscoped assignment grant cluster-admin-equivalent access. This companion directory implements the blog's namespace-scoped tenant model and uses different paths and role names.

## What was checked locally

On 10 November 2026, the example rendered successfully with Kustomize v5.8.1 and upstream PolicyGenerator v1.19.0. These describe the local authoring tools, not a Red Hat support certification for that combination.

Checks passed for all three MRA manifests against the upstream v1beta1 CRD, all five assignments having explicit namespaces, separate hub and spoke routing, no PolicySet placement binding, identical role definitions at both destinations, strict role-rule compliance, namespace coexistence, object retention, and the disabled assignment gate. The authorization script passed syntax validation.

The included `rendered/vm-rbac.yaml` is a local review artifact for the first stage. Rebuild it when editing the source. The Application points at `vm-rbac-example/` and runs PolicyGenerator inside the configured Argo CD repository server; it does not synchronize the `rendered/` directory.

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
9. Configure and verify the Argo CD init container, plugin mount, build options, controller permissions, and AppProject. Test both rollout stages through source-based GitOps delivery.

Add a short tested-environment note and verified results to the blog after these pass. Do not invent console screenshots, timings, customer outcomes, or cluster-test results.

## Run the example

Follow the blog in order. Commands are run from this directory. Replace HUB and SPOKE with actual kubeconfig context names. The `default` managed cluster set must already exist and contain the hub and selected managed clusters; use a different set consistently if needed.

## Configure PolicyGenerator in Argo CD

Follow the documented [ACM 5.0 GitOps policy integration](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html-single/gitops). Apply bootstrap first to create the `policies` namespace and hub/spoke placements.

For a direct configuration change, review `gitops/argocd-policygenerator-patch.yaml`. Preserve any existing repository environment variables, init containers, mounts, volumes, and build options by merging them into the patch before applying it; JSON merge patches replace arrays.

```bash
oc --context HUB patch argocd openshift-gitops -n openshift-gitops \
  --type=merge --patch-file=gitops/argocd-policygenerator-patch.yaml
oc --context HUB apply -f gitops/controller-policy-rbac.yaml
oc --context HUB rollout status deployment/openshift-gitops-repo-server \
  -n openshift-gitops
```

The patch installs the binary from the ACM 5.0 image, mounts its plugin directory, sets `KUSTOMIZE_PLUGIN_HOME`, and configures `kustomizeBuildOptions: --enable-alpha-plugins`. Adjust instance names and registry access for your environment. The Role and RoleBinding grant the application controller access to policy resources in `policies`; bootstrap creates placements separately.

Alternatively, apply `gitops/policy-openshift-gitops-policygenerator.yaml` directly with `oc`. This adaptation of the community [PolicyGenerator integration policy](https://github.com/open-cluster-management-io/policy-collection/blob/main/community/CM-Configuration-Management/policy-openshift-gitops-policygenerator.yaml) configures the same ArgoCD resource and controller permissions through governance. It starts in `inform` mode and binds only to `vm-rbac-hub`. Review its differences, change the parent Policy to `enforce`, and wait for compliance and the repository-server rollout. Choose this policy or the direct patch route to manage the integration.

These setup files are deliberately outside the workload generator inputs. Apply them directly before creating the workload Application.

## Deploy the source through Argo CD

`application.yaml` points at this repository's `vm-rbac-example` Kustomization. Set its reviewed commit SHA and adjust the source repository in both the Application and AppProject if deploying from a fork.

```bash
oc --context HUB apply -f appproject.yaml
oc --context HUB apply -f application.yaml
```

Manually sync the Application with `vm-rbac-hub-assignments` disabled. Confirm role and namespace compliance on every selected cluster, then commit the change to `disabled: false`, update the Application revision to that reviewed commit, and manually sync again. Argo CD runs PolicyGenerator for each source revision.

## Render locally for review

For a local preview, install a reviewed PolicyGenerator executable at:

```text
$KUSTOMIZE_PLUGIN_HOME/policy.open-cluster-management.io/v1/policygenerator/PolicyGenerator
```

Then run:

```bash
mkdir -p rendered
kustomize build --enable-alpha-plugins . > rendered/vm-rbac.yaml
```

This local preview does not configure the Argo CD repository server. The Argo CD integration above is required for the source-based Application.

The examples retain objects when policy is deleted. Follow the blog's explicit `mustnothave` transition for tenant revocation. Do not delete tenant namespaces as a shortcut for revoking permissions.
