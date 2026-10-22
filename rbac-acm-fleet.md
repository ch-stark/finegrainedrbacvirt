# RBAC in ACM: the patterns you need

This is a deep dive into RBAC in ACM: the use cases, and the patterns you can actually implement.

"We gave the team access, but the console says `Forbidden`."

On one cluster, RBAC is one question: which role is bound to this user? On a fleet, that same sentence can fail in several places. Each place can say no on its own.

The **hub** decides what a person may see: which clusters, which console tabs, which queries. The **spoke** decides what they may do. A console click that returns `Forbidden` is usually a hub role without a matching spoke binding.

## Start here

- ACM is useful in three places: applications, virtual machines, and observability. Each place can be centralized or decentralized. You can mix them.
- A virtual machine fleet usually goes centralized, because the same group and the same roles repeat on every cluster in the zone.
- Application teams usually stay decentralized, because project names differ per cluster. A hub policy is the centralized option when the customer accepts it.
- Observability collection stays a service account on the spoke. The query on the hub follows the cluster set. Finer query scope is not generally available yet.
- An admission controller is for the case a role cannot express. The role allows the update. The controller refuses one specific change.
- GitOps has its own RBAC. It does not follow the ACM binding, and the ACM binding does not open the Argo CD UI.
- Whoever can create a `Policy`, a `MulticlusterRoleAssignment`, a `ManifestWork`, or a `GitOpsCluster` can grant spoke power. Treat that like `cluster-admin`.

## Hub and spoke

| | Hub | Spoke |
| --- | --- | --- |
| Question | What may this person see? | What may this person do? |
| A console click | Cluster set role, hub console role, through cluster-proxy | The apiserver, as the impersonated user and groups |
| A controller, a policy, or GitOps | The hub object that submitted the work | A service account |

Cluster-proxy reaches the managed cluster API without publishing it. On a console click it impersonates the hub username and the hub groups. The audit log has both names, including `impersonatedUser`.

The work agent, the policy agent, the observability collector, and GitOps do not impersonate. The audit line names `system:serviceaccount:...`. That account's role is the ceiling for everyone who can trigger the work. Do not create one service account per hub user. That repeats the problem.

```
Person --> Hub console --> cluster-proxy --> Spoke API
           (what can I     (impersonates     (what may this
            see?)           user + groups)    user do?)

Hub object --> work agent or GitOps --> Spoke API
(Policy, ManifestWork, Application)   (ceiling = service account)
```

The console path needs the hub to be self-managed (`local-cluster`). The group string on the hub token and the group string on the spoke binding must be the same characters. ACM does not translate directories. Two people who share a short name, such as `AP001` in two directories, are one Kubernetes subject.

## Choose a pattern per place

Centralized means the hub holds the grant and projects it. Decentralized means the grant is created on the spoke. The hub may still supply the console tab or the query.

| Place | Centralized | Decentralized |
| --- | --- | --- |
| Applications | A hub policy creates the project bindings. OpenShift GitOps applies through a `GitOpsCluster`, as one spoke service account. | The team binds `admin` or `view` on the spoke. Project names can differ per cluster. |
| Virtual machines | One `MulticlusterRoleAssignment` per group. This is the usual VM pattern. | Bind `kubevirt.io:admin` on the spoke. The console tab stays a hub role. |
| Observability | The cluster set decides which clusters a person may query. Namespace and VM scope is planned, and not generally available. | Collectors stay service accounts. A query against that cluster's own store is evaluated there. |

| Capability | Where it stands |
| --- | --- |
| Cluster sets, policies, placements, cluster-proxy | Current ACM |
| `MulticlusterRoleAssignment` for OpenShift Virtualization | Generally available in ACM 2.16 and 2.17. The API is still `rbac.open-cluster-management.io/v1beta1`. The `fine-grained-rbac` component is off until you enable it. |
| Applications, including OpenShift GitOps | Current. Spoke-local bindings and a hub policy are both valid. The default GitOps account is a cluster administrator. |
| Observability query scope through the same assignment | Not generally available. There will not be a second API. |
| Admission control | For a limit a role cannot express. Appendix E. |

## Identity

Identity is the username and the groups the rest of the system will trust.

| Setup | When to use it |
| --- | --- |
| One identity provider on the hub and on the spokes. Bind groups. | People log in on both. The console and `oc login` carry the same username and the same groups. |
| Hub identity provider only. Spoke bindings use those group strings. | People do not log in on the spokes. The console still works. Keep a break-glass administrator. |
| Zone-qualified groups such as `zonea-vm-admins`. | Two zones or two directories. An unqualified `AP001` binding would grant both people. |

The console never asks the spoke identity provider. Leave the user provider off the spokes when those people must not log in there. That is simpler than an admission rule on tokens.

