# ACM 5.0 VM access reference implementation

This runbook accompanies [Govern VM access with ACM 5.0](../virtrbacblog_v2.md). It implements three permission tiers for separate example teams. The namespaces, groups, and file names retain the `tenant-a`, `tenant-b`, and `tenant-c` identifiers used in the manifests.

The source snapshot is tagged `acm5-rbac-reference-v2`. The article links to that snapshot; use a new reviewed commit for your deployment changes. The assignment policy starts disabled. There are no recorded live ACM results for this reference implementation; the [validation record](validation-results.md) distinguishes local checks from pending cluster tests.

## File map

| Path | Purpose |
| --- | --- |
| `bootstrap.yaml` | Management namespace, cluster-set binding, hub/spoke placements |
| `roles/` | One source for both custom role definitions |
| `namespaces/` | Managed-cluster workload namespaces |
| `assignments/` | Hub MRA objects with explicit target namespaces |
| `fleet-access/` | Hub fleet-console bindings |
| `policy-generator.yaml`, `kustomization.yaml` | Governance generation and routing |
| `gitops/` | Argo CD patch, scoped controller RBAC, alternative setup policy |
| `application.yaml`, `appproject.yaml` | Source-based GitOps delivery |
| `rendered/vm-rbac.yaml` | Local first-stage review output |
| `verify-access.py` | Managed-cluster authorization queries |
| `validation-results.md` | Environment and operational evidence template |

The separate [full-admin example](../examplefulladmin/README.md) grants cluster-admin-equivalent access through a wildcard role and unscoped assignment. It is a different permission model.

## Prepare the environment

