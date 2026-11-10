# Govern tenant VM access across clusters with Red Hat Advanced Cluster Management

A virtual machine operator needs to restart an application server. A platform engineer needs to change its configuration. An auditor needs to inspect its state. Giving all three people the same virtualization role makes onboarding easy, but grants more access than their work requires.

The challenge grows when those responsibilities span several clusters. Manually maintained bindings are difficult to review consistently, and a successful deployment does not prove that access is limited to the intended tenant.

This walkthrough shows platform engineers how to keep custom virtual machine permissions in Git, distribute their definitions with Red Hat Advanced Cluster Management for Kubernetes (ACM) governance, and assign them to groups within specific namespaces. Three tenants illustrate maintenance, lifecycle operations, and read-only access.

The result is a repeatable access-management workflow: review the permission change, select the clusters, reconcile the roles, and verify both allowed and denied operations.

## Choose a documented product baseline

This example targets **ACM 2.17** and its documented custom-role workflow. Fine-grained RBAC for virtualization became generally available in **ACM 2.16**. Product support status comes from the release documentation; an API suffix such as `v1beta1` does not establish that status by itself. [ACM 2.16 release notes](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.16/html/release_notes/acm-release-notes)

Use an OpenShift Container Platform and OpenShift Virtualization combination supported by your ACM release. For ACM 2.16, review that release's configuration and upgrade guidance before adapting these examples. In particular, assignments carried forward from 2.15 can require recreation with explicit placement references. [ACM upgrade troubleshooting](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.16/html/troubleshooting/troubleshooting)

## Understand the control flow

The architecture has three responsibilities:

