# Govern VM access with ACM 5.0

A **VM maintainer** needs to change a machine's configuration. A **lifecycle operator** needs to restart it. A **viewer** needs to inspect its state. Assigning the same broad virtualization role to all three gives people permissions their work does not require.

Across several clusters, the problem is also consistency: which group can perform which operation, in which namespace, on which clusters? Keeping those decisions in Git makes them reviewable. Red Hat Advanced Cluster Management for Kubernetes (ACM) can distribute the role definitions and create the corresponding access assignments.

This article presents an **ACM 5.0 reference design** for platform engineers. The [companion example](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/README.md) has passed local rendering, schema, and consistency checks. Live ACM deployment, console behavior, and revocation remain acceptance tests; this is not a report of a completed production deployment.

## Choose three access tiers

Start with the operator-provided `kubevirt.io:view` role and add only the operations each team needs. The built-in `kubevirt.io:edit` role is broader: it includes VM deletion and console/VNC access, which these tiers deliberately omit. Inspect the installed built-in roles when assessing the effective permissions. [Virtualization role definitions](https://github.com/kubevirt/kubevirt/blob/main/pkg/virt-operator/resource/generate/rbac/cluster.go)

| Access tier | Example group | Managed-cluster namespace | Additional role | Intended operations |
| --- | --- | --- | --- | --- |
| Maintainer | `tenant-a-operators` | `tenant-a-namespace` | `custom-vm-maintainer` | Create, update and patch VM objects; start, stop and restart |
| Lifecycle operator | `tenant-b-operators` | `tenant-b-namespace` | `custom-vm-lifecycle` | Start, stop and restart existing VMs |
| Viewer | `tenant-c-viewers` | `tenant-c-namespace` | None | Read virtualization resources |

Every group also receives `kubevirt.io:view` in its assigned namespace. The file names use “tenant” to identify three example teams. The **tier** describes their permissions; network, storage, resource quotas, and admission controls are separate parts of a tenant boundary.

Kubernetes RBAC is additive. Other user or group bindings can expand these permissions, and the absence of `delete` does not make VM modification harmless. Workload creation and editing can provide indirect access to namespace data. [Kubernetes RBAC considerations](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)

Treat maintainers as trusted workload authors. Subject to the installed virtualization and admission configuration, VM specifications can reference namespace PVCs, Secrets and ConfigMaps, supply cloud-init content, and request devices. Review permitted references and device use before granting this tier. Where supported, admission rules such as a [ValidatingAdmissionPolicy](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/) can constrain selected VM fields; this example does not install those guardrails.

VM object creation also does not supply every permission needed by a provisioning wizard, disk import, or network attachment workflow. Begin with pre-provisioned resources and test the exact workflow you intend to offer.

## Separate role delivery from access assignment

The design uses governance policies for role definitions and `MulticlusterRoleAssignment` (MRA) resources for access grants:

```mermaid
flowchart TD
    Git[Reviewed Git source] --> Argo[Argo CD with PolicyGenerator]
    Argo --> Governance[Governance policies on the hub]
    Governance --> Roles[Role definitions on hub and selected managed clusters]
    Governance --> MRA[Hub MulticlusterRoleAssignment resources]
    MRA --> Bindings[RoleBindings in explicit workload namespaces]
    Roles --> API[Managed cluster API authorizes VM requests]
    Bindings --> API
```

A hub role is available for discovery; a role binding is what grants access. The hub console grant is separate again: each group receives `acm-vm-fleet:view` on the hub, while its workload roles are bound in managed-cluster namespaces. The documented purpose of the fleet role is access to the virtualization console. It is **not a promise that all fleet metadata is hidden from other teams**. [ACM 5.0 role descriptions](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html/secure_clusters/securing-cluster-intro#fine-grain-roles-descriptions)

The hub is excluded from workload placement. Even though the prerequisites include OpenShift Virtualization on the hub, these assignments give the example teams no access to hub-hosted VMs.

The repository also contains a separate [full-admin example](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/examplefulladmin/README.md). Its wildcard role and cluster-wide assignment grant cluster-admin-equivalent access. Use the namespace-scoped companion files for the tiers described here.

## Prepare the hub and selected clusters

Use a supported product combination from the [ACM 5.0 support matrix](https://access.redhat.com/articles/7149098). Before proceeding, confirm:

- Governance and fine-grained virtualization RBAC are configured on the ACM 5.0 hub.
- The self-managed hub retains the name `local-cluster`, which this example's placements select explicitly.
- Supported OpenShift Virtualization installations and required built-in roles exist on the hub and intended managed clusters.
- Users, groups, and memberships match across hub and managed clusters.
- The `default` managed cluster set contains the hub and intended targets; otherwise adapt the set and binding together.
- Red Hat OpenShift GitOps is installed on the hub, and the setup administrator can configure it and impersonate test identities.

The feature component entry is:

```yaml
spec:
  overrides:
    components:
      - name: fine-grained-rbac
        enabled: true
```

Merge this fragment into the existing `MultiClusterHub` component list. Preserve unrelated entries and avoid duplicates. The [ACM 5.0 setup procedure](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html/secure_clusters/securing-cluster-intro#fine-grain-enable) documents the component and identity prerequisites.

## Define each role once

The [lifecycle role](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/roles/custom-vm-lifecycle.yaml) contains only the additional operations:

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

The [maintainer role](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/roles/custom-vm-maintainer.yaml) adds `create`, `update`, and `patch` on `kubevirt.io` virtual machines. Read permissions come from the baseline view role.

The three labels follow the [documented custom-role workflow](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html/secure_clusters/securing-cluster-intro#fine-grain-mca-custom). A label alone does not install a propagation policy: the discovery-based approach in the documentation requires creating that policy. This design instead names its source files explicitly. `vm-rbac-hub-roles` manages hub definitions and `vm-rbac-spoke-baseline` manages managed-cluster definitions. Both read the same `roles/` directory. Do not deploy an additional discovery-based policy for these same objects.

The [generator configuration](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/policy-generator.yaml) also makes several scope decisions explicit:

- `mustonlyhave` treats extra rules in these role definitions as drift and remediates them. Additional metadata is permitted; namespace objects use `musthave`.
- Hub and spoke policies have separate placements. The PolicySet groups policies without introducing another placement binding.
- The assignment policy starts disabled, allowing role and namespace checks before access is granted.
- `pruneObjectBehavior: None` retains objects when policies are removed. Revocation therefore requires an explicit transition.

## Make namespace scope visible in the assignment

MRAs live in the hub's `policies` management namespace in this example. Their workload scope comes from `targetNamespaces`, and their cluster scope comes from referenced placements. ACM's [MRA examples](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html/secure_clusters/securing-cluster-intro#fine-grain-mca-examples) demonstrate management namespaces other than the global-set namespace; that namespace name is not itself a workload-access boundary.

The [lifecycle assignment](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/assignments/tenant-b.yaml) grants the baseline and additional role separately:

```yaml
apiVersion: rbac.open-cluster-management.io/v1beta1
kind: MulticlusterRoleAssignment
metadata:
  name: tenant-b-vm-access
  namespace: policies
spec:
  subject:
    kind: Group
    name: tenant-b-operators
  roleAssignments:
  - name: tenant-b-role-1
    clusterRole: kubevirt.io:view
    targetNamespaces:
    - tenant-b-namespace
    clusterSelection:
      type: placements
      placements:
      - name: vm-rbac-spokes
        namespace: policies
  - name: tenant-b-role-2
    clusterRole: custom-vm-lifecycle
    targetNamespaces:
    - tenant-b-namespace
    clusterSelection:
      type: placements
      placements:
      - name: vm-rbac-spokes
        namespace: policies
```

**Keep `targetNamespaces` populated.** An omitted or empty value creates a cluster-wide binding instead of namespace-scoped RoleBindings. [ACM binding scope](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html/secure_clusters/securing-cluster-intro#fine-grain-mca-binding)

The companion baseline creates the example namespaces. A tenant group receives no namespace-creation privilege, and these workload RoleBindings do not grant cluster-scoped namespace discovery.

## Follow one rollout path

The article and its companion links use the fixed snapshot `acm5-rbac-reference-v1`. Check out that snapshot so the prose, manifests, and instructions stay aligned:

```bash
git clone --branch acm5-rbac-reference-v1 --single-branch \
  https://github.com/ch-stark/finegrainedrbacvirt.git
cd finegrainedrbacvirt/vm-rbac-example
git switch -c vm-rbac-deployment
```

Use your own branch or fork for configuration changes. Replace `HUB` and `SPOKE` below with kubeconfig context names.

**1. Select clusters deliberately.** Apply the [bootstrap manifest](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/bootstrap.yaml) and opt in a managed cluster:

```bash
oc --context HUB apply -f bootstrap.yaml
oc --context HUB label managedcluster managed-cluster-01 \
  example.com/vm-rbac=enabled
oc --context HUB get placementdecision -n policies -o yaml
```

Confirm that `vm-rbac-hub` selects only `local-cluster` and `vm-rbac-spokes` selects exactly the intended managed clusters. `example.com/vm-rbac` is a valid illustrative label; substitute your organization-owned prefix consistently in the label and selector if appropriate. Restrict who can edit placements and selection labels because those changes affect access.

**2. Configure PolicyGenerator in Argo CD.** The supported [ACM 5.0 GitOps integration](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/5.0/html-single/gitops) patches the operator-managed ArgoCD resource. Its repository-server init container installs the generator, its shared volume supplies the plugin, and `kustomizeBuildOptions` permits it to run.

Follow the [direct configuration procedure](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/README.md#configure-policygenerator-in-argo-cd). It contains the full patch and controller RBAC. Merge existing repository settings into the patch before applying it, because JSON merge patches replace arrays.

This example deliberately grants the application controller a Role in `policies`, rather than the broader ClusterRoleBinding shown in the documentation. It manages only policy resources there; the administrator creates placements separately. The [governance-policy alternative](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/README.md#configure-the-integration-with-a-governance-policy) and the linked community policy are available in the companion guide.

**3. Review and sync the baseline.** Configure the [Application](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/application.yaml) and [AppProject](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/appproject.yaml) for your repository. Set `targetRevision` to a reviewed commit SHA. The Application points at `vm-rbac-example`, so Argo CD runs the source Kustomization and PolicyGenerator.

Create the project and Application, then manually sync with `vm-rbac-hub-assignments` still disabled. Check the per-cluster policy status and inspect every intended managed cluster for both custom roles, `kubevirt.io:view`, and the three namespaces. A successful Argo CD sync does not establish downstream compliance.

**4. Grant access after the baseline is ready.** Change the assignment policy to `disabled: false`, review and commit the change, update the Application revision, and manually sync again. Check MRA status and inspect the resulting RoleBinding subjects, role references, and namespaces. The [complete rollout commands](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/README.md#deploy-the-source-through-argo-cd) remain with the manifests.

## Verify capabilities and boundaries

Run the [authorization script](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/verify-access.py) against each selected managed cluster:

```bash
python3 verify-access.py SPOKE
```

It queries expected permissions for all three tiers, including cross-namespace denials. It does not perform VM operations or test the console. Test with actual users as well: an administrator's own access and a synthetic identity's limited group list are not substitutes for real group membership.

| Acceptance check | Maintainer | Lifecycle operator | Viewer |
| --- | --- | --- | --- |
| Read VMs in the assigned namespace | Allowed | Allowed | Allowed |
| Start, stop and restart existing VMs | Allowed | Allowed | Denied |
| Create or modify VM objects with approved resources | Allowed | Denied | Denied |
| Delete VMs or use console/VNC endpoints | Denied | Denied | Denied |
| Read another team's VMs through its managed-cluster API | Denied | Denied | Denied |
| Find another team's VMs through hub inventory, search, or direct details links | Must not expose unauthorized VM data | Must not expose unauthorized VM data | Must not expose unauthorized VM data |

These are acceptance criteria, not recorded results. Exercise real operations on disposable workloads and check responses, not only whether buttons appear. Storage, admission, and networking can still reject an operation that RBAC permits.

For console validation, sign in as the lifecycle operator and search for a known maintainer-team VM by name and namespace. Try inventory filters and a saved direct details link. Repeat for the other teams. Separately record any visible cluster names, namespace names, or counts, and compare them with your organization's metadata-visibility requirements. Namespace-scoped workload bindings alone do not guarantee that all fleet metadata is confidential. If the shared console exposes metadata outside your allowed scope, this design does not meet that requirement without additional controls or a different access path.

The [validation record](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/validation-results.md) separates local checks from pending deployment evidence. Record exact product versions, the source commit, MRA status, resulting RoleBindings, console/search observations, and successful revocation before describing your deployment as validated.

## Keep the boundary after rollout

Grant changes, onboarding, revocation, and placement changes all need the same review discipline. With object retention configured, deleting a Git file or disabling a policy is insufficient proof that access disappeared.

The [revocation procedure](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/README.md#onboard-and-revoke-access) uses a temporary `mustnothave` transition, then checks hub and managed-cluster cleanup before files are removed. The companion guide also contains [troubleshooting](https://github.com/ch-stark/finegrainedrbacvirt/blob/acm5-rbac-reference-v1/vm-rbac-example/README.md#troubleshoot-the-layer-that-failed).

Start with one managed cluster and disposable VMs. Confirm the selected destinations, prove the permission and visibility boundaries, and record the results. That gives the next team a reviewed role definition and a concrete validation process to reuse.