Follow the [ACM 5.0 virtualization RBAC setup](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html/secure_clusters/securing-cluster-intro#fine-grain-enable) and [support matrix](https://access.redhat.com/articles/7149098). Configure governance and the `fine-grained-rbac` component. Preserve existing component entries when merging the setting.

Keep the self-managed hub named `local-cluster`; this reference does not support renaming that object. Install supported OpenShift Virtualization on the hub and targets, align identities and memberships, and confirm the built-in roles exist. This design excludes hub-hosted VMs from the workload grants.

Commands below run from `vm-rbac-example/`. Replace `HUB` and `SPOKE` with kubeconfig contexts. Use an administrator for setup, with authorization to impersonate test identities for validation.

```bash
oc --context HUB api-resources --api-group=rbac.open-cluster-management.io
oc --context HUB explain multiclusterroleassignment.spec \
  --api-version=rbac.open-cluster-management.io/v1beta1
```

The existing `default` managed cluster set must contain the hub and selected targets. If it does not, adapt both the set reference and binding. Apply bootstrap and opt in only intended clusters:

```bash
oc --context HUB apply -f bootstrap.yaml
oc --context HUB label managedcluster managed-cluster-01 \
  example.com/vm-rbac=enabled
oc --context HUB get placementdecision -n policies -o yaml
```

Check exact decisions for both placements. `vm-rbac-hub` must select only `local-cluster`; `vm-rbac-spokes` must select only approved targets. The `example.com` label prefix is illustrative and valid; change the label and selector together if using your own prefix.

## ACM 5.0 configuration references

The [ACM 5.0 feature setup procedure](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html/secure_clusters/securing-cluster-intro#fine-grain-enable) enables an entry with `name: fine-grained-rbac` and `enabled: true` in `spec.overrides.components`.

The [ACM 5.0 MRA examples](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html/secure_clusters/securing-cluster-intro#fine-grain-mca-examples) use `dev-virt` and `prod-virt` as management namespaces. This reference uses `policies`; workload namespace scope remains explicit in each assignment's `targetNamespaces`. Validate reconciliation and console discovery in the deployed environment using the results record.

Snapshot refs named `acm5-rbac-reference-v*` are annotated tags, not branches. Keep each published tag fixed; create a new tag when revising the article and linked companion files.

## Configure PolicyGenerator in Argo CD

This is the primary setup path. Follow the documented [ACM 5.0 GitOps policy integration](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html-single/gitops). Configure the `ArgoCD` custom resource; the GitOps operator manages the repository-server Deployment.

The [patch file](gitops/argocd-policygenerator-patch.yaml) contains:

```yaml
spec:
  kustomizeBuildOptions: --enable-alpha-plugins
  repo:
    env:
    - name: KUSTOMIZE_PLUGIN_HOME
      value: /etc/kustomize/plugin
    initContainers:
    - name: policy-generator-install
      image: registry.redhat.io/rhacm2/multicluster-operators-subscription-rhel9:v5.0
      command:
      - /bin/bash
      args:
      - -c
      - cp /policy-generator/PolicyGenerator-not-fips-compliant /policy-generator-tmp/PolicyGenerator
      volumeMounts:
      - name: policy-generator
        mountPath: /policy-generator-tmp
    volumeMounts:
    - name: policy-generator
      mountPath: /etc/kustomize/plugin/policy.open-cluster-management.io/v1/policygenerator
    volumes:
    - name: policy-generator
      emptyDir: {}
```

The documented binary is copied from the ACM 5.0 subscription image into a shared volume. The repository server receives the plugin path and `--enable-alpha-plugins` build option. Ensure the image can be pulled. Adapt Argo CD instance names, namespace, and service-account references where needed.

Inspect existing `spec.repo` lists and `spec.kustomizeBuildOptions` first. A JSON merge patch replaces arrays: merge existing environment variables, init containers, mounts, volumes, and build flags into the patch file before applying it.

```bash
oc --context HUB patch argocd openshift-gitops -n openshift-gitops \
  --type=merge --patch-file=gitops/argocd-policygenerator-patch.yaml
oc --context HUB apply -f gitops/controller-policy-rbac.yaml
oc --context HUB rollout status deployment/openshift-gitops-repo-server \
  -n openshift-gitops
```

Confirm the operator has reconciled the changed ArgoCD resource and that the new repository-server pod's `policy-generator-install` init container completed. A rollout command that returns before reconciliation starts is not sufficient evidence of the new configuration. Inspect the new pod's init-container status and mounted configuration if generation fails.

The [controller Role and RoleBinding](gitops/controller-policy-rbac.yaml) are a deliberate narrowing of the documentation's cluster-wide example. They grant access to `Policy`, `PolicySet`, and `PlacementBinding` resources only in `policies`. Bootstrap resources are applied separately by the administrator, so the controller does not need to create placements or administer workload RBAC for this example.

## Configure the integration with a governance policy

You can also govern the Argo CD configuration itself. The community [OpenShift GitOps PolicyGenerator policy](https://github.com/open-cluster-management-io/policy-collection/blob/main/community/CM-Configuration-Management/policy-openshift-gitops-policygenerator.yaml) shows this pattern: a ConfigurationPolicy configures the ArgoCD resource and supplies application-controller permissions. Its init container obtains the binary from the ACM CLI image using a template lookup.

The companion [setup policy](gitops/policy-openshift-gitops-policygenerator.yaml) adapts that approach for this walkthrough. It uses the ACM 5.0 image and copy command shown above, the namespace-scoped controller permissions, and a PlacementBinding targeting only `vm-rbac-hub`. It starts in `inform` mode for review.

Use this policy **instead of the direct patch commands** when you want governance to manage the integration:

```bash
oc --context HUB apply -f gitops/policy-openshift-gitops-policygenerator.yaml
oc --context HUB get policy vm-rbac-policygenerator-setup -n policies -o yaml
```

Review the reported differences against your existing Argo CD configuration. Then enforce the reviewed configuration and wait for compliance and the repository-server rollout:

```bash
oc --context HUB patch policy vm-rbac-policygenerator-setup -n policies \
  --type=merge -p '{"spec":{"remediationAction":"enforce"}}'
oc --context HUB wait policy/vm-rbac-policygenerator-setup -n policies \
  --for=jsonpath='{.status.compliant}'=Compliant --timeout=5m
oc --context HUB rollout status deployment/openshift-gitops-repo-server \
  -n openshift-gitops
```

Apply this setup policy directly with `oc`: it is ordinary policy YAML and does not require an already-configured PolicyGenerator. Keep it outside the workload generator's manifest inputs.

## Deploy the source through Argo CD

The [Application](application.yaml) points to this repository's `vm-rbac-example` Kustomization. Set `targetRevision` to the reviewed commit SHA. If using a fork, update the repository in both the Application and [AppProject](appproject.yaml). You can identify your checked-out source commit with:

```bash
git rev-parse HEAD
```

Argo CD runs PolicyGenerator in its configured repository server. The `rendered/` subdirectory is a local preview, not the Application source. Create the project and Application:

```bash
oc --context HUB apply -f appproject.yaml
oc --context HUB apply -f application.yaml
```

Keep synchronization manual for both rollout stages.

### Stage one deploys roles and namespaces

Leave `vm-rbac-hub-assignments` disabled. Render locally if desired, validate the output against the hub API, and manually sync the Application:

```bash
oc --context HUB apply --dry-run=server -f rendered/vm-rbac.yaml
```

If source changes were made, regenerate the local output before validating it. After Argo CD synchronization, inspect the baseline on every selected managed cluster:

```bash
oc --context HUB get policy vm-rbac-spoke-baseline -n policies -o yaml
oc --context HUB get policy vm-rbac-hub-roles -n policies -o yaml
oc --context SPOKE get clusterrole custom-vm-lifecycle custom-vm-maintainer
oc --context SPOKE get namespace \
  tenant-a-namespace tenant-b-namespace tenant-c-namespace
oc --context SPOKE get clusterrole kubevirt.io:view -o yaml
```

Confirm that the hub role definitions also exist. Inspect per-cluster policy compliance; Argo CD `Synced` status alone does not verify propagation.

### Stage two grants access

Once the baseline is ready, change the assignment policy from `disabled: true` to `disabled: false`. Review, commit, and push that source change. Update the Application to the new reviewed commit SHA, then manually sync it.

Validate the assignment files against the installed API and inspect the result:

```bash
oc --context HUB apply --dry-run=server -f assignments/
oc --context HUB get multiclusterroleassignments -n policies -o yaml
oc --context SPOKE get rolebindings -n tenant-b-namespace -o yaml
```

For every MRA, inspect status and cluster selection. For every generated RoleBinding, inspect the subject, role reference, and namespace. Do not assume a generated resource name. In addition, confirm that the hub console bindings reference only `acm-vm-fleet:view` for the intended groups.

The [policy health-check example](https://github.com/open-cluster-management-io/policy-collection/blob/main/stable/CM-Configuration-Management/argocd-policy-healthchecks.yaml) can improve policy status shown in Argo CD. It does not replace direct downstream validation.

## Render locally for review

The source previously rendered with Kustomize v5.8.1 and upstream PolicyGenerator v1.19.0. Those are authoring-tool versions, not a Red Hat support certification of the combination or a live test of the ACM image.

Install a reviewed executable at:

```text
$KUSTOMIZE_PLUGIN_HOME/policy.open-cluster-management.io/v1/policygenerator/PolicyGenerator
```

Then run:

```bash
mkdir -p rendered
kustomize build --enable-alpha-plugins . > rendered/vm-rbac.yaml
```

Confirm that the hub policy bindings reference `vm-rbac-hub`, the spoke baseline references `vm-rbac-spokes`, and no PlacementBinding targets the PolicySet. The setup-policy files under `gitops/` are deliberately outside the workload generator inputs.

This preview does not configure Argo CD. The repository-server integration above is required for the source-based Application.

## Validate workload and console access

Run authorization queries on every target:

```bash
python3 verify-access.py SPOKE
```

The script checks a synthetic identity with a specified group list. Repeat checks as real users with their actual memberships; permissions from other bindings are additive. The script submits explicit SelfSubjectAccessReview attributes, including API group and subresource, so client discovery cannot reinterpret the lifecycle endpoints. A nonzero script exit means at least one observed result differed from its expectation. Use `--results FILE` to record details. The hub-only overlay uses `--hub-only`, which expects namespace listing from the separate hub fleet-console grant; do not use that flag for a spoke-only test.

Use disposable VMs to exercise lifecycle actions and approved VM creation/editing. Authorization success alone does not establish successful storage, networking, or admission. Include the maintainer's permitted storage and data references in your review, and add environment-specific admission controls as needed.

Sign in through the hub as each real user. Check fleet inventory, search by another team's known VM name and namespace, and open a saved direct details link. Other teams' VM data must not be exposed. Record separately whether cluster names, namespace names, resource counts, or other metadata are visible. Compare those observations with an explicitly approved metadata-visibility requirement; namespace RBAC alone is not proof that all fleet metadata is confidential.

Verify MRA visibility and reconciliation in `policies`, record the exact installed `acm-vm-fleet:view` definition, and record results in [validation-results.md](validation-results.md). If console or search visibility exceeds the requirement, resolve it before accepting the design for that environment.

## Troubleshoot the layer that failed

| Symptom | Check |
| --- | --- |
| Generator cannot load in Argo CD | Init-container completion, image pull access, executable volume mount, `KUSTOMIZE_PLUGIN_HOME`, and `kustomizeBuildOptions: --enable-alpha-plugins` |
| Placement selects no clusters | Cluster set membership, its namespace binding, opt-in labels, cluster health, and PlacementDecision objects |
| Role differs on a managed cluster | Spoke policy compliance and its ConfigurationPolicy messages; check for another controller managing the same role |
| Role is missing from the console | Hub role existence, required labels, feature configuration, and the user's hub console binding |
| Assignment fails or grants nothing | Installed MRA schema, assignment status, referenced placement, role existence, and target namespace existence |
| User has too much access | Actual identity-provider groups, all RoleBindings and ClusterRoleBindings, and any assignment with empty target namespaces |
| Authorization succeeds but VM operation fails | Exact failing API request, admission messages, workload state, and storage or network prerequisites |

## Onboard and revoke access

For a new tenant, create its namespace manifest, group-specific assignment, and hub fleet-access binding. Add the namespace to the spoke baseline and both hub files to the assignment policy. Deploy the namespace first, then the assignment, and extend the authorization tests before promotion.

For revocation, keep the relevant files in the generator and temporarily set `complianceType: mustnothave` on that tenant's assignment and fleet-access manifest entries. For Tenant B, those entries become:

```yaml
- path: assignments/tenant-b.yaml
  complianceType: mustnothave
- path: fleet-access/tenant-b.yaml
  complianceType: mustnothave
```

Commit this source change, update the Application to the reviewed commit SHA, and sync the transition while the assignment policy remains enabled. Verify deletion of the hub MRA and hub console binding, then confirm that the MRA controller has removed the managed-cluster bindings and that access checks now deny the former grants. Account for other bindings and group memberships when interpreting those checks.

Only after confirming revocation should you remove those entries and files. Retain tenant namespaces and workloads until a separate approved offboarding process handles them. Removing a file or disabling a policy alone does not revoke existing access with the retention settings in this example.

Keep managed clusters reachable during planned revocation and verify the outcome on each one. Treat placement changes as access changes, including checks for permissions left on previously selected clusters.