## Cluster sets

A cluster set is how the hub answers "which clusters may this group see?"

For a set named `zone-a`, ACM creates three roles. Bind them with a `ClusterRoleBinding`.

| Role | What it grants |
| --- | --- |
| `open-cluster-management:managedclusterset:view:zone-a` | See the clusters in that set, and the resources the console attaches to that view. |
| `open-cluster-management:managedclusterset:admin:zone-a` | Manage the set. |
| `open-cluster-management:managedclusterset:bind:zone-a` | View, plus create a `ManagedClusterSetBinding` for that set. |

`view` does not create the binding. `bind` does. A `Placement` only selects clusters from sets that are already bound into its namespace. The platform owner creates that binding. The team receives `view`.

`view` does not grant virtual machines, applications, logs, or Argo CD. A developer who works only on the spoke does not need a hub login. ACM still controls and monitors that cluster.

Keep a `global-set` for platform owners. Do not hand that view to every team.

## Virtual machines

Virtual machines usually go centralized. Six things push that way:

1. The personas repeat: viewer, VM administrator, migration operator. The same group needs the same role on every cluster in the zone.
2. The roles are ClusterRoles that exist on every cluster running OpenShift Virtualization. Binding them by hand forty times is how they drift.
3. Cross-cluster live migration needs the hub role and matching spoke roles on the source and the destination at the same time.
4. Many VM teams use only the ACM console. Hub identity plus a projected spoke binding is the whole story. The spoke identity provider can stay off.
5. Revocation is one edit. Remove a person from the hub group to revoke them. Remove the assignment to revoke the zone.
6. The list of people who can grant spoke power stays short, because the grant is a hub object. That object is powerful. Section "Hub objects that equal spoke power" is the cost.

`MulticlusterRoleAssignment` is the object. One per group. It names a subject, a `Placement`, and the ClusterRoles. The controller creates the spoke bindings.

| `targetNamespaces` | Result on each selected cluster |
| --- | --- |
| Empty or omitted | One `ClusterRoleBinding`. The role applies in every namespace. |
| A list | One `RoleBinding` in each listed namespace. Nothing elsewhere, including `openshift-cnv`. |

Leave `targetNamespaces` empty unless the hub team can keep the list current. The list does not grow when someone creates a project. A long list is merged into one `ManifestWork` and can hit the size limit, about 1.5 MiB. The placement must select only clusters where the ClusterRole exists. A cluster without OpenShift Virtualization will fail a binding to `kubevirt.io:view`.

The decentralized pattern still works. Bind `kubevirt.io:admin` and `acm-vm-extended:admin` on the spoke. The console tab does not follow. `acm-vm-fleet:view` stays on the hub. Without the hub role the tab does not open. Without the spoke binding the click returns `Forbidden`.

| Who | Hub | Each managed cluster |
| --- | --- | --- |
| Viewer | `acm-vm-fleet:view` | `kubevirt.io:view` and `acm-vm-extended:view` |
| VM administrator | `acm-vm-fleet:view` | `kubevirt.io:admin` and `acm-vm-extended:admin` |
| Cross-cluster live migration | `acm-vm-fleet:admin` | On source and destination: those two admin roles, plus cluster-scoped `acm-vm-cluster-migration:view` |

`kubevirt.io:admin` includes `HyperConverged` in `openshift-cnv`. It is not OpenShift `cluster-admin`. Enable `fine-grained-rbac` before the `acm-vm-*` roles exist. Appendix A has the command. The API is still `v1beta1`. Appendices B and C are the assignment, cluster-wide and for a namespace list.

OpenShift Virtualization aggregates `kubevirt.io:admin` into the namespace `admin` role unless you opt out. On 4.22, `spec.roleAggregationStrategy: Manual` is that opt-out, and it is Developer Preview. Set it only after the explicit bindings exist. Do not strip the aggregation labels. Do not bind the retired names `kubevirt.io-acm-managed:*` or `kubevirt.io-acm-hub:*`.

In-cluster migration panels still need `migrations.kubevirt.io:view`, `migrations.kubevirt.io:storagemigrate`, and `migrations.kubevirt.io:storagemigrate-multins` until those rules are folded into the extended roles. Confirm the name with `oc get clusterrole`. The console has shown an underscore. The product request uses a hyphen.

## Applications

Applications usually stay decentralized. The team owns its projects. Someone on the spoke creates the `RoleBinding` for `admin` or `view`. The group string matches the hub group when those people also use the console. A developer who never logs in to the hub does not need a cluster set role.

The centralized option is a policy. Appendix D is the community sample: an SRE group gets `cluster-admin`, and each application group gets `admin` or `view` in its project. Use it when the customer has accepted that the hub may grant namespace roles. A `MulticlusterRoleAssignment` can list namespaces too, and that list has the problems in the virtual machine section. For applications, prefer the spoke binding or the policy.

