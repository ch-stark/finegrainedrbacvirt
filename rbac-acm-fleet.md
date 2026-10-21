# RBAC in ACM: the patterns you need

When you implement RBAC with ACM there are many options and this deep-drive blog tries to write them down.

The **hub** decides what you see: which clusters, which console tabs, which queries. The **spoke** decides what you can do. A console click that returns `Forbidden` is usually a hub role without a matching spoke binding.

Controllers keep service accounts. People should be impersonated. The hub user and the hub groups are what the spoke should see in the audit log.

## The model

| | Hub | Spoke |
| --- | --- | --- |
| Question | What may this person see? | What may this person do? |
| Object | Cluster set role, hub console role | `RoleBinding` or `ClusterRoleBinding` |
| Who acts for a person | The console, through cluster-proxy | The apiserver, as the impersonated user and groups |
| Who acts for a controller | The hub controller | A service account, applied by the work agent |

**Cluster-proxy** is the addon that lets the hub reach a managed cluster API without publishing that API. On a console click it impersonates the hub username and the hub groups. The authenticated caller is the cluster-proxy service account. Spoke RBAC is then evaluated as the impersonated user. The audit log has both names. Cluster-proxy does not apply `ManifestWork` objects. The work agent does that, as its own service account. Cluster-proxy does not read the spoke identity provider.

**The default path does not impersonate.** The klusterlet work agent and the addon agents (policy, observability, GitOps, and others) act as service accounts. The audit line names `system:serviceaccount:...`, not the person who clicked. The service account's role is the ceiling for everyone who can trigger it. Access to the hub that can submit that work is access to that spoke power. Do not create one service account per hub user. That repeats the problem.

The console path needs the hub to be self-managed (`local-cluster`). The group string on the hub token and the group string on the spoke binding must be the same characters. ACM does not translate directories. Two people who share a short name, such as `AP001` in two directories, are one Kubernetes subject.

The console never asks the spoke identity provider. Configure that provider on the spokes only when the same people log in there directly. If they must not, leave the user provider off the spokes. That blocks direct login more simply than an admission rule on tokens. Keep a break-glass administrator for when the hub is down.

## What you need, by version

| Capability | Where it stands |
| --- | --- |
| Cluster sets, policies, placements, cluster-proxy | Current ACM |
| `MulticlusterRoleAssignment` for OpenShift Virtualization | Generally available in ACM 2.16 and 2.17. The API is still `rbac.open-cluster-management.io/v1beta1`. Generally available means Red Hat supports this use. It does not mean the API has moved to `v1`. The `fine-grained-rbac` component on `MultiClusterHub` is off until you enable it. |
| Log and metric scope through the same assignment | Not generally available. There will not be a second API. |
| Applications and Argo CD | Partially separate product RBAC but needs to fit together.  |
| Admission control | Not direct ACM RBAC but often related |

## Cluster sets

A cluster set is the hub's answer to "which clusters may this group see?"

For a set named `zone-a`, ACM creates three roles. Bind them with a `ClusterRoleBinding`.

| Role | What it grants |
| --- | --- |
| `open-cluster-management:managedclusterset:view:zone-a` | See the clusters in that set, and the resources the console attaches to that view. |
| `open-cluster-management:managedclusterset:admin:zone-a` | Manage the set. |
| `open-cluster-management:managedclusterset:bind:zone-a` | View, plus create a `ManagedClusterSetBinding` for that set. |

`view` does not create the binding. `bind` does. A `Placement` only selects clusters from sets that are already bound into its namespace. The platform owner creates that binding. The team receives `view`.

`view` does not grant virtual machines, applications, or logs on the spoke. It does not open Argo CD. A developer who should work only on the spoke does not need a cluster set role and does not need a hub login. ACM still controls and monitors that cluster.

Keep a `global-set` (or the equivalent) for platform owners. Do not hand that view to every team.

## MulticlusterRoleAssignment

`MulticlusterRoleAssignment` is centralized RBAC. One object on the hub names a subject, a `Placement`, and the ClusterRoles to bind on the selected spokes. The controller creates the spoke bindings. Prefer one assignment per group.

| `targetNamespaces` | Result on each selected cluster |
| --- | --- |
| Empty or omitted | One `ClusterRoleBinding`. The role applies in every namespace. |
| A list | One `RoleBinding` in each listed namespace. Nothing elsewhere, including `openshift-cnv`. |