1. **Git and PolicyGenerator describe the desired state.** Kustomize runs PolicyGenerator to produce governance policies and their bindings.
2. **Governance distributes role definitions.** One policy targets the hub; another targets explicitly selected managed clusters, also called spokes. The spoke policy also creates tenant namespaces.
3. **Role assignments grant access.** Hub-side `MulticlusterRoleAssignment` resources reference roles, cluster placements, and target namespaces. Their controller creates the managed-cluster RBAC bindings. [MRA API definitions](https://github.com/stolostron/multicluster-role-assignment/blob/main/api/v1beta1/multiclusterroleassignment_types.go)

“Policy-to-UI” is a useful description of this flow, rather than a separate API: policy distributes the role, the hub console discovers it, and a role assignment grants access. A discoverable role does not grant permissions until it is bound.

Hub console access and managed-cluster workload access are separate grants. This example binds `acm-vm-fleet:view` on the hub and namespace-scoped workload roles on the managed clusters. It does not grant tenants permission to administer access assignments.

## Define what each tenant can do

| Tenant | Identity group | Managed-cluster namespace | Assigned workload roles | Intended access |
| --- | --- | --- | --- | --- |
| A | `tenant-a-operators` | `tenant-a-namespace` | `kubevirt.io:view`, `custom-vm-maintainer` | Read VMs; create, update and patch VM objects; start, stop and restart |
| B | `tenant-b-operators` | `tenant-b-namespace` | `kubevirt.io:view`, `custom-vm-lifecycle` | Read VMs; start, stop and restart |
| C | `tenant-c-viewers` | `tenant-c-namespace` | `kubevirt.io:view` | Read virtualization resources |

These custom roles add no VM deletion, console, VNC, pause, migration, secret access, or RBAC administration. The baseline role is the operator-provided `kubevirt.io:view`; inspect its installed definition when validating the complete permission set. [Default OpenShift Virtualization roles](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/pdf/virtualization/OpenShift_Container_Platform-4.21-Virtualization-en-US.pdf)

Kubernetes permissions are additive. The expected restrictions apply only when other user or group bindings do not grant broader access. A missing `delete` permission is also not protection against damaging updates: a maintainer can still change a VM specification. Keep this tier restricted to trusted operators. [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)

VM object creation is deliberately narrower than a complete provisioning workflow. Creating disks, importing images, attaching networks, or using a console wizard can require additional permissions. Use pre-provisioned storage for the first test, then add individually reviewed permissions for your intended workflow.

## Prepare the environment

Before deploying, prepare:

- An ACM 2.17 hub with governance and fine-grained RBAC for virtualization configured, including the documented self-managed `local-cluster` setup.
- Supported OpenShift Virtualization installations on the hub and target managed clusters, with the required built-in roles present.
- Consistent users, groups, and group memberships across hub and managed clusters.
- Administrator access for setup and authorization to impersonate test identities for the validation commands.
- Kustomize and the PolicyGenerator executable in the expected plugin directory. Pin their versions in your build environment.
- An existing managed cluster set. This example uses `default`; it must contain the hub and every intended target. Replace that set name and its binding together if needed.

The documented component setting is `fine-grained-rbac: enabled: true` in `MultiClusterHub.spec.overrides.components`. Merge it into the existing component configuration without replacing unrelated settings. The same documentation describes identity alignment and hub access requirements. [ACM virtualization RBAC setup](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html/secure_clusters/securing-cluster-intro)

Confirm the served API before applying the assignments:

```bash
oc --context HUB api-resources --api-group=rbac.open-cluster-management.io
oc --context HUB explain multiclusterroleassignment.spec \
  --api-version=rbac.open-cluster-management.io/v1beta1
```

Replace `HUB` and `SPOKE` throughout with your kubeconfig context names.

## Keep one source for the custom roles

The companion example uses this layout:

```text
vm-rbac-example/
├── bootstrap.yaml
├── kustomization.yaml
├── policy-generator.yaml
├── roles/
│   ├── custom-vm-lifecycle.yaml
│   └── custom-vm-maintainer.yaml
├── namespaces/
│   └── tenant-{a,b,c}.yaml
├── assignments/
│   └── tenant-{a,b,c}.yaml
├── fleet-access/
│   └── tenant-{a,b,c}.yaml
├── application.yaml
└── verify-access.py
```

The brace notation abbreviates three separate files. Directory names describe resource purpose; file order is not a deployment dependency. Both role policies reference `roles/`, so there is no second copy of the permission rules to maintain.

The lifecycle role contains only the additional start, stop, and restart permissions:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-lifecycle
  labels:
    rbac.open-cluster-management.io/filter: vm-clusterroles
    clusterview.open-cluster-management.io/discoverable: 'true'
    rbac.open-cluster-management.io/custom-role: 'true'
rules:
- apiGroups:
  - subresources.kubevirt.io
  resources:
  - virtualmachines/start
  - virtualmachines/stop
  - virtualmachines/restart
  verbs:
  - update
```

The maintainer role adds VM object changes:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-maintainer
  labels:
    rbac.open-cluster-management.io/filter: vm-clusterroles
    clusterview.open-cluster-management.io/discoverable: 'true'
    rbac.open-cluster-management.io/custom-role: 'true'
rules:
- apiGroups:
  - kubevirt.io
  resources:
  - virtualmachines
  verbs:
  - create
  - update
  - patch
- apiGroups:
  - subresources.kubevirt.io
  resources:
  - virtualmachines/start
  - virtualmachines/stop
  - virtualmachines/restart
  verbs:
  - update
```

Both roles are layered on `kubevirt.io:view`, so neither repeats the baseline VM read rules. Lifecycle operations use the `subresources.kubevirt.io` API group and an `update` verb. Confirm these endpoints against the installed virtualization API. [KubeVirt API operations](https://kubevirt.io/api-reference/main/operations.html)

The three labels follow ACM 2.17's custom-role requirements. The `custom-role` label also supports the discovery-based propagation pattern documented there. This example instead distributes explicitly named Git files; do not introduce a second policy that manages the same role definitions. [Custom-role workflow](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html/secure_clusters/securing-cluster-intro)

There is no `namespaces` rule in these workload roles. Namespace discovery is cluster-scoped, and a namespace-scoped RoleBinding cannot grant it. Handle any required cluster-level access as a separate, reviewed grant.

## Select the hub and opt in managed clusters

Apply `bootstrap.yaml` on the hub before deploying the generated policies. It creates the policy namespace, binds the existing cluster set, and defines separate hub and spoke placements:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: policies
---
apiVersion: cluster.open-cluster-management.io/v1beta2
kind: ManagedClusterSetBinding
metadata:
  name: default
  namespace: policies
spec:
  clusterSet: default
---
apiVersion: cluster.open-cluster-management.io/v1beta1
kind: Placement
metadata:
  name: vm-rbac-hub
  namespace: policies
spec:
  clusterSets:
  - default
  predicates:
  - requiredClusterSelector:
      labelSelector:
        matchExpressions:
        - key: name
          operator: In
          values:
          - local-cluster
---
apiVersion: cluster.open-cluster-management.io/v1beta1
kind: Placement
metadata:
  name: vm-rbac-spokes
  namespace: policies
spec:
  clusterSets:
  - default
  predicates:
  - requiredClusterSelector:
      labelSelector:
        matchExpressions:
        - key: example.com/vm-rbac
          operator: In
          values:
          - enabled
        - key: name
          operator: NotIn
          values:
          - local-cluster
```

Opt in only the intended managed clusters. For example:

```bash
oc --context HUB label managedcluster managed-cluster-01 \
  example.com/vm-rbac=enabled
oc --context HUB apply -f bootstrap.yaml
oc --context HUB get placementdecision -n policies -o yaml
```

The label is applied to the hub's `ManagedCluster` object. Confirm that the hub placement selects only `local-cluster` and the spoke placement selects exactly the intended managed clusters. Control who can change these labels and placements: changing placement can change where access is granted.

This positive selection avoids enrolling every newly imported cluster. It also excludes the hub from workload assignment even if someone adds the opt-in label to `local-cluster`.

## Assign roles to explicit tenant namespaces

All three MRA objects live in the hub's `policies` namespace. That management namespace does not determine workload scope. Every role assignment explicitly references the spoke placement and a target namespace.

Tenant A's assignment is:

```yaml
apiVersion: rbac.open-cluster-management.io/v1beta1
kind: MulticlusterRoleAssignment
metadata:
  name: tenant-a-vm-access
  namespace: policies
spec:
  subject:
    kind: Group
    name: tenant-a-operators
  roleAssignments:
  - name: tenant-a-role-1
    clusterRole: kubevirt.io:view
    targetNamespaces:
    - tenant-a-namespace
    clusterSelection:
      type: placements
      placements:
      - name: vm-rbac-spokes
        namespace: policies
  - name: tenant-a-role-2
    clusterRole: custom-vm-maintainer
    targetNamespaces:
    - tenant-a-namespace
    clusterSelection:
      type: placements
      placements:
      - name: vm-rbac-spokes
        namespace: policies
```

Tenant B follows the same structure with `custom-vm-lifecycle` plus the baseline view role. Tenant C assigns only the view role. Their complete files are in the companion bundle.

**Keep `targetNamespaces` populated on every tenant assignment.** An omitted or empty value produces a ClusterRoleBinding rather than tenant-scoped RoleBindings. Review this field whenever adding an assignment. [MRA binding scope](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.16/html/secure_clusters/securing-cluster-intro)

The spoke baseline policy creates the three target namespaces; for example:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-a-namespace
```

Namespace creation belongs to the platform workflow. A tenant receives no namespace-creation privilege through these assignments. Resource quotas, network isolation, storage policy, and admission controls remain separate parts of tenant setup.

For hub console access, create a separate binding for each tenant group. Tenant A's file is:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: tenant-a-fleet-view
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: acm-vm-fleet:view
subjects:
- kind: Group
  apiGroup: rbac.authorization.k8s.io
  name: tenant-a-operators
```

This binding targets the hub only. Do not copy it into the spoke policy or replace the workload roles with a cluster-wide administrator binding.

## Generate policies without mixing their destinations

Use this `policy-generator.yaml`:

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: PolicyGenerator
metadata:
  name: vm-rbac
policyDefaults:
  namespace: policies
  remediationAction: enforce
  complianceType: mustonlyhave
  metadataComplianceType: musthave
  pruneObjectBehavior: None
  policySets:
  - vm-rbac
  generatePlacementWhenInSet: true
policySetDefaults:
  generatePolicySetPlacement: false
policies:
- name: vm-rbac-hub-roles
  placement:
    placementName: vm-rbac-hub
  manifests:
  - path: roles
- name: vm-rbac-spoke-baseline
  placement:
    placementName: vm-rbac-spokes
  manifests:
  - path: roles
  - path: namespaces
    complianceType: musthave
- name: vm-rbac-hub-assignments
  disabled: true
  placement:
    placementName: vm-rbac-hub
  manifests:
  - path: assignments/tenant-a.yaml
  - path: fleet-access/tenant-a.yaml
  - path: assignments/tenant-b.yaml
  - path: fleet-access/tenant-b.yaml
  - path: assignments/tenant-c.yaml
  - path: fleet-access/tenant-c.yaml
policySets:
- name: vm-rbac
  description: VM roles and tenant assignments with separate policy placements
placementBindingDefaults:
  name: vm-rbac-binding
```

Three settings deserve attention:

- `mustonlyhave` makes extra permission rules in these custom role definitions drift to remediate. `metadataComplianceType: musthave` permits additional metadata. Namespace manifests use `musthave`, so the policy can coexist with platform-managed namespace fields.
- `generatePolicySetPlacement: false` leaves the PolicySet as a logical group. `generatePlacementWhenInSet: true` retains each policy's explicit placement. No binding targets the PolicySet itself.
- `vm-rbac-hub-assignments` starts disabled. This provides a deliberate checkpoint before granting access.

The policies retain managed objects when removed (`pruneObjectBehavior: None`). This avoids accidental namespace deletion and requires an explicit revocation workflow. Consult the [PolicyGenerator configuration reference](https://raw.githubusercontent.com/open-cluster-management-io/policy-generator-plugin/main/docs/policygenerator-reference.yaml) before changing placement or pruning behavior.

The Kustomization invokes the generator:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
generators:
- policy-generator.yaml
```

Render from the example directory after installing the executable at `$KUSTOMIZE_PLUGIN_HOME/policy.open-cluster-management.io/v1/policygenerator/PolicyGenerator`:

```bash
mkdir -p rendered
kustomize build --enable-alpha-plugins . > rendered/vm-rbac.yaml
```

Inspect the rendered bindings. Hub policies must reference `vm-rbac-hub`; the spoke baseline must reference `vm-rbac-spokes`. There must be no PlacementBinding whose subject is the `vm-rbac` PolicySet.

## Deploy in two stages

First apply the generated resources with the assignment policy disabled:

```bash
oc --context HUB apply --dry-run=server -f rendered/vm-rbac.yaml
oc --context HUB apply -f rendered/vm-rbac.yaml
oc --context HUB get policies -n policies
```

Check the spoke policy's per-cluster compliance and inspect each target cluster:

```bash
oc --context HUB get policy vm-rbac-spoke-baseline -n policies -o yaml
oc --context SPOKE get clusterrole custom-vm-lifecycle custom-vm-maintainer
oc --context SPOKE get namespace \
  tenant-a-namespace tenant-b-namespace tenant-c-namespace
oc --context SPOKE get clusterrole kubevirt.io:view -o yaml
```

A compliant policy on the hub does not prove that all managed clusters are ready. Wait for the role and namespace baseline on every selected cluster. Also confirm the custom roles exist on the hub for discovery.

Next, change `disabled: true` to `disabled: false` on the assignment policy, regenerate, review, and apply the new output. Validate the raw assignment files against the installed hub API as well:

```bash
oc --context HUB apply --dry-run=server -f assignments/
oc --context HUB apply -f rendered/vm-rbac.yaml
oc --context HUB get multiclusterroleassignments -n policies -o yaml
oc --context SPOKE get rolebindings -n tenant-b-namespace -o yaml
```

Inspect each assignment's status. On the managed cluster, verify the RoleBinding's subject, role reference, and namespace rather than relying on a generated binding name.

## Deliver reviewed output with Argo CD

A practical GitOps option is to render policies in CI, review the resulting changes, and have Argo CD synchronize the rendered directory. This keeps the executable plugin in the controlled build environment. Argo CD does not need to run PolicyGenerator in this arrangement.

Commit `rendered/vm-rbac.yaml` to your deployment repository and adapt this Application:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: vm-rbac
  namespace: openshift-gitops
spec:
  project: vm-rbac
  source:
    repoURL: https://git.example.com/platform/vm-rbac.git
    targetRevision: REPLACE_WITH_REVIEWED_COMMIT_SHA
    path: rendered
    directory:
      recurse: false
  destination:
    server: https://kubernetes.default.svc
    namespace: policies
```

Replace the repository URL and revision with your repository and reviewed commit SHA. Adapt the companion `appproject.yaml` to create the named `vm-rbac` AppProject with that source repository, the hub destination, and the required namespaced policy resource kinds allowed. Grant the Argo CD controller permission to manage those resources in `policies`. Bootstrap and workload RBAC enforcement remain separate administrative responsibilities.

Use a manual sync for the initial deployment and for the assignment-enablement change. The Application intentionally omits an automated sync policy. Argo CD's `Synced` status confirms synchronization of root resources; verify ACM policy compliance and MRA status separately.

Running PolicyGenerator inside Argo CD is another option, but requires installation and configuration of the plugin and Kustomize build options in the repository server. An Application alone does not supply that setup. [Argo CD Kustomize configuration](https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/)

## Verify authorization and the user experience

Test with identities that have only the intended group memberships. An administrator running the commands without impersonation will see the administrator's access.

For Tenant B, a lifecycle operation should be permitted:

```bash
oc --context SPOKE auth can-i update \
  virtualmachines.subresources.kubevirt.io --subresource=start \
  -n tenant-b-namespace --as=rbac-validation \
  --as-group=tenant-b-operators --as-group=system:authenticated
```

Expected answer: `yes`. VM creation and another tenant's inventory should be denied:

```bash
oc --context SPOKE auth can-i create virtualmachines.kubevirt.io \
  -n tenant-b-namespace --as=rbac-validation \
  --as-group=tenant-b-operators --as-group=system:authenticated

oc --context SPOKE auth can-i list virtualmachines.kubevirt.io \
  -n tenant-a-namespace --as=rbac-validation \
  --as-group=tenant-b-operators --as-group=system:authenticated
```

Expected answer to both: `no`. A denial normally returns exit status 1; account for that in automation. The companion `verify-access.py` checks all three tiers, including cross-tenant denials:

```bash
python3 verify-access.py SPOKE
```

Run it on every selected managed cluster. Then sign in through the hub console as real users from each group and test against disposable workloads:

| Check | Tenant A | Tenant B | Tenant C |
| --- | --- | --- | --- |
| View VMs in the assigned namespace | Allowed | Allowed | Allowed |
| Start, stop and restart an existing VM | Allowed | Allowed | Denied |
| Create or change a VM object using the supported test workflow | Allowed | Denied | Denied |
| Delete a VM or open its console | Denied | Denied | Denied |
| View VMs in another tenant's namespace | Denied | Denied | Denied |

These are acceptance criteria. Check API responses as well as whether console actions are available. An authorization check cannot establish that storage, admission, networking, or a multi-step console workflow will succeed. Test each intended operation, inspect audit records for unexpected access, and repeat the denial tests with actual user identities.

## Troubleshoot the layer that failed

| Symptom | Check |
| --- | --- |
| Generator cannot load | Executable location, execute permission, plugin home, and `--enable-alpha-plugins` |
| Placement selects no clusters | Cluster set membership, its namespace binding, opt-in labels, cluster health, and PlacementDecision objects |
| Role differs on a managed cluster | Spoke policy compliance and its ConfigurationPolicy messages; check for another controller managing the same role |
| Role is missing from the console | Hub role existence, required labels, feature configuration, and the user's hub console binding |
| Assignment fails or grants nothing | Installed MRA schema, assignment status, referenced placement, role existence, and target namespace existence |
| User has too much access | Actual identity-provider groups, all RoleBindings and ClusterRoleBindings, and any assignment with empty target namespaces |
| Authorization succeeds but VM operation fails | Exact failing API request, admission messages, workload state, and storage or network prerequisites |

## Onboard and revoke access deliberately

For a new tenant, create its namespace manifest, group-specific assignment, and hub fleet-access binding. Add the namespace to the spoke baseline and both hub files to the assignment policy. Deploy the namespace first, then the assignment, and extend the authorization tests before promotion.

For revocation, keep the relevant files in the generator and temporarily set `complianceType: mustnothave` on that tenant's assignment and fleet-access manifest entries. For Tenant B, those entries become:

```yaml
- path: assignments/tenant-b.yaml
  complianceType: mustnothave
- path: fleet-access/tenant-b.yaml
  complianceType: mustnothave
```

Render and deploy this transition while the assignment policy remains enabled. Verify deletion of the hub MRA and hub console binding, then confirm that the MRA controller has removed the managed-cluster bindings and that access checks now deny the former grants. Account for other bindings and group memberships when interpreting those checks.

Only after confirming revocation should you remove those entries and files. Retain tenant namespaces and workloads until a separate approved offboarding process handles them. Removing a file or disabling a policy alone does not revoke existing access with the retention settings in this example.

Keep managed clusters reachable during planned revocation and verify the outcome on each one. Treat placement changes as access changes, including checks for permissions left on previously selected clusters.

## Make access review repeatable

Custom roles are useful when a built-in role grants more than a team needs. Their value depends on an explicit scope and a verification routine that proves restrictions as well as capabilities.

Start with one managed cluster and disposable workloads. Use the companion manifests to render the policies, confirm the selected destinations, and run the permission matrix. Promote the reviewed configuration only after the real-user workflow and revocation checks pass. Keep those checks with the repository so the next tenant, product upgrade, or role change goes through the same review.