A policy creates and removes the spoke binding from one place. It cannot split two people who share a username, and it cannot edit a directory. Put it in a namespace whose placements only see the intended clusters. `pruneObjectBehavior` belongs on the `ConfigurationPolicy`. On the parent `Policy` it is dropped. `DeleteIfCreated` removes an object the policy created when you delete that object from the policy. The parent `remediationAction` overrides the template. `inform` reports drift. `enforce` applies the objects.

### OpenShift GitOps

GitOps is centralized apply, and its authorization is a second system. A hub `RoleBinding` does not open the Argo CD UI. An Argo CD policy does not create a spoke binding. Configure both.

A `GitOpsCluster` points at a `Placement`. The placement only sees cluster sets bound into its namespace. The controller creates one cluster secret per selected cluster, in `openshift-gitops` by default. Push is the default: Argo CD on the hub applies to the spoke. The secret carries the `application-manager` account. That account is a cluster administrator on the managed cluster. Every Application aimed at that secret shares that ceiling.

Narrow it with a `ManagedServiceAccount` and a `ClusterPermission` on the hub, and set `managedServiceAccountRef` on the `GitOpsCluster`. The new account is still one account for every Application that uses the secret. The `AppProject` limits repositories (`sourceRepos`), clusters and namespaces (`destinations`), and which resource kinds are allowed. Argo CD enforces the project before the spoke account applies anything.

Who may see and sync in the GitOps UI is `argocd-rbac-cm`, also exposed as `spec.rbac.policy` on the OpenShift GitOps CR. Map an OpenShift group to an Argo CD role there. With Applications in any namespace, an application in that policy is `<project>/<namespace>/<name>`. The instance has to read group scopes, or the group lines never match.

Teams can keep those objects in their own namespaces on the hub. `spec.sourceNamespaces` lists namespaces that may hold `Application` objects. `spec.applicationSet.sourceNamespaces` lists namespaces that may hold `ApplicationSet` objects. ApplicationSets in any namespace is generally available in OpenShift GitOps 1.22. The Application an ApplicationSet generates stays in the ApplicationSet's namespace, so that namespace also belongs in `spec.sourceNamespaces`.

The Argo CD agent pulls instead of waiting for the hub to push. In OpenShift GitOps 1.22 the hybrid layout is generally available: existing applications can stay on the hub controller, and agent applications sync from the spoke. By default the agent writes the hub Application into the Argo CD namespace on the spoke. The spoke does not need Applications in any namespace for that. `destinationBasedMapping`, or a cluster annotation, can place it in a team namespace. That spoke then needs `sourceNamespaces` for the namespace you chose. The agent still applies as a service account.

Impersonation is standard mode only. The agent path does not use it. Upstream Argo CD 3.5 applies it to every API operation, not only sync. OpenShift GitOps 1.22 ships that as Technology Preview. Turn it on with `application.sync.impersonation.enabled` in `argocd-cm`, and name the account in `AppProject.spec.destinationServiceAccounts`. The account is a service account on the destination. It is not the person who clicked Sync. The project limits stay.

## Observability

Collection and query do not share an identity.

The collector on each spoke is a service account. A scrape and a log line leave the cluster as that account. The person who queries must not borrow it.

The query on the hub is centralized. Today it follows the clusters the cluster set role lets the person see. Setup is in [Secure clusters](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.17/html-single/secure_clusters/index), "Enabling RBAC for Observability."

Scoping that query with `MulticlusterRoleAssignment`, down to a namespace or a virtual machine, is the planned direction. It is not generally available. There will not be a second API. Logs need a tighter rule than metrics. A metric is a number. A log line can contain tokens, audit events, and virtual-machine console output.

A person who logs in on one spoke and opens that cluster's own monitoring is on the decentralized path. ACM is not in it.

## Admission

Use an admission controller when the question is no longer "may this person update the object?" and has become "which field may they change?" A role that allows the update allows every label. Appendix E is the example. A namespace admin may add `argocd.argoproj.io/managed-by` and no other new label. Namespaces whose name contains `openshift`, and users whose name starts with `system:`, are skipped, so controllers can still label.

The rule compares keys. A key present now and absent before is a new label. A changed value, or a removed key, is outside this rule. Gatekeeper must already be installed. Apply the template before the constraint. An ACM policy can ship both. `inform` on that policy becomes Gatekeeper `warn`. `enforce` becomes `deny`.

## Hub objects that equal spoke power

Whoever can write the objects below can grant spoke permissions.