The `Placement` must exist first. It should select only clusters where the ClusterRole exists. A placement that includes clusters without OpenShift Virtualization will fail a binding to `kubevirt.io:view`.

Namespace lists from the hub are the hard case. The list does not grow when someone creates a project. The same application uses different project names on different clusters. A long list is merged with every other assignment into one `ClusterPermission` and one `ManifestWork`, and that work object can hit the size limit (about 1.5 MiB). Applications add more lists: the team namespace, the GitOps source namespaces, and the destination namespace. Leave `targetNamespaces` empty unless the hub team can keep the list current.

## Worked example: Zone A virtual machine admins

The group `zonea-vm-admins` may see Zone A in the console and administer virtual machines there. They are not cluster administrators.

1. **Hub identity.** Put the people in `zonea-vm-admins` on the hub identity provider. Add that same provider on the Zone A spokes only if those people log in on the spokes. The console path does not need it.
2. **Hub, cluster set.** Bind `zonea-vm-admins` to `open-cluster-management:managedclusterset:view:zone-a`. A platform owner with `open-cluster-management:managedclusterset:bind:zone-a` creates the `ManagedClusterSetBinding` in the namespace where placements will live.
3. **Hub, spoke power.** Create one `MulticlusterRoleAssignment` on the hub, in that namespace. The subject is the group. The placement selects Zone A clusters that run OpenShift Virtualization. The roles are `kubevirt.io:admin` and `acm-vm-extended:admin`. The controller creates the bindings on the spokes. This object is not created on the spokes.
4. **Hub, console tab.** Bind the same group to `acm-vm-fleet:view`. Cross-cluster live migration needs `acm-vm-fleet:admin` on the hub and `acm-vm-cluster-migration:view` on both the source and the destination spoke.
5. **Check.** On a Zone A spoke, `oc auth can-i` as a member of the group. In the spoke audit log, the click should name the person (`impersonatedUser`), not only `system:serviceaccount:...`.

| Step | Where the object is created | Object |
| --- | --- | --- |
| 2 | Hub | `ClusterRoleBinding` to `open-cluster-management:managedclusterset:view:zone-a`, and a `ManagedClusterSetBinding` created by someone who has `bind` |
| 3 | Hub | `MulticlusterRoleAssignment` |
| 3, applied by the controller | Spoke | `ClusterRoleBinding` or `RoleBinding` for the group |
| 4 | Hub | `ClusterRoleBinding` to `acm-vm-fleet:view` |

Enable `fine-grained-rbac` before the `acm-vm-*` roles exist. The command is in the appendix.

## Hub objects that equal spoke power

The opening problem is not only the default service accounts. Whoever can write the objects below can grant spoke permissions. Treat create and update on them as cluster-admin on the clusters they can reach.

| Hub object | What it can do on a spoke |
| --- | --- |
| `MulticlusterRoleAssignment` | Bind any ClusterRole the placement's clusters have, to any subject you name. |
| `Policy` with a `PlacementBinding` | Ship any manifest the template contains, including `ClusterRoleBinding` objects. `remediationAction: enforce` applies them. |
| `ManifestWork` | The work agent applies it as a privileged service account. It lives in the managed cluster's namespace on the hub. |
| `Placement` | Does not apply anything by itself. It aims the three objects above. A placement only sees sets bound into its namespace. |
| `ManagedClusterSetBinding` | Projects a set into a namespace, so placements there can select those clusters. Creating it requires `managedclustersets/bind`, not namespace admin alone. |

These objects are namespaced (except the bind permission, which is a subresource check). The OpenShift `admin` role in a namespace can create a `Policy`, a `Placement`, and a `MulticlusterRoleAssignment` there. Give that role only to people who are allowed to grant spoke power.

Practical split:

- Platform owners create bindings, assignments, policies, and manifest works.
- A team that only needs to see clusters gets `managedclusterset:view:<set>`, not `admin` on the namespace the set is bound into.
- Do not bind a production set into a namespace where developers are namespace admins.

```bash
oc auth can-i create multiclusterroleassignments.rbac.open-cluster-management.io -n site-virt --as=<user> --as-group=<group>
oc auth can-i create policies.policy.open-cluster-management.io -n site-virt --as=<user> --as-group=<group>
oc auth can-i create placements.cluster.open-cluster-management.io -n site-virt --as=<user> --as-group=<group>
oc auth can-i create manifestworks.work.open-cluster-management.io -n <cluster-namespace> --as=<user> --as-group=<group>
oc auth can-i create managedclustersets/bind.cluster.open-cluster-management.io --as=<user> --as-group=<group>
```

