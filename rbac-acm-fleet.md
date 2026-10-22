# RBAC in ACM: the patterns you need

ACM is useful in three places: applications, virtual machines, and observability. Each place has more than one pattern. A team can keep the grant on the spoke. A platform team can write it once on the hub and project it. Some grants need both. A few cases also need an admission controller, because the role that allows the update is still too wide for the change you want to permit.

This is a deep dive into those concepts. The patterns are not interchangeable. A virtual machine fleet and an application platform often choose opposite ones, and both choices can be right.

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

## The three places

The same hub and spoke split shows up in applications, virtual machines, and observability. Centralized means the hub holds the grant and projects it. Decentralized means the grant is created on the spoke, and the hub may only supply the console or the query.

| Place | Centralized | Decentralized |
| --- | --- | --- |
| Applications | A hub `Policy` creates the project `RoleBinding`s. OpenShift GitOps applies from a `GitOpsCluster`, as one spoke service account. | The team binds `admin` or `view` on the spoke. Project names can differ per cluster. |
| Virtual machines | One `MulticlusterRoleAssignment` per group. The controller creates the spoke bindings. This is the usual VM pattern, because the same role repeats across the zone. | Bind `kubevirt.io:admin` on the spoke yourself. The console tab is still a hub role. |
| Observability | The cluster set role decides which clusters a person may query. Finer scope, down to a namespace or a virtual machine, is the planned use of the same assignment. | Collectors stay service accounts on the spoke. A person who queries that cluster's own store is evaluated there, and ACM is not in that path. |

You can mix them. Virtual machines often go centralized while the applications on those same clusters stay decentralized. Observability collection stays decentralized even when the query is centralized. The sections below are the concepts behind each cell.

Admission control is the extra gate, not a fourth product area. Use it when a role cannot express the limit. Appendix E is one case: a namespace admin may add `argocd.argoproj.io/managed-by` and no other new label.

## What you need, by version