| Hub object | What it can do on a spoke |
| --- | --- |
| `MulticlusterRoleAssignment` | Bind any ClusterRole the placement's clusters have, to any subject you name. |
| `Policy` with a `PlacementBinding` | Ship any manifest in the template, including a `ClusterRoleBinding`. `enforce` applies it. |
| `ManifestWork` | The work agent applies it as a privileged service account. |
| `Placement` | Aims the objects above. It only sees sets bound into its namespace. |
| `ManagedClusterSetBinding` | Projects a set into a namespace. Creating it requires `managedclustersets/bind`. |
| `GitOpsCluster` | Registers those clusters with OpenShift GitOps. The default account is a cluster administrator. |

The OpenShift `admin` role in a namespace can create a `Policy`, a `Placement`, and a `MulticlusterRoleAssignment` there. Give that role only to people who are allowed to grant spoke power. Do not bind a production set into a namespace where developers are namespace admins.

```bash
oc auth can-i create multiclusterroleassignments.rbac.open-cluster-management.io -n site-virt --as=<user> --as-group=<group>
oc auth can-i create policies.policy.open-cluster-management.io -n site-virt --as=<user> --as-group=<group>
oc auth can-i create placements.cluster.open-cluster-management.io -n site-virt --as=<user> --as-group=<group>
oc auth can-i create manifestworks.work.open-cluster-management.io -n <cluster-namespace> --as=<user> --as-group=<group>
oc auth can-i create managedclustersets/bind.cluster.open-cluster-management.io --as=<user> --as-group=<group>
oc auth can-i create gitopsclusters.apps.open-cluster-management.io -n openshift-gitops --as=<user> --as-group=<group>
```

A `yes` on the first four, or on `GitOpsCluster`, in a namespace bound to a cluster set, is spoke power.

## Worked example: Zone A virtual machine admins

The group `zonea-vm-admins` may see Zone A and administer virtual machines there. They are not cluster administrators.

| Step | Where | Object |
| --- | --- | --- |
| 1 | Hub identity | Put the people in `zonea-vm-admins`. Add that provider on the spokes only if they log in there. |
| 2 | Hub | `ClusterRoleBinding` to `open-cluster-management:managedclusterset:view:zone-a`. A platform owner with `bind` creates the `ManagedClusterSetBinding`. |
| 3 | Hub | One `MulticlusterRoleAssignment`: `kubevirt.io:admin` and `acm-vm-extended:admin`, on clusters in the zone that run OpenShift Virtualization. Appendices B and C. |
| 3 | Spoke, written by the controller | The `ClusterRoleBinding` or `RoleBinding`. |
| 4 | Hub | `ClusterRoleBinding` to `acm-vm-fleet:view`. Cross-cluster migration also needs `acm-vm-fleet:admin` on the hub and `acm-vm-cluster-migration:view` on both spokes. |

```bash
oc auth can-i get virtualmachines.kubevirt.io -n team-a --as=<hub-username> --as-group=zonea-vm-admins
```

In the spoke audit log, the click should name the person (`impersonatedUser`). A work-agent change and a GitOps sync should still show `system:serviceaccount:...`.

## Pitfalls

- Hub role, no spoke binding. The tab opens. The call returns `Forbidden`.
- Group strings that differ by one character. The spoke never matches.
- One short name in two directories. Both people get the grant. Qualify the group.
- `pruneObjectBehavior` on the parent `Policy`. It is dropped. Put it on the `ConfigurationPolicy`.
- `inform` on the policy and `enforce` on the template. The parent wins.
- The default GitOps account, `application-manager`. It is a cluster administrator on every registered cluster.
- Argo CD impersonation. It selects a destination service account. It does not record the person who clicked Sync, and the agent does not use it.
- Role aggregation, and the retired `kubevirt.io-acm-*` names. See the virtual machine section.

## Checklist

1. Decide centralized or decentralized for each place. Virtual machines can be centralized while applications on the same clusters stay on the spoke.
2. Keep controller actions on service accounts. A person's click should run as that person.
3. If people log in on the spokes, use one identity provider. If they do not, do not configure a user provider there.
4. Bind each team to `open-cluster-management:managedclusterset:view:<set>`. A platform owner creates the `ManagedClusterSetBinding`.
5. Keep create permission on `MulticlusterRoleAssignment`, `Policy`, `Placement`, `ManifestWork`, and `GitOpsCluster` with the people who may grant spoke power.
6. Enable `fine-grained-rbac` before the virtualization roles. One assignment per group. Leave `targetNamespaces` empty unless the list will stay current.
7. For applications, use a spoke binding, or Appendix D. If Git applies the manifests, replace `application-manager`.
8. Add an admission controller only for a limit a role cannot express. Appendix E is the label case.
9. On a spoke, `oc auth can-i` as the hub user and group. Confirm `impersonatedUser` for a console click.

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

## A. Enable fine-grained RBAC (based on MultiClusterRoleAssignment)

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
