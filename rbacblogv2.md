# Fine-grained RBAC for virtualization in ACM 2.16 and 2.17

Red Hat Advanced Cluster Management can grant a virtualization administrator the VM power they need across a fleet, without `cluster-admin` on every managed cluster.

This guide answers the questions customers actually ask: which roles exist, where you bind them, which combination matches a VMware-style VM admin, and what still surprises people in the console.

Official documentation: [Secure clusters — fine-grained RBAC](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html-single/secure_clusters/index#fine-grain-intro). Copy-paste YAML for common personas is in [`examples/`](examples/).

> **Do not assign these names.** Some older documentation still lists `kubevirt.io-acm-managed:admin`, `kubevirt.io-acm-managed:view`, `kubevirt.io-acm-hub:admin`, and `kubevirt.io-acm-hub:view`. Those ClusterRoles are not installed on ACM 2.16, 2.17, or later. Use the live names in this post.

## Two planes: hub and spoke

ACM does not grant VM access from hub configuration alone. You always bind roles in two places.

| Plane | What you bind | What it does |
|---|---|---|
| **Hub** | `acm-vm-fleet:view` or `acm-vm-fleet:admin` as a ClusterRoleBinding on the hub | Opens the Fleet Virtualization tab. `acm-vm-fleet:admin` is required to drive **cross-cluster live migration** from the hub. Neither role grants `virtualmachines` on a managed cluster. |
| **Spoke** | `kubevirt.io:*`, `acm-vm-extended:*`, and (today) `migrations.kubevirt.io:*`, usually through a `MulticlusterRoleAssignment` | Real Kubernetes RBAC on that cluster. The ACM cluster proxy impersonates the same user or group. If the spoke has no RoleBinding, opening a VM returns **Access Denied**, even when the hub list showed the VM. |

Users, groups, and group membership must match on the hub and on every managed cluster. The hub must be self-managed. OpenShift Virtualization must be installed on the hub and on every cluster where you manage VMs.

### How a click is authorized

1. The fleet list and VM summary pages read ACM Search on the hub.
2. Opening a VM, changing it, or starting a migration tunnels through the cluster proxy to the managed cluster.
3. That cluster evaluates the RoleBindings and ClusterRoleBindings that exist there.

A broad hub role such as `cluster-reader` fills the list and then fails on click-through. The spoke never agreed.

## Live roles: bind both, do not assume “extends”

OpenShift Virtualization installs `kubevirt.io:view`, `kubevirt.io:edit`, and `kubevirt.io:admin`. ACM installs **companion** ClusterRoles. Those companions do not include kubevirt.io permissions. You bind both.

| Role | Where | What it is | What it is not |
|---|---|---|---|
| `acm-vm-fleet:view` | Hub ClusterRoleBinding | See the Virtualization tab. | VM create, edit, or delete on spokes. Cross-cluster live migration. |
| `acm-vm-fleet:admin` | Hub ClusterRoleBinding | Console plus cross-cluster live migration from the hub. | VM administrator on a spoke. |
| `kubevirt.io:view`, `:edit`, `:admin` | Spoke | Core virtualization APIs. `:admin` includes the HyperConverged resource in `openshift-cnv`. Cross-cluster live migration requires `:admin` on **source and destination**. | ACM console extras. OpenShift `cluster-admin`. |
| `acm-vm-extended:view`, `:admin` | Spoke, same namespaces as the kubevirt.io role | ACM console details, troubleshooting, and configuration in the VM UI. | Core VM create, edit, or delete. |
| `acm-vm-cluster-migration:view` | Spoke, cluster-scoped, on source **and** destination | Readiness checks for cross-cluster live migration. | Creating VMs. The hub migration UI (`acm-vm-fleet:admin`). |
| `migrations.kubevirt.io:view`, `:storagemigrate`, `:storagemigrate-multins` | Spoke, required today for in-cluster migration UI | Storage migrate and related console panels. Easy to omit; the console then looks incomplete. | Cross-cluster live migration. That stays `acm-vm-fleet:admin` plus `kubevirt.io:admin` plus `acm-vm-cluster-migration:view`. |

If documentation says a role “extends” kubevirt.io, read that as **extra ACM console APIs you bind in addition to kubevirt.io**. It does not mean the ACM role already contains kubevirt.io.

To see whether a grant is too much, run this **on the managed cluster**:

```bash
oc describe clusterrole kubevirt.io:admin
oc describe clusterrole acm-vm-extended:admin
oc describe clusterrole migrations.kubevirt.io:view
oc auth can-i --list --as=<user>
```

## Personas

Hub bindings are ClusterRoleBindings on the hub. `MulticlusterRoleAssignment` creates the spoke RoleBindings and ClusterRoleBindings.

| Who | Hub | Each managed cluster |
|---|---|---|
| **Viewer** (auditor, NOC, read-only operator) | `acm-vm-fleet:view` | `kubevirt.io:view` and `acm-vm-extended:view` in the allowed namespaces. Also bind `migrations.kubevirt.io:view` if in-cluster migration panels must appear. |
| **VM administrator, not cluster-admin** (typical former vSphere admin) | `acm-vm-fleet:view`. Add `acm-vm-fleet:admin` only if they will migrate VMs **between clusters**. | **Both** `kubevirt.io:admin` **and** `acm-vm-extended:admin`. This pairing replaces the retired `kubevirt.io-acm-managed:admin` name. They still cannot administer the OpenShift cluster. |
| **Cross-cluster live migration operator** | `acm-vm-fleet:admin` | On **source and destination**: `kubevirt.io:admin` and `acm-vm-extended:admin`, plus cluster-scoped `acm-vm-cluster-migration:view`. |
| **Day-2 operator** (start and stop, no delete) | `acm-vm-fleet:view` | `kubevirt.io:view` plus a custom ClusterRole. See [`customrbac.md`](customrbac.md). Label the custom role `rbac.open-cluster-management.io/filter: vm-clusterroles` so it appears in the ACM UI. |

## In-cluster migration UI

For the virtualization console **on a managed cluster**, you currently assign three extra ClusterRoles besides kubevirt.io and `acm-vm-extended`:

- `migrations.kubevirt.io:view`
- `migrations.kubevirt.io:storagemigrate`
- `migrations.kubevirt.io:storagemigrate-multins`

Without them, VM actions can work while migration-related panels fail. Cross-cluster live migration is a different recipe. Do not use these three roles as a substitute for `acm-vm-fleet:admin` and `acm-vm-cluster-migration:view`.

A later ACM release is expected to include the read permissions in `acm-vm-extended:view` and the write permissions in `acm-vm-extended:admin`, so a typical console assignment becomes hub fleet view plus kubevirt.io plus extended only. Until that ships, bind the three roles explicitly.

## How many MulticlusterRoleAssignment objects

`MulticlusterRoleAssignment` is the right API for fleet assignment. Today, every assignment that targets a given managed cluster is combined into **one** `ClusterPermission`, delivered as **one** ManifestWork. That object has a size limit (on the order of 1.5 MiB). Large onboarding — many assignments, many clusters, several role bindings each, still adding LDAP groups — can hit the limit. Deleting and recreating the ClusterPermission is only a temporary unblock; the controller rebuilds the same object.

Until ACM splits that payload, keep the number of assignments down:

- Prefer groups over one assignment per user.
- Prefer one `MulticlusterRoleAssignment` with several `roleAssignments` over many objects for the same subject.
- If you are already over the limit, some bindings can be placed in a per-cluster `ClusterPermission` by hand. Treat that as overflow, not the design.

Do not work around the limit by granting `cluster-admin` or `cluster-reader` on the hub. That only restores a list of VMs the user cannot open.

## Implicit VM access from namespace admin

Fine-grained RBAC **adds** explicit grants. By default, OpenShift Virtualization still **aggregates** `kubevirt.io:admin`, `:edit`, and `:view` into the built-in namespace `admin`, `edit`, and `view` ClusterRoles. A namespace admin can manage VMs with no ACM assignment at all.

OpenShift Virtualization 4.22 adds an opt-out as **Developer Preview**. On HyperConverged, set `spec.roleAggregationStrategy` to `Manual` (the historical default is `AggregateToDefault`). Confirm the field on your cluster:

```bash
oc explain hyperconverged.spec.roleAggregationStrategy
```

Developer Preview is not covered in OpenShift product documentation. After you set Manual, an explicit `kubevirt.io:*` RoleBinding (or a MulticlusterRoleAssignment) is the only VM grant. Flip to Manual **after** those bindings exist, or namespace admins lose VMs. Do not patch aggregation labels off the ClusterRoles; the operator puts them back.

Fleet-wide steps, including a ConfigurationPolicy example: [`disable-role-aggregation.md`](disable-role-aggregation.md).

## Apply order

1. Use the same users and groups on the hub and on managed clusters.
2. Create a hub ClusterRoleBinding for `acm-vm-fleet:view` or `acm-vm-fleet:admin`.
3. Create a `MulticlusterRoleAssignment` in a namespace that has a `ManagedClusterSetBinding` for the Placement cluster set. Prefer groups and fewer objects.
4. On each managed cluster, confirm the RoleBindings exist.
5. Run `oc auth can-i get virtualmachines -n <namespace> --as=<user>` on the **managed cluster**, not only on the hub.
6. If you need deny-by-default VM access, opt out of role aggregation on OpenShift Virtualization 4.22 or later **after** step 3.

## Former VMware administrators

The usual request is full VM administration without OpenShift `cluster-admin`:

- Hub: `acm-vm-fleet:view`. Add `acm-vm-fleet:admin` only for cross-cluster live migration.
- Spoke: `kubevirt.io:admin` **and** `acm-vm-extended:admin` in the VM namespaces. Today, also bind the three `migrations.kubevirt.io:*` roles if the in-cluster migration UI is in scope.
- Do not assign `cluster-admin`, do not assign the retired `kubevirt.io-acm-managed:admin` name, and do not use hub `cluster-reader` as a substitute.