| Capability | Where it stands |
| --- | --- |
| Cluster sets, policies, placements, cluster-proxy | Current ACM |
| `MulticlusterRoleAssignment` for OpenShift Virtualization | Generally available in ACM 2.16 and 2.17. The API is still `rbac.open-cluster-management.io/v1beta1`. Generally available means Red Hat supports this use. It does not mean the API has moved to `v1`. The `fine-grained-rbac` component on `MultiClusterHub` is off until you enable it. |
| Applications | Current ACM. Spoke-local bindings and a hub policy are both valid. The default GitOps account is a cluster administrator. |
| Observability query scope through the same assignment | Not generally available. Collection stays a service account. There will not be a second API. |
| Admission control | For a limit a role cannot express. Appendix E. |

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
| `Placement` | Does not apply anything by itself. It aims the objects above. A placement only sees sets bound into its namespace. |
| `ManagedClusterSetBinding` | Projects a set into a namespace, so placements there can select those clusters. Creating it requires `managedclustersets/bind`, not namespace admin alone. |
| `GitOpsCluster` | Registers the placement's clusters with OpenShift GitOps. The default account on those clusters is a cluster administrator. |

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
oc auth can-i create gitopsclusters.apps.open-cluster-management.io -n openshift-gitops --as=<user> --as-group=<group>
```

A `yes` on the first four, or on `GitOpsCluster`, in a namespace bound to a cluster set, is spoke power.

## Virtualization

Virtual machines are the place that usually goes centralized. The same group needs the same ClusterRoles on every cluster in the zone, and cross-cluster migration needs both clusters at once. One `MulticlusterRoleAssignment` per group is that pattern. The worked example above is the full path.

The decentralized pattern still works. Bind `kubevirt.io:admin` and `acm-vm-extended:admin` on the spoke, by hand or with a local process. The console tab does not follow that binding. `acm-vm-fleet:view` stays on the hub. Without the hub role the tab does not open. Without the spoke binding the click returns `Forbidden`.

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

## Applications

Applications are the place where the two patterns diverge.

**Decentralized.** The team owns its projects. Someone on the spoke creates the `RoleBinding` for `admin` or `view`. The group string matches the hub group when those people also use the console. A developer who never logs in to the hub does not need a cluster set role. Project names can differ per cluster. That is the normal application layout, and it is why a hub-maintained namespace list is a poor fit here.

**Centralized, with a policy.** A platform owner ships the bindings from the hub. Appendix D is the community sample. An SRE group gets `cluster-admin`. Each application group gets `admin` or `view` in its project. The policy creates the groups, the projects, and the bindings. Use it when the customer has accepted that the hub may grant namespace roles on the spokes. `MulticlusterRoleAssignment` can list namespaces too. The list does not grow when someone creates a project, and a long list can hit the `ManifestWork` size limit. For applications, prefer the policy, or the spoke-local binding, over that list.

**Centralized apply, through OpenShift GitOps.** A `GitOpsCluster` in the Argo CD namespace points at a `Placement`. The placement only sees cluster sets bound into that namespace. The controller creates one cluster secret per selected cluster, in `openshift-gitops` by default. Push is the default: Argo CD on the hub applies to the spoke. The secret carries the `application-manager` account, and that account is a cluster administrator on the managed cluster, because the application subscription add-on uses it. Every Application aimed at that secret shares that ceiling. The person who clicked Sync is not the subject on the spoke.

Narrow the account when the team should not be a cluster administrator. On the hub, create a `ManagedServiceAccount` and a `ClusterPermission`, and set `managedServiceAccountRef` on the `GitOpsCluster`. The new account is still one account for every Application that uses the secret. The `AppProject` limits the repositories, the clusters, and the namespaces. It does not change which account applies the manifests. Argo CD's own RBAC, in `argocd-rbac-cm` and in project roles, decides who may see and sync in the GitOps UI. The spoke still evaluates the service account.

The same ApplicationSet can pull instead. The work agent applies a `ManifestWork`. In the ACM 2.16 GitOps documentation the Argo CD agent is Technology Preview. Enabling that add-on through `GitOpsCluster` turns push off for those applications. The agent connects out from the spoke. It still applies as a service account.

**What works now.** ACM fine-grained RBAC and Argo CD RBAC do not configure each other. A hub `RoleBinding` does not open the Argo CD UI. An Argo CD policy does not create a spoke binding. You keep both.

The ACM console shows a team's Applications when the group has a `RoleBinding` in that namespace on the hub. That is namespace RBAC on the hub. The cluster set role is still what decides which clusters the group may see.

The Argo CD UI has its own policy. The rules live in `argocd-rbac-cm`, and the OpenShift GitOps CR carries the same text in `spec.rbac.policy`. Map an OpenShift group onto an Argo CD role in that policy. With Applications in any namespace, an application in the policy is `<project>/<namespace>/<name>`. A group can be allowed to sync `team-a/team-a/*` and be refused everywhere else. The instance has to read group scopes, or those group lines never match.

**On the hub, teams use their own namespaces.** `spec.sourceNamespaces` on the hub Argo CD CR lists the namespaces that may hold `Application` objects. `spec.applicationSet.sourceNamespaces` lists the namespaces that may hold `ApplicationSet` objects. ApplicationSets in any namespace is generally available in OpenShift GitOps 1.22. The Application an ApplicationSet generates stays in the ApplicationSet's namespace, so that namespace also belongs in `spec.sourceNamespaces`.

The `AppProject` is the wall around that namespace. `sourceRepos`, `destinations`, and the resource allow and deny lists decide what the team may name. Argo CD enforces the project before the spoke account is asked to apply anything.

**On the spoke, the agent has a default landing place.** It writes the hub Application into the Argo CD namespace on the spoke. The spoke does not need Applications in any namespace for that. `destinationBasedMapping`, or a cluster annotation, can place the Application in a team namespace on the spoke. That spoke then needs `sourceNamespaces` for the namespace you chose.

**Impersonation is standard mode only.** Upstream Argo CD 3.5 applies it to every API operation, not only sync: get, logs, delete, and resource actions. OpenShift GitOps 1.22 ships that as Technology Preview. Turn it on with `application.sync.impersonation.enabled` in `argocd-cm`, and name the account in `AppProject.spec.destinationServiceAccounts`, per destination server and namespace. The account is a service account. It is not the person who clicked Sync. The agent path does not use this. The `AppProject` limits stay. Impersonation chooses which account acts. It does not replace the project.

## Policies

A policy is one centralized pattern from the applications section. It creates and removes the spoke binding from one place. It cannot split two people who share a username, and it cannot edit a directory.

Put the policy in a namespace whose placements only see the intended clusters, and only clusters where the ClusterRole exists. A second policy, placed only on `local-cluster`, binds the same group to the hub console role.

`pruneObjectBehavior` is a field on the `ConfigurationPolicy`, not on the parent `Policy`. On the parent it is dropped. `DeleteIfCreated` removes an object the policy created when you delete that object from the policy. The appendix puts the field on the configuration policy.

Appendix D is the community sample for application namespaces. It creates the groups, the projects, and the bindings. Virtual machine roles stay on `MulticlusterRoleAssignment`.

You can also enforce the `MulticlusterRoleAssignment` on the hub. The controller still creates the spoke bindings. The same people who may create a policy may grant spoke power. See the table above.

Remove one person from the hub group to revoke them. Remove the binding from the policy to revoke the zone.

## Admission

Most grants stop at a role. Some do not. The question is no longer "may this person update the namespace?" It is "which label may they add?" A role that allows the update allows every label. An admission controller is how you refuse the rest. Treat it as a special case beside applications, virtual machines, and observability, not as a replacement for them.

A role can allow an update and still be too wide. RBAC decides that this person may update the namespace. It does not decide which label they may add.

The namespace admin may add `argocd.argoproj.io/managed-by`. Gatekeeper denies any other new label key. A namespace whose name contains `openshift` is out of scope. A user whose name starts with `system:` is out of scope, so a controller can still set labels.

The rule compares keys. A key that is present now and was absent before is a new label. A changed value, or a removed key, is not what this rule checks.

Appendix E is the constraint. Gatekeeper must already be installed on the cluster. Apply the template first. The constraint kind does not exist until the template is established. An ACM policy can ship both. On that policy, `inform` becomes Gatekeeper `warn`, and `enforce` becomes `deny`.

## Observability

Observability uses both patterns at once, and the two halves do not share an identity.

**Collection is decentralized.** The collector on each spoke is a service account. The person who queries must not borrow that account. A scrape and a log line leave the cluster as the collector, then land in the hub store.

**The query is centralized.** Today, what someone can query follows the clusters their cluster set role lets them see. A user who can see three clusters can query those three. Hub role setup is in [Secure clusters](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html-single/secure_clusters/index), "Enabling RBAC for Observability."

**The finer query is the centralized pattern that is not ready.** Scoping metrics, logs, and traces with `MulticlusterRoleAssignment` is the planned direction. It is not generally available. There will not be a second API. Logs need a tighter rule than metrics. A metric is a number. A log line can contain tokens, audit events, and virtual-machine console output.

**The decentralized query still exists.** A person who logs in on one spoke and opens that cluster's own monitoring is evaluated by that cluster's RBAC. ACM is not in that path. The hub store is the path that uses the cluster set, and later the assignment.

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
4. Keep create permission on `MulticlusterRoleAssignment`, `Policy`, `Placement`, `ManifestWork`, and `GitOpsCluster` with the people who are allowed to grant spoke power.
5. Enable `fine-grained-rbac` before using the virtualization roles.
6. For virtual machines, grant spoke permissions with one `MulticlusterRoleAssignment` per group. Leave `targetNamespaces` empty unless the hub team can keep the list current. A spoke-local binding is the decentralized alternative. The console role stays on the hub.
7. For applications, choose. Spoke-local bindings when the team owns the projects. Appendix D when the hub should grant them. A narrowed GitOps service account when Git applies the manifests. The default `application-manager` account is a cluster administrator.
8. Add an admission controller only for a limit a role cannot express. Appendix E allows one namespace label.
9. On a spoke, confirm the grant:

```bash
oc auth can-i get virtualmachines.kubevirt.io -n team-a --as=<hub-username> --as-group=zonea-vm-admins
```

10. In the spoke audit log, confirm a console click has an `impersonatedUser`. A work-agent change, and a GitOps sync, should still show `system:serviceaccount`.

## Sources

- [Secure clusters, ACM 2.17](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html-single/secure_clusters/index)
- [Fine-grained RBAC for virtual machines](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html-single/secure_clusters/index#fine-grain-mca)
- [ManagedClusterSet](https://open-cluster-management.io/docs/concepts/cluster-inventory/managedclusterset/)
- [Application workload RBAC sample](https://github.com/open-cluster-management-io/policy-collection/blob/main/community/AC-Access-Control/policy-configure-appworkloads-rbac-sample.yaml)
- [Gatekeeper constraint templates](https://open-policy-agent.github.io/gatekeeper/website/docs/constrainttemplates/)
- [ACM GitOps, 2.16](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.16/html/gitops/gitops-overview)
- [OpenShift GitOps 1.22 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.22/html/release_notes/index)
- [Argo CD 3.5 impersonation](https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/app-sync-using-impersonation/)

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

## D. Policy for application workload RBAC

This is the [community sample](https://github.com/open-cluster-management-io/policy-collection/blob/main/community/AC-Access-Control/policy-configure-appworkloads-rbac-sample.yaml) for access to the applications on the managed clusters. ACM console roles stay on the hub.

Two applications are running. Application X is in `project-x`. Application Y is in `project-y`.

| Group | Binding |
| --- | --- |
| `SreAdminGrp` | `cluster-admin` on the cluster |
| `AppX-AdminGrp` | `admin` in `project-x` |
| `AppX-ViewGrp` | `view` in `project-x` |
| `AppY-AdminGrp` | `admin` in `project-y` |
| `AppY-ViewGrp` | `view` in `project-y` |

Each group is created with `users` empty. Add people through the identity provider.

`remediationAction` is `inform` on the policy and on the configuration policy. The parent value overrides the template. `inform` reports drift. Set both to `enforce` to create the objects. `pruneObjectBehavior: DeleteIfCreated` is on the `ConfigurationPolicy`. Removing an object from the policy then deletes it on the cluster.

Create the namespace `app-workloads` on the hub, then the policy, the placement, and the placement binding there. A platform owner controls that namespace. Label a cluster `app-rbac: enabled` to bring it into scope. On each selected cluster, `SreAdminGrp` is `cluster-admin`.

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: Policy
metadata:
  name: policy-configure-appworkloads-rbac
  namespace: app-workloads
  annotations:
    policy.open-cluster-management.io/standards: NIST SP 800-53
    policy.open-cluster-management.io/categories: AC Access Control
    policy.open-cluster-management.io/controls: AC-3 Access Enforcement
spec:
  remediationAction: inform
  disabled: false
  policy-templates:
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: policy-configure-appworkloads-rbac-example
        spec:
          remediationAction: inform
          severity: high
          pruneObjectBehavior: DeleteIfCreated
          object-templates:
            - complianceType: musthave
              objectDefinition:
                kind: Group
                apiVersion: user.openshift.io/v1
                metadata:
                  name: SreAdminGrp
                users: null
            - complianceType: musthave
              objectDefinition:
                kind: Group
                apiVersion: user.openshift.io/v1
                metadata:
                  name: AppX-AdminGrp
                users: null
            - complianceType: musthave
              objectDefinition:
                kind: Group
                apiVersion: user.openshift.io/v1
                metadata:
                  name: AppX-ViewGrp
                users: null
            - complianceType: musthave
              objectDefinition:
                kind: Group
                apiVersion: user.openshift.io/v1
                metadata:
                  name: AppY-AdminGrp
                users: null
            - complianceType: musthave
              objectDefinition:
                kind: Group
                apiVersion: user.openshift.io/v1
                metadata:
                  name: AppY-ViewGrp
                users: null
            - complianceType: musthave
              objectDefinition:
                apiVersion: v1
                kind: Namespace
                metadata:
                  name: project-x
                  labels:
                    purpose: namespace-for-sample-AppX-artifacts
            - complianceType: musthave
              objectDefinition:
                apiVersion: v1
                kind: Namespace
                metadata:
                  name: project-y
                  labels:
                    purpose: namespace-for-sample-AppY-artifacts
            - complianceType: musthave
              objectDefinition:
                kind: ClusterRoleBinding
                apiVersion: rbac.authorization.k8s.io/v1
                metadata:
                  name: SreAdmin-Binding
                subjects:
                  - kind: Group
                    apiGroup: rbac.authorization.k8s.io
                    name: SreAdminGrp
                roleRef:
                  apiGroup: rbac.authorization.k8s.io
                  kind: ClusterRole
                  name: cluster-admin
            - complianceType: musthave
              objectDefinition:
                kind: RoleBinding
                apiVersion: rbac.authorization.k8s.io/v1
                metadata:
                  name: AppX-Admin-Binding
                  namespace: project-x
                subjects:
                  - kind: Group
                    apiGroup: rbac.authorization.k8s.io
                    name: AppX-AdminGrp
                roleRef:
                  apiGroup: rbac.authorization.k8s.io
                  kind: ClusterRole
                  name: admin
            - complianceType: musthave
              objectDefinition:
                kind: RoleBinding
                apiVersion: rbac.authorization.k8s.io/v1
                metadata:
                  name: AppX-View-Binding
                  namespace: project-x
                subjects:
                  - kind: Group
                    apiGroup: rbac.authorization.k8s.io
                    name: AppX-ViewGrp
                roleRef:
                  apiGroup: rbac.authorization.k8s.io
                  kind: ClusterRole
                  name: view
            - complianceType: musthave
              objectDefinition:
                kind: RoleBinding
                apiVersion: rbac.authorization.k8s.io/v1
                metadata:
                  name: AppY-Admin-Binding
                  namespace: project-y
                subjects:
                  - kind: Group
                    apiGroup: rbac.authorization.k8s.io
                    name: AppY-AdminGrp
                roleRef:
                  apiGroup: rbac.authorization.k8s.io
                  kind: ClusterRole
                  name: admin
            - complianceType: musthave
              objectDefinition:
                kind: RoleBinding
                apiVersion: rbac.authorization.k8s.io/v1
                metadata:
                  name: AppY-View-Binding
                  namespace: project-y
                subjects:
                  - kind: Group
                    apiGroup: rbac.authorization.k8s.io
                    name: AppY-ViewGrp
                roleRef:
                  apiGroup: rbac.authorization.k8s.io
                  kind: ClusterRole
                  name: view
---
apiVersion: cluster.open-cluster-management.io/v1beta1
kind: Placement
metadata:
  name: app-workload-clusters
  namespace: app-workloads
spec:
  predicates:
    - requiredClusterSelector:
        labelSelector:
          matchLabels:
            app-rbac: enabled
  tolerations:
    - key: cluster.open-cluster-management.io/unreachable
      operator: Equal
    - key: cluster.open-cluster-management.io/unavailable
      operator: Equal
---
apiVersion: policy.open-cluster-management.io/v1
kind: PlacementBinding
metadata:
  name: policy-configure-appworkloads-rbac
  namespace: app-workloads
placementRef:
  apiGroup: cluster.open-cluster-management.io
  kind: Placement
  name: app-workload-clusters
subjects:
  - apiGroup: policy.open-cluster-management.io
    kind: Policy
    name: policy-configure-appworkloads-rbac
```

## E. Gatekeeper: one label on a namespace

A namespace admin may add `argocd.argoproj.io/managed-by` and no other new label. The template is the rule. The constraint turns it on for `Namespace` updates.

`enforcementAction: deny` matches a policy whose `remediationAction` is `enforce`. Use `warn` when the policy is `inform`.

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8snamespacelabelchange
  annotations:
    description: >-
      Allows a non-system user to add only argocd.argoproj.io/managed-by
      on a namespace. Skips namespaces whose name contains openshift.
spec:
  crd:
    spec:
      names:
        kind: K8sNamespaceLabelChange
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package namespacechange

        violation[{"msg": msg}] {
          input.review.operation == "UPDATE"
          input.review.kind.kind == "Namespace"
          not contains(lower(input.review.object.metadata.name), "openshift")
          not startswith(input.review.userInfo.username, "system:")

          new_labels := object.get(input.review.object.metadata, "labels", {})
          old_meta := object.get(object.get(input.review, "oldObject", {}), "metadata", {})
          old_labels := object.get(old_meta, "labels", {})

          added := {key |
            new_labels[key]
            not old_labels[key]
          }

          count(added) > 0
          added_label := added[_]
          added_label != "argocd.argoproj.io/managed-by"

          msg := sprintf("Added label key '%v' is not allowed on namespace '%v'. Only 'argocd.argoproj.io/managed-by' is permitted.", [added_label, input.review.object.metadata.name])
        }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sNamespaceLabelChange
metadata:
  name: namespace-argocd-managed-by-only
spec:
  enforcementAction: deny
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Namespace"]
```