A `yes` on the first four, in a namespace bound to a cluster set, is spoke power.

## Virtualization

A hub role opens the console tab. Spoke roles allow the action, as the user, not as the work service account.

| Who | Hub | Each managed cluster |
| --- | --- | --- |
| Viewer | `acm-vm-fleet:view` | `kubevirt.io:view` and `acm-vm-extended:view` |
| VM administrator, not cluster-admin | `acm-vm-fleet:view` | `kubevirt.io:admin` and `acm-vm-extended:admin` |
| Cross-cluster live migration | `acm-vm-fleet:admin` | On source and destination: `kubevirt.io:admin`, `acm-vm-extended:admin`, and cluster-scoped `acm-vm-cluster-migration:view` |

`kubevirt.io:admin` includes `HyperConverged` in `openshift-cnv`. It is not OpenShift `cluster-admin`.

In-cluster migration panels still need `migrations.kubevirt.io:view`, `migrations.kubevirt.io:storagemigrate`, and `migrations.kubevirt.io:storagemigrate-multins` until those rules are folded into the extended roles. Confirm the name with `oc get clusterrole`. The console has shown an underscore (`storagemigrate_multins`). The product request uses a hyphen (`storagemigrate-multins`).

OpenShift Virtualization aggregates `kubevirt.io:admin` into the namespace `admin` role unless you opt out. On 4.22, `spec.roleAggregationStrategy: Manual` is that opt-out, and it is Developer Preview. Set it only after the explicit bindings exist. Do not strip the aggregation labels.

Do not bind the retired names `kubevirt.io-acm-managed:*` or `kubevirt.io-acm-hub:*`.

## Policies

A policy creates and removes the spoke binding from one place. It cannot split two people who share a username, and it cannot edit a directory.

Put the policy in a namespace whose placements only see the intended clusters, and only clusters where the ClusterRole exists. A second policy, placed only on `local-cluster`, binds the same group to the hub console role.

`pruneObjectBehavior` is a field on the `ConfigurationPolicy`, not on the parent `Policy`. On the parent it is dropped. `DeleteIfCreated` removes an object the policy created when you delete that object from the policy. The appendix puts the field on the configuration policy.

You can also enforce the `MulticlusterRoleAssignment` on the hub. The controller still creates the spoke bindings. The same people who may create a policy may grant spoke power. See the table above.

Remove one person from the hub group to revoke them. Remove the binding from the policy to revoke the zone.

## Observability

Collectors should stay service accounts. The person querying must not borrow that identity.

Today, what someone can query follows the clusters their cluster set role lets them see. Hub role setup is in [Secure clusters](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html-single/secure_clusters/index), "Enabling RBAC for Observability."

Scoping queries with `MulticlusterRoleAssignment` is the planned direction. It is not generally available. Logs need a tighter rule than metrics. A metric is a number. A log line can contain tokens, audit events, and virtual-machine console output.

## Identity

| Setup | When to use it |
| --- | --- |
| One identity provider on the hub and on the spokes. Bind groups. | People log in on both. The console and `oc login` then carry the same username and the same groups. |
| Hub identity provider only. Spoke bindings use those group strings. No user provider on the spokes. | Direct spoke login is forbidden. The console still works. Keep a break-glass administrator. |
| Zone-qualified groups such as `zonea-vm-admins`. | Two zones or two directories. An unqualified `AP001` binding would grant both people who share that short name. |

Removing the spoke provider does not stop the console path. Removing the hub provider does not stop direct spoke login.

## Checklist

1. Keep controller actions on service accounts. Run a person's click as that person.
2. Decide whether those people log in on the spokes. If they do, use one identity provider. If they do not, do not configure a user provider there.
3. Bind each team's group to `open-cluster-management:managedclusterset:view:<set>`. Have a platform owner create the `ManagedClusterSetBinding` with the `bind` role.
4. Keep create permission on `MulticlusterRoleAssignment`, `Policy`, `Placement`, and `ManifestWork` with the people who are allowed to grant spoke power.
5. Enable `fine-grained-rbac` before using the virtualization roles.
6. Grant spoke permissions with one `MulticlusterRoleAssignment` per group. Leave `targetNamespaces` empty unless the hub team can keep the list current.
7. For applications, use the spoke-local path unless the customer allows centralized access. 
8. On a spoke, confirm the grant:

```bash
oc auth can-i get virtualmachines.kubevirt.io -n team-a --as=<hub-username> --as-group=zonea-vm-admins
```

9. In the spoke audit log, confirm a console click has an `impersonatedUser`. A work-agent change should still show `system:serviceaccount`.

## Sources

- [Secure clusters, ACM 2.17](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html-single/secure_clusters/index)
- [Fine-grained RBAC for virtual machines](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html-single/secure_clusters/index#fine-grain-mca)
- [ManagedClusterSet](https://open-cluster-management.io/docs/concepts/cluster-inventory/managedclusterset/)

---

## A. Enable fine-grained RBAC

In ACM 2.16 and 2.17 the component is off by default. On the hub:

```bash
oc patch mch multiclusterhub -n open-cluster-management --type=json \
  -p='[{"op":"add","path":"/spec/overrides/components/-","value":{"name":"fine-grained-rbac","enabled":true}}]'
```

If `fine-grained-rbac` is already in `spec.overrides.components`, set `enabled: true` on that entry. Do not append a second one.

## B. MulticlusterRoleAssignment, cluster-wide

Empty `targetNamespaces` is a `ClusterRoleBinding` on each selected cluster. Create this on the hub.

```yaml
apiVersion: rbac.open-cluster-management.io/v1beta1
kind: MulticlusterRoleAssignment
metadata:
  name: zonea-vm-admins
  namespace: site-virt
spec:
  subject:
    kind: Group
    name: zonea-vm-admins
  placement:
    name: remote-vm-sites
    namespace: site-virt
  roleAssignments:
    - name: kubevirt-admin
      clusterRole: kubevirt.io:admin
    - name: vm-extended-admin
      clusterRole: acm-vm-extended:admin
```

## C. MulticlusterRoleAssignment, listed namespaces

One `RoleBinding` in each named namespace. No access anywhere else.

```yaml
apiVersion: rbac.open-cluster-management.io/v1beta1
kind: MulticlusterRoleAssignment
metadata:
  name: zonea-vm-admins-namespaces
  namespace: site-virt
spec:
  subject:
    kind: Group
    name: zonea-vm-admins
  placement:
    name: remote-vm-sites
    namespace: site-virt
  roleAssignments:
    - name: kubevirt-admin
      clusterRole: kubevirt.io:admin
      targetNamespaces:
        - team-a-vms
        - team-b-vms
    - name: vm-extended-admin
      clusterRole: acm-vm-extended:admin
      targetNamespaces:
        - team-a-vms
        - team-b-vms
```

## D. Policy that enforces the spoke binding

`pruneObjectBehavior` is on the `ConfigurationPolicy`. Create the policy, the placement, and the placement binding on the hub, in a namespace a platform owner controls.

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: Policy
metadata:
  name: zonea-vm-admins
  namespace: open-cluster-management-global-set
spec:
  remediationAction: enforce
  disabled: false
  policy-templates:
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: zonea-vm-admins-kubevirt
        spec:
          remediationAction: enforce
          severity: high
          pruneObjectBehavior: DeleteIfCreated
          object-templates:
            - complianceType: musthave
              objectDefinition:
                apiVersion: rbac.authorization.k8s.io/v1
                kind: ClusterRoleBinding
                metadata:
                  name: zonea-vm-admins-kubevirt
                roleRef:
                  apiGroup: rbac.authorization.k8s.io
                  kind: ClusterRole
                  name: kubevirt.io:admin
                subjects:
                  - kind: Group
                    apiGroup: rbac.authorization.k8s.io
                    name: zonea-vm-admins
---
apiVersion: cluster.open-cluster-management.io/v1beta1
kind: Placement
metadata:
  name: zonea-clusters
  namespace: open-cluster-management-global-set
spec:
  predicates:
    - requiredClusterSelector:
        labelSelector:
          matchLabels:
            zone: zonea
  tolerations:
    - key: cluster.open-cluster-management.io/unreachable
      operator: Equal
    - key: cluster.open-cluster-management.io/unavailable
      operator: Equal
---
apiVersion: policy.open-cluster-management.io/v1
kind: PlacementBinding
metadata:
  name: zonea-vm-admins
  namespace: open-cluster-management-global-set
placementRef:
  apiGroup: cluster.open-cluster-management.io
  kind: Placement
  name: zonea-clusters
subjects:
  - apiGroup: policy.open-cluster-management.io
    kind: Policy
    name: zonea-vm-admins
```
