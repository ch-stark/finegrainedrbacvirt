# Architecture and concepts

The hub decides what a person can see. The managed cluster decides what that person can do. This page is the short form. The reference is [Fine-Grained RBAC Across an ACM Fleet](rbac-acm-fleet.md), sections 1 through 5 and section 11.

Checked against the ACM 2.17 Secure clusters guide. Confirm fields with `oc explain` on the hub you are changing.

## Two paths

A console click:

```
Identity provider
    |
    v
ACM console on the hub
    |
    v
Hub role and cluster-set role
    |
    v
cluster-proxy impersonates the hub user and groups
    |
    v
Managed-cluster RBAC
```

The spoke audit log shows the impersonated user. cluster-proxy does not apply manifests. The work agent does that, as its own service account.

A controller or a policy:

```
Hub object
    |
    v
Controller or work agent
    |
    v
Service account on the managed cluster
```

The service account's role is the ceiling for anyone who can cause that controller to run. Do not create one service account per hub user.

## What to choose

| Work | Start here |
| --- | --- |
| Virtual machines that repeat across clusters | [OpenShift Virtualization RBAC](rbac-virtualization.md) |
| Applications owned by the team on the spoke | [Application RBAC](rbac-applications.md) |
| Argo CD on the hub | [GitOps integration](rbac-gitops.md) |
| Metrics and logs | Section 9 of the [reference](rbac-acm-fleet.md). Hub view of the cluster gates metrics in ACM 2.17. Namespace queries are Technology Preview. |

## Identity

The group string on the hub token and the group string on the spoke binding are the same characters. ACM does not translate directories. Use one identity provider when the same people also log in on the spokes. The console path does not consult the spoke directory.

## Cluster sets

For a set named `zone-a`, bind the team to `open-cluster-management:managedclusterset:view:zone-a`. A platform owner with `open-cluster-management:managedclusterset:bind:zone-a` creates the `ManagedClusterSetBinding`. A `Placement` only selects sets that are already bound into its namespace.

`open-cluster-management:view:zone-a` is the view role for a managed cluster of that name. It is a different role from the cluster-set role.

View does not grant virtual machines, applications, or metrics beyond what the observability procedure attaches to cluster view. It does not open Argo CD.

## Hub objects that grant spoke power

Creating these on the hub can grant permissions on the clusters they reach:

| Object | Effect |
| --- | --- |
| `MulticlusterRoleAssignment` | Binds ClusterRoles on the selected clusters for the named subject |
| `Policy` with a `PlacementBinding` | Can ship any manifest in the template, including a `ClusterRoleBinding` |
| `ManifestWork` | The work agent applies it as a privileged service account |
| `Placement` | Chooses the clusters for the objects above |
| `ManagedClusterSetBinding` | Lets placements in that namespace see the set. Creating it requires `managedclustersets/bind` |

Give namespace `admin` on a namespace bound to a production set only to people who may grant that spoke power. Section 11 of the reference has the `oc auth can-i` commands.
