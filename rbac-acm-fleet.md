# Fine-Grained RBAC Across an ACM Fleet: Security Boundaries, Practical Patterns, and Common Pitfalls

Managing access across a fleet of OpenShift clusters is more complex than creating roles and role bindings. With Red Hat Advanced Cluster Management (ACM), authorization can span the management hub, managed-cluster APIs, GitOps controllers, and the services that connect users to workloads.

This article explores practical patterns for designing fine-grained, auditable access control across an ACM-managed fleet, with a focus on OpenShift Virtualization, application workloads, and observability.

The goal is not simply to make access work. It is to make access predictable, appropriately scoped, and secure across the fleet.

> **Scope and version note:** The examples below are based on ACM and OpenShift authorization patterns, including features whose availability depends on product version. Verify API schemas, supported configurations, and preview or general-availability status against the exact releases deployed in your environment before applying these examples in production. Fine-grained RBAC for observability and for logging is work in progress. Do not treat the query and log authorization behavior in this article as a finished, generally available model.

## Table of Contents

- 1\. The Problem: Access Granted, but Still Forbidden
- 2\. Understand the Hub-and-Spoke Authorization Model
- 3\. Choose the Right Delegation Pattern
- 4\. Identity and Group Mapping
- 5\. Cluster Sets and Hub Visibility
- 6\. Fine-Grained RBAC for OpenShift Virtualization
- 7\. Application Workload RBAC
- 8\. OpenShift GitOps: A Separate Authorization Boundary
- 9\. Observability and Query Authorization
- 10\. When RBAC Is Not Enough: Admission Control
- 11\. Hub Permissions That Can Grant Spoke Privileges
- 12\. Worked Example: Virtual Machine Administrators for Zone A
- 13\. Common Pitfalls and Troubleshooting
- 14\. Production Readiness Checklist
- 15\. Conclusion
- Appendix A: Enable Fine-Grained RBAC
- Appendix B: Cluster-Wide MulticlusterRoleAssignment
- Appendix C: Namespace-Scoped MulticlusterRoleAssignment
- Appendix D: Centralized Application RBAC with ACM Policies
- Appendix E: Restrict Namespace Label Changes with Gatekeeper

---

## 1\. The Problem: Access Granted, but Still Forbidden

"We gave the team access, but the console says `Forbidden`."

This is a familiar problem in Kubernetes environments. In a single cluster, troubleshooting often starts with a simple question: which role is bound to this user?

In a managed fleet, that question is only the beginning.

A user might be authorized to see a managed cluster in the ACM console but lack permission to list virtual machines on that cluster. Another user might have the appropriate permissions on the managed cluster but lack the hub-side role needed to access the corresponding console view.

Both cases can produce an authorization failure, but the fixes are different.

The first principle is therefore:

**Hub authorization determines what a user can access through the management layer; managed-cluster authorization determines what that identity can do on the target cluster.**

This distinction becomes especially important when different teams manage applications, virtual machines, and observability across multiple clusters.

### The design goals

A robust fleet-wide authorization model should provide:

- **Least privilege:** Users receive only the permissions required for their responsibilities.
- **Consistent delegation:** Similar teams receive consistent permissions across the clusters they manage.
- **Clear ownership:** Platform teams control fleet boundaries, while application teams can own their project-level permissions where appropriate.
- **Auditable identity:** It is possible to determine whether an action was performed by a human user or a controller.
- **Safe automation:** Policies and GitOps workflows cannot silently become an unrestricted path to cluster administration.
- **Predictable revocation:** Removing a user's access or changing a team's responsibilities should have a clear effect across the fleet.

These goals are related, but they do not necessarily require one universal RBAC strategy.

## 2\. Understand the Hub-and-Spoke Authorization Model

ACM introduces a management hub and a set of managed clusters, often called spokes.

Authorization must be considered at both levels.

| Question | Management hub | Managed cluster |
| --- | --- | --- |
| What is being authorized? | Access to fleet resources and hub-managed capabilities | Access to Kubernetes and OpenShift resources |
| Typical controls | Hub roles, cluster-set roles, policies, placements | Roles, ClusterRoles, RoleBindings, ClusterRoleBindings |
| Human console access | Determines access through the management interface | Determines permissions for the impersonated user |
| Controller access | Authorizes creation or modification of hub objects | Determines what the controller's service account can do |
| Typical failure | Cluster or console view is unavailable | API request returns `Forbidden` |

### 2.1 Human access through the console

A simplified request path looks like this:

```
Human user
    |
    v
ACM console on the hub
    |
    v
Hub-side authorization
    |
    v
cluster-proxy
    |
    | Impersonates the user and groups
    v
Managed-cluster API
    |
    v
Spoke-side RBAC
```

The hub authorizes access to the relevant management resources. When a request is proxied to the managed cluster, the user identity and group memberships are used for authorization on that cluster.

This means the hub and the spoke must agree on the identity being evaluated.

If the hub sees a user as belonging to `zonea-vm-admins`, but the spoke binding references a different group string, the request will not match the intended binding.

A hub role alone does not grant permissions to manage virtual machines, applications, or other spoke resources.

### 2.2 Controller and automation access

A different path applies when a hub-side controller, policy, or GitOps workflow changes a managed cluster.

```
Hub object
    |
    v
ACM controller, work agent, or GitOps
    |
    v
Managed-cluster service account
    |
    v
Managed-cluster API
```

These operations generally use a service-account identity rather than impersonating the human who initiated the workflow.

That distinction has a significant security consequence.

If an automation account has broad privileges, anyone who can cause that account to execute an operation may be able to indirectly exercise those privileges.

The account's effective permissions therefore establish an important security boundary.

**Do not assume that the permissions of the human who initiated a workflow are automatically inherited by the controller that executes it.**

Check the identity recorded in managed-cluster audit logs when validating both console operations and automated changes.

## 3\. Choose the Right Delegation Pattern

Not every workload should use the same authorization model.

For this article, three areas are particularly relevant: applications, virtual machines, and observability.

| Area | Centralized approach | Decentralized approach | Typical consideration |
| --- | --- | --- | --- |
| Applications | ACM policy distributes RBAC resources; GitOps can manage application configuration. With the Argo CD agent and the central UI, AppProject RBAC covers day-to-day management in the Argo CD UI | Teams own RoleBindings on managed clusters | Project names and ownership may differ by cluster. The ACM console is a separate path from the Argo CD UI |
| Virtual machines | ACM `MulticlusterRoleAssignment` distributes role bindings | RBAC bindings are managed on each spoke | Roles and team responsibilities often repeat across a fleet |
| Observability and logging | Hub-side access is scoped through the supported ACM observability authorization model. Perses dashboards placed in a namespace follow OpenShift RBAC for who can open them. Fine-grained query and log RBAC is work in progress | Users query monitoring on individual clusters | Collection identity, query identity, and dashboard visibility are separate. Do not treat the current query or log model as finished |

### Centralized authorization

Centralized authorization is useful when the platform team wants consistent permissions across a known set of clusters.

Advantages include:

- One place to define access.
- Consistent application of roles.
- Easier auditing of the intended configuration.
- Simplified revocation and policy updates.
- Reduced configuration drift.

However, centralization creates a privileged control plane for access management. Anyone who can modify the relevant hub objects may be able to grant permissions across multiple clusters.

### Decentralized authorization

Decentralized authorization is useful when teams own their projects and have different requirements on different clusters.

Advantages include:

- Clear local ownership.
- Fewer fleet-wide privileges in the hub.
- Easier adaptation to cluster-specific namespaces.
- Reduced coupling between application teams and central policy administration.

The trade-off is that local configuration can drift. Platform teams may need additional reporting, compliance checks, or GitOps controls to ensure that intended permissions remain consistent.

### A practical rule

Use centralized authorization where roles and responsibilities are consistent across a fleet. Use decentralized authorization where local ownership and variation are important.

A single environment can use both approaches.

For example, a platform team might centrally manage virtual machine administrators while allowing application teams to manage their own namespace-level bindings.

## 4\. Identity and Group Mapping

RBAC depends on the identity presented to the API server.

For human users, this commonly means a username and a collection of groups. The exact identity strings matter.

Consider the group:

```
zonea-vm-admins
```

A RoleBinding or ClusterRoleBinding that references this group matches only requests whose authenticated identity contains the corresponding group membership.

ACM does not automatically reconcile differences between identity providers or normalize group names across directories.

### 4.1 Shared identity provider

When users log in directly to both the hub and managed clusters, using a consistent identity provider and group mapping simplifies authorization.

The console identity and the identity used by `oc login` should resolve to the expected usernames and groups.

### 4.2 Hub-only user authentication

Some teams want users to access managed clusters only through the ACM console.

In that model, users authenticate to the hub, while the managed-cluster RBAC configuration contains bindings for the identities and groups used by the proxied requests.

The managed clusters do not necessarily need the same interactive user-login configuration.

Maintain a tested break-glass administrative path so that authentication or hub availability problems do not prevent emergency recovery.

### 4.3 Avoid ambiguous identities

Suppose two directories contain a user named `AP001`. If both identities are represented identically to Kubernetes, a binding for that username cannot distinguish the two people.

The same problem can arise with unqualified group names.

Prefer stable, unambiguous identities and group names that reflect the intended security boundary, for example:

```
zonea-vm-admins
zoneb-vm-admins
project-x-developers
project-y-developers
```

The important property is not the naming convention itself. It is that the identity used by the API server uniquely represents the intended principal.

## 5\. Cluster Sets and Hub Visibility

Cluster sets provide a way to group managed clusters and control which users and namespaces can access those groups.

For example, a platform team might define:

```
zone-a
zone-b
production
development
```

A cluster-set role grants hub-side access to the relevant set. It does not, by itself, grant permissions to administer workloads on those clusters.

For a cluster set named `zone-a`, ACM provides roles such as:

| Role | Purpose |
| --- | --- |
| `open-cluster-management:managedclusterset:view:zone-a` | View the cluster set and associated hub resources permitted by that role |
| `open-cluster-management:managedclusterset:admin:zone-a` | Administer the cluster set |
| `open-cluster-management:managedclusterset:bind:zone-a` | View the set and create the corresponding namespace binding, subject to the role's permissions |

The exact generated role names and permissions should be checked against the deployed ACM release.

### 5.1 Bind cluster sets into namespaces

A `Placement` selects clusters from cluster sets that are available in its namespace. A `ManagedClusterSetBinding` makes a cluster set available there.

This is an important isolation boundary.

The platform team should control which cluster sets are bound into namespaces where teams can create policies, placements, or role assignments.

Granting a team permission to view a cluster set is not the same as granting it permission to bind that set into arbitrary namespaces.

### 5.2 Keep global visibility restricted

A broad cluster set such as `global-set` may be appropriate for platform owners, but it should not automatically be available to every development team.

Start with the smallest cluster set required by a team's responsibilities.

Remember that cluster-set visibility does not automatically grant access to every virtual machine, application, log stream, or Argo CD resource.

Those capabilities have their own authorization requirements.

## 6\. Fine-Grained RBAC for OpenShift Virtualization

OpenShift Virtualization is a strong candidate for centralized authorization because the same operational roles often need to be applied consistently across multiple clusters.

Typical personas include:

- Virtual machine viewers.
- Virtual machine administrators.
- Operators responsible for cross-cluster migration.

Without a centralized mechanism, maintaining these permissions across a large fleet can become repetitive and error-prone.

### 6.1 The `MulticlusterRoleAssignment` pattern

Where supported by the deployed ACM release, `MulticlusterRoleAssignment` can distribute selected ClusterRoles to a group across clusters selected by a `Placement`.

The general model is:

```
Hub group
    |
    v
MulticlusterRoleAssignment
    |
    v
Placement
    |
    v
Selected managed clusters
    |
    v
RoleBindings or ClusterRoleBindings
```

This reduces the need to create equivalent bindings manually on every spoke.

A typical design might use:

| Persona | Hub permission | Managed-cluster permission |
| --- | --- | --- |
| VM viewer | Access to the relevant VM console capability | Virtual machine view roles |
| VM administrator | Access to the relevant VM console capability | Virtual machine administration roles |
| Migration operator | Appropriate hub-side migration capability | Required migration roles on source and destination clusters |

The precise role names and permissions depend on the installed OpenShift Virtualization and ACM versions. Inspect the actual ClusterRoles before creating bindings.

### 6.2 Cluster-wide versus namespace-scoped grants

A cluster-wide binding applies the selected ClusterRole across the cluster. A namespace-scoped assignment can instead create RoleBindings in explicitly listed namespaces, where the feature and role support that behavior.

For example, a team might manage virtual machines in:

```
team-a-vms
team-b-vms
```

The namespace-scoped approach avoids granting the role in unrelated namespaces.

However, there are operational trade-offs:

- The namespace list must be maintained.
- Newly created namespaces do not automatically appear in a static list.
- The role must exist on every selected cluster.
- Large assignments can produce large managed resources.
- A namespace-scoped binding cannot grant permissions that require cluster scope.

Do not assume that listing namespaces is automatically safer in every environment. Evaluate the lifecycle of those namespaces and the actual permissions contained in the role.

### 6.3 Enabling the feature

Some ACM releases require the `fine-grained-rbac` component to be enabled before the relevant role-assignment functionality becomes available.

See Appendix A for an example of the component configuration.

Confirm that the component name, API version, and installation procedure match your release before applying the change.

### 6.4 Understand role aggregation

OpenShift and Kubernetes can aggregate permissions from one ClusterRole into another based on labels.

This matters when OpenShift Virtualization permissions interact with broader namespace roles.

A change to role aggregation can alter the effective permissions of existing bindings. A namespace administrator might receive more virtualization access than expected if the relevant role is aggregated into the namespace's `admin` role.

Before changing aggregation behavior:

1. Inspect the installed role definitions and aggregation labels.
2. Determine which existing bindings depend on aggregation.
3. Review the supported configuration for your OpenShift release.
4. Test the change in a non-production cluster.
5. Confirm that the intended users retain the required permissions and do not gain unrelated ones.

Do not remove aggregation labels or adopt preview-only settings without understanding their product-specific implications.

### 6.5 Migration permissions need special attention

Cross-cluster live migration can involve authorization on both the source and destination clusters, as well as the hub-side capabilities that expose the workflow.

A user who can administer virtual machines on one cluster may not have all the permissions required to migrate a VM to another cluster.

Validate the full path:

- The user can access the relevant hub-side interface.
- The user has the required source-cluster permissions.
- The user has the required destination-cluster permissions.
- The required migration-specific roles and resources exist.
- The workflow behaves as expected in audit logs.

Do not assume that a VM administrator role automatically grants every migration permission.

## 7\. Application Workload RBAC

Application teams often have different ownership boundaries from virtualization teams.

One team might own `project-x` on one cluster, while another team owns `project-y` across several clusters. In some environments, project names are consistent; in others, they vary.

For that reason, decentralized RBAC is often a reasonable starting point for applications.

### 7.1 Spoke-managed bindings

A team can receive namespace-scoped access through a RoleBinding on the managed cluster.

For example:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: project-x-developers
  namespace: project-x
subjects:
  - kind: Group
    apiGroup: rbac.authorization.k8s.io
    name: project-x-developers
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: view
```

This example grants the group the permissions defined by the `view` ClusterRole within `project-x`.

An administrator could create a similar binding for an application administrator group using the `admin` role.

The group names must match the identities supplied to the managed-cluster API server.

### 7.2 Centralized application RBAC with ACM policies

If the organization wants the hub to manage namespace bindings centrally, ACM policies can distribute the required resources to selected managed clusters.

A policy can create RoleBindings for application teams and ClusterRoleBindings for platform-level administrators.

This is powerful, but it must be treated as a privileged operation.

A person who can modify an enforced policy may be able to distribute arbitrary RBAC resources to the clusters selected by that policy's placement.

Keep policy ownership, placement scope, and the namespaces containing these objects under platform-team control.

See Appendix D for a representative example.

### 7.3 Understand policy remediation and cleanup

ACM policy behavior depends on both the parent `Policy` and its embedded `ConfigurationPolicy`.

Pay particular attention to:

- `remediationAction`, which controls whether the policy reports drift or attempts remediation.
- `pruneObjectBehavior`, which controls cleanup of objects created by the policy when they are removed from its templates.
- The `Placement` and `PlacementBinding`, which determine which clusters receive the policy.

Test policy creation, drift correction, and cleanup before applying an authorization policy to production clusters.

Do not assume that removing a template automatically deletes every previously created object in every policy configuration.

## 8\. OpenShift GitOps: A Separate Authorization Boundary

GitOps introduces another authorization system.

OpenShift RBAC controls access to Kubernetes resources and parts of the platform. Argo CD has its own authorization model for applications, projects, repositories, destinations, and synchronization operations.

These systems interact, but they are not interchangeable.

**A hub RoleBinding does not automatically grant access to the Argo CD UI, and an Argo CD role does not automatically create the necessary spoke-side RBAC.**

### 8.1 The default service-account risk

In a push-based configuration, a hub-side Argo CD instance can apply resources to managed clusters through credentials associated with those clusters.

The default service account used by some ACM GitOps configurations can have cluster-administrator privileges on the managed cluster.

If that is the case in your installation, every application using those credentials can potentially exercise the privileges granted to that account, subject to the controls enforced earlier in the workflow.

This is a significant security boundary.

Do not assume that restricting a user in the Argo CD UI also reduces the permissions of the service account used to apply manifests.

### 8.2 Reduce the privileges used for deployment

Where supported, consider using a dedicated managed service account with explicitly scoped permissions instead of a broadly privileged default account.

The design should address several layers:

1. **Cluster selection:** Restrict which managed clusters are registered for deployment.
2. **Destination scope:** Limit which namespaces an application can target.
3. **Repository scope:** Restrict trusted Git repositories through Argo CD project configuration.
4. **Resource scope:** Limit which resource kinds applications can manage where supported.
5. **Deployment identity:** Use a service account with only the required permissions.
6. **Application authorization:** Control who can create, view, modify, or synchronize applications.

An Argo CD `AppProject` can constrain source repositories, destination clusters and namespaces, and resource kinds. These restrictions should complement least-privilege permissions on the destination cluster.

### 8.3 ApplicationSets in many hub namespaces

Some customers do not want every team to share the Argo CD namespace. They want each team, application, or site to own its own `ApplicationSet` on the hub, in its own namespace. In a large fleet that can mean ApplicationSets in hundreds of hub namespaces.

That pattern uses ordinary OpenShift RBAC as the ownership boundary. A team that can create objects in its namespace can manage the ApplicationSets that live there. A team that cannot is kept out of that namespace. It also multiplies the GitOps control points the platform team has to account for.

Where the installed OpenShift GitOps release supports ApplicationSets outside the Argo CD namespace, the instance has to be told which namespaces it may watch. Review:

- `spec.sourceNamespaces` for `Application` resources
- `spec.applicationSet.sourceNamespaces` for `ApplicationSet` resources

An Application generated by an ApplicationSet may land in a different namespace from the ApplicationSet itself. That namespace also has to be one the Argo CD instance is allowed to monitor.

At the scale of hundreds of namespaces, how that allowlist is maintained becomes part of the authorization model:

- An explicit list is precise, and it goes stale as teams and namespaces are added or removed. Adding a namespace to the list is a privileged change. It lets ApplicationSets in that namespace be reconciled.
- A wildcard or all-namespaces setting, where the release supports it, avoids maintaining the list and widens the set of namespaces the controller will act on. Treat that as a conscious expansion of the trust boundary.
- Namespace admin in any watched namespace can create an Application or ApplicationSet that triggers deployment, within the limits of the Argo CD project configuration and the destination credentials.

Confirm the exact fields, and whether a wildcard is supported, against the installed OpenShift GitOps release before choosing a pattern.

### 8.4 Argo CD agent, the central UI, and AppProject RBAC

Some customers integrate the Argo CD agent with ACM and use the central Argo CD UI. Teams manage applications from one Argo CD interface on the hub. An agent on each managed cluster carries that work to the cluster. Day-to-day application management does not have to go through the ACM console.

Authorization for that UI is Argo CD's own model. An `AppProject` defines which Git repositories, destination clusters, namespaces, and resource kinds a group of applications may use. Argo CD roles then decide which groups can view, create, update, or synchronize the applications in that project.

If the customer is comfortable directing teams to the Argo CD UI, and not the ACM console, for day-to-day application management, the AppProject-based RBAC approach fully addresses that need. Those teams do not also need a parallel set of ACM console permissions for the same application operations.

That conclusion is about the management surface. It does not change the deployment-identity checks in sections 8.1 and 8.2. An AppProject restricts what the project is allowed to target. It does not, by itself, prove that the identity which applies the manifests on the managed cluster is least privilege.

Agent-based sync and impersonation can also change which identity is recorded on the spoke. Those capabilities are version-sensitive. Verify whether the integration is supported, generally available, or still in preview in the installed ACM and OpenShift GitOps releases.

Do not assume that a destination service account represents the human who clicked Sync. The actual identity depends on the configured execution path. Test the relevant audit events and authorization checks rather than inferring identity from the user interface.

If the same teams are later asked to manage those applications in the ACM console, AppProject RBAC does not grant that console view. That path has to be designed separately.

## 9\. Observability and Query Authorization

> **Work in progress:** RBAC for ACM observability and for logging is currently work in progress. Namespace-scoped Perses dashboards, described below, are a partial control that exists today. They are not a finished model for who can query metrics or logs. Re-check the installed ACM release before relying on query isolation or log isolation in production.

Observability requires separating two different activities:

1. Collecting metrics and logs from a managed cluster.
2. Allowing a human user to query that data.

The collector usually runs with a service-account identity. The person querying the data should be authorized independently.

A collector's permissions should not become a general-purpose authorization mechanism for human users.

### 9.1 Centralized queries

In centralized ACM observability configurations, query access can depend on the user's permissions to view the relevant managed clusters.

The precise scope of access to metrics and logs depends on the observability architecture and the features supported by the deployed version.

Do not assume that a user who can view a cluster has unrestricted access to every observability data source, or that cluster-level authorization automatically provides namespace-level filtering.

Verify the effective behavior for the actual metrics and logging components.

### 9.2 Logs deserve particular scrutiny

Logging RBAC is part of the same work in progress. There is not yet a finished, generally available model for who can query which logs across the fleet.

Logs can contain more sensitive information than aggregate metrics.

Depending on the workload and logging configuration, they may include:

- Application identifiers and customer data.
- Authentication or authorization errors.
- Tokens accidentally written by applications.
- Audit events.
- Virtual machine console output.

A broad query permission can therefore expose sensitive information even when the user cannot modify workloads.

Review query scope, retention, access logging, and the sensitivity of the data collected.

### 9.3 Local observability

A user who logs in directly to a managed cluster and queries its own monitoring stack follows a different authorization path from a user querying centrally through ACM.

Document both models if your organization supports them.

Do not assume that centralized observability permissions apply to direct access to a managed cluster's monitoring interface.

### 9.4 Perses dashboards follow namespace RBAC

ACM observability uses Perses for dashboards. A Perses dashboard is a resource you can place in a namespace, and access to that resource follows ordinary OpenShift RBAC.

That helps, to some extent. Put a team's dashboards in a namespace that team can view, and people without permission to get or list those dashboard resources will not see them in the console. You do not need a separate dashboard access-control list for that boundary. Users who can create or update the dashboard resource can edit it. Users who can only read it can open it.

The limit is that this authorizes the dashboard object, not the data behind it. Opening a dashboard is not the same as being restricted to the series that dashboard queries. A user who can view the dashboard may still receive whatever metrics or logs the query path allows. A user who cannot see the dashboard may still reach the same data through another query interface, if that interface authorizes them.

Use namespace placement to separate who can see and edit which dashboards. Keep testing the query authorization model above for who can read the underlying data. Confirm the dashboard API, and which namespaces the installed ACM and OpenShift releases expose in Observe, before relying on this split.

## 10\. When RBAC Is Not Enough: Admission Control

Kubernetes RBAC answers questions such as:

> May this user update this object?

It does not generally answer every question about which individual fields or changes that user may make.

For example, a namespace administrator might be allowed to update a Namespace object but should only be permitted to add one specific label:

```
argocd.argoproj.io/managed-by
```

A standard RoleBinding cannot easily express the rule that one new label is permitted while every other new label is rejected.

This is where admission control can help.

### 10.1 Use admission control for change-specific restrictions

A validating admission controller can inspect an update and reject changes that violate a policy.

For a label-change rule, the controller can compare the previous object with the proposed object and determine which label keys have been added.

The policy might allow the approved key while rejecting other newly added keys.

However, the exact semantics must be explicit:

- Are only new keys restricted?
- Can existing label values change?
- Can labels be removed?
- Are system namespaces excluded?
- Are controller identities exempt?
- What happens when the old object is unavailable?

These decisions affect the security properties of the rule.

### 10.2 Validate the rule before enforcing it

Admission policies can block legitimate platform operations if they are too broad.

A safe rollout should include:

1. Deploying the constraint template.
2. Testing it with representative namespace updates.
3. Confirming that allowed changes succeed.
4. Confirming that prohibited changes fail.
5. Testing controller operations and exception cases.
6. Starting in a non-blocking mode where appropriate.
7. Enabling enforcement only after reviewing the results.

See Appendix E for a starting example. Its policy logic must be tested against the cases above before production use.

### 10.3 Delete protection

RBAC can grant or deny the `delete` verb. It cannot easily say that a namespace administrator may delete ordinary workload objects but must not delete the namespace, a virtual machine, an ApplicationSet, or a GitOps credential.

Some customers close that gap with an admission controller. Gatekeeper is a common choice. Kyverno and a Kubernetes `ValidatingAdmissionPolicy` can express the same kind of rule. The controller sees the `DELETE` and rejects it even when RBAC would have allowed the call.

Decide the rule explicitly:

- Which kinds and namespaces are protected.
- Which identities may still delete them, including a tested break-glass user.
- Whether controllers are exempt. GitOps prune, ACM policy cleanup (`pruneObjectBehavior`), garbage collection, and operators all delete objects. An exemption that covers every `system:` account will not stop the automation path that matters. An exemption that covers none of them will block legitimate reconciliation.
- What happens to related objects, including finalizers, cascading delete, and scale-to-zero as distinct from delete.

Roll a delete rule out the same way as any other admission policy. Run positive and negative tests, start in a non-blocking mode where the product supports it, and enforce only after reviewing the results. Appendix E shows the shape of a Gatekeeper constraint for a different rule. A delete rule needs its own tests. In particular, confirm that a human delete is rejected and that the controllers which must delete still can.

## 11\. Hub Permissions That Can Grant Spoke Privileges

One of the most important security considerations in an ACM-managed fleet is that a hub-side object can indirectly grant substantial permissions on a managed cluster.

Consider the following resources:

| Hub resource | Potential security impact |
| --- | --- |
| `MulticlusterRoleAssignment` | Can distribute selected ClusterRoles to a subject on clusters selected by its placement |
| `Policy` and `PlacementBinding` | Can distribute resources, potentially including privileged RBAC objects, to selected clusters |
| `ManifestWork` | Can deliver resources to a managed cluster through the work mechanism |
| `Placement` | Determines which clusters receive associated work or policy |
| `ManagedClusterSetBinding` | Makes a cluster set available to resources in a namespace |
| `GitOpsCluster` | Can register clusters for GitOps management using the configured deployment identity |

The effective impact depends on the permissions of the user, the resource configuration, the controllers involved, and the scope of the selected clusters.

The general lesson is that the ability to create or modify these objects can be equivalent to the ability to grant spoke privileges.

### 11.1 Namespace administrators may need more power than expected

A common mistake is to grant namespace-level `admin` permissions in a hub namespace without reviewing which ACM resources can be created there.

If that namespace has access to a production cluster set, and users can create policies or role assignments that target those clusters, the namespace boundary may not provide the isolation that the platform team intended.

The important question is not merely:

> Can this user administer the namespace?

It is also:

> What can this user cause the controllers to do on the managed clusters?

The same question applies on the hub when ApplicationSets are spread across many namespaces. Admin in one of those namespaces can create an ApplicationSet that the GitOps controller will reconcile.

### 11.2 Audit the ability to create privileged objects

Use impersonation to test whether a user can create the relevant resource types.

Run these commands with an appropriately privileged account that is allowed to impersonate the test identity:

```
oc auth can-i create \
  multiclusterroleassignments.rbac.open-cluster-management.io \
  -n site-virt \
  --as=<user> \
  --as-group=<group>

oc auth can-i create \
  policies.policy.open-cluster-management.io \
  -n site-virt \
  --as=<user> \
  --as-group=<group>

oc auth can-i create \
  placements.cluster.open-cluster-management.io \
  -n site-virt \
  --as=<user> \
  --as-group=<group>

oc auth can-i create \
  manifestworks.work.open-cluster-management.io \
  -n <cluster-namespace> \
  --as=<user> \
  --as-group=<group>

oc auth can-i create \
  managedclustersets/bind.cluster.open-cluster-management.io \
  --as=<user> \
  --as-group=<group>

oc auth can-i create \
  gitopsclusters.apps.open-cluster-management.io \
  -n openshift-gitops \
  --as=<user> \
  --as-group=<group>
```

Check the exact resource names and API groups exposed by your ACM installation before using these commands in automation.

A `yes` response does not prove that every possible escalation path is exploitable. It identifies a permission that deserves closer review in the context of the resources and cluster sets available to that identity.

### 11.3 Treat authorization configuration as privileged infrastructure

The people who can grant permissions across a fleet should be a deliberately small and auditable group.

Protect:

- Policy definitions and their placement bindings.
- Role assignments and their subjects.
- Placement definitions.
- Cluster-set bindings.
- ManifestWork creation.
- GitOps cluster registration and destination credentials.

Review these permissions whenever teams, cluster sets, or automation workflows change.

## 12\. Worked Example: Virtual Machine Administrators for Zone A

Consider an organization with multiple managed clusters. The platform team wants a group called `zonea-vm-admins` to administer virtual machines in Zone A without receiving general OpenShift cluster-administrator privileges.

The intended model is:

- The group can see the clusters in `zone-a`.
- The group can access the required VM console functionality.
- The group receives the necessary OpenShift Virtualization roles on eligible managed clusters.
- The group does not receive unrelated cluster-wide administrative privileges.
- Only authorized platform administrators can modify the hub resources that grant these permissions.

### Step 1: Define the identity

Create or configure the group in the identity provider:

```
zonea-vm-admins
```

Verify that the hub authentication path supplies the expected group membership.

### Step 2: Scope hub visibility

Bind the group to the appropriate cluster-set view role for `zone-a`.

Ensure that the platform team controls the `ManagedClusterSetBinding` that exposes the cluster set to the relevant namespace.

### Step 3: Select eligible clusters

Create a `Placement` in a controlled namespace that selects only the intended managed clusters.

Where appropriate, use cluster labels to distinguish clusters running OpenShift Virtualization from those that do not.

For example, a platform-managed label might be:

```
virtualization-enabled=true
```

The label is only a selection mechanism; the platform team must control who can set or modify it.

### Step 4: Distribute the required roles

Where supported by the deployed ACM release, use a `MulticlusterRoleAssignment` to distribute the required ClusterRoles to the group.

A cluster-wide example is provided in Appendix B. A namespace-scoped example is provided in Appendix C.

Inspect the actual role definitions before choosing them. Confirm that they grant the required virtualization operations without introducing unintended access.

### Step 5: Grant hub-side console access

The managed-cluster bindings and the hub console permissions solve different problems.

Configure the required hub-side role separately. If the hub role is missing, the console view may not open even when the spoke permissions are correct.

Conversely, if the hub role exists but the managed-cluster bindings are missing, the console request may reach the spoke and fail with `Forbidden`.

### Step 6: Validate authorization

Test a representative API request:

```
oc auth can-i get virtualmachines.kubevirt.io \
  -n team-a \
  --as=<hub-username> \
  --as-group=zonea-vm-admins
```

Run the check against the appropriate managed cluster and use the exact username and groups present in the authenticated request.

Then test the actual console workflow.

Finally, inspect the managed-cluster audit log. A proxied human action should reflect the impersonated identity where the request path uses impersonation. A controller or GitOps operation should instead show the relevant service-account identity.

This confirms that the expected identity is being evaluated at the correct authorization boundary.

## 13\. Common Pitfalls and Troubleshooting

### The hub role exists, but the console returns `Forbidden`

Check the managed-cluster binding and the identity presented to the API server.

```
oc auth can-i get virtualmachines.kubevirt.io \
  -n team-a \
  --as=<user> \
  --as-group=<group>
```

### The group appears correct, but authorization fails

Compare the group strings exactly. Check capitalization, prefixes, directory mappings, and whether the request actually contains the expected group.

### Two users unexpectedly receive the same permissions

Check whether their usernames or group names collide across identity providers. Use identities that distinguish the intended principals.

### A policy does not remove an object after a template change

Review `pruneObjectBehavior`, its placement on the `ConfigurationPolicy`, and the parent policy's remediation configuration. Test the lifecycle behavior in a non-production environment.

### GitOps users have less access in the UI than expected

Review Argo CD RBAC, group-scope configuration, application ownership, project permissions, and the relevant OpenShift GitOps settings. Hub-side RBAC is not a substitute for Argo CD authorization.

### Application access was designed for the Argo CD UI, but teams are in the ACM console

AppProject RBAC applies to the central Argo CD UI. It does not grant the same application management in the ACM console. If the operating model is the Argo CD UI, direct teams there. If they must use the ACM console, design that path separately.

### GitOps can change more than intended

Inspect the destination credentials and the permissions of the service account used to apply resources. Check the AppProject's repositories, destinations, and resource restrictions as well.

### ApplicationSets exist in many hub namespaces, and a team can deploy more than intended

Confirm that each namespace is present in the Argo CD source-namespace configuration only on purpose. Then review who can create `Application` and `ApplicationSet` objects there, and what the destination service account can do once a sync runs.

### Delete protection blocks a workflow that should still succeed

Check whether the admission rule matches the GitOps controller, the policy controller, or another service account. Compare the username in the rejection with the exemption list. Test prune and cleanup, not only a manual delete.

### Virtual machine permissions appear broader than expected

Inspect ClusterRole definitions and aggregation labels. Determine whether virtualization permissions are aggregated into namespace-level roles and verify the supported configuration for your OpenShift version.

### Migration fails even though VM administration works

Validate the required permissions on both the source and destination clusters, along with the hub-side access required for the workflow.

### Observability or log access is broader than expected

Fine-grained RBAC for observability and logging is still work in progress. Review whatever query behavior the installed ACM release actually enforces. Do not assume that a cluster-set role provides namespace-level or workload-level data isolation, for metrics or for logs.

### A Perses dashboard is hidden, but the same data is still visible

Dashboard namespace RBAC controls who can open that dashboard resource. Query authorization controls who can read the metrics and logs. Test both. Hiding a dashboard does not hide the series it queries.

## 14\. Production Readiness Checklist

Before deploying an ACM fleet-wide RBAC design, verify the following.

### Identity and visibility

- [ ] Usernames and group names are consistent across the relevant authentication paths.
- [ ] Ambiguous identities across directories are avoided.
- [ ] Cluster-set visibility is scoped to the appropriate teams.
- [ ] Only platform administrators can bind sensitive cluster sets into privileged namespaces.

### Managed-cluster permissions

- [ ] Each role has been reviewed for the resources and verbs it grants.
- [ ] Namespace-scoped and cluster-scoped permissions are deliberately distinguished.
- [ ] Cross-cluster workflows have been tested on all participating clusters.
- [ ] Virtualization role aggregation has been reviewed.
- [ ] Newly created clusters receive the intended permissions without receiving unrelated access.

### Policies and automation

- [ ] Only authorized users can create or modify privileged policies, placements, role assignments, and ManifestWorks.
- [ ] Placement selectors cannot unintentionally include production clusters.
- [ ] Policy enforcement and cleanup behavior have been tested.
- [ ] GitOps destination credentials use the least privilege practical for the deployment.
- [ ] Argo CD UI authorization and destination-cluster authorization are both configured.
- [ ] Teams that manage applications in the central Argo CD UI have AppProject and Argo CD role assignments for that work, and are not also expected to use the ACM console for the same operations.
- [ ] Every hub namespace that may contain an ApplicationSet is intentional, and the Argo CD source-namespace configuration matches that set.
- [ ] Delete-protection rules have been tested against human users, GitOps prune, and policy cleanup, with an explicit break-glass identity.
- [ ] Human actions and controller actions can be distinguished in audit logs.

### Observability and admission control

- [ ] Metrics and log access are reviewed separately where their sensitivity differs.
- [ ] The observability and logging RBAC design is treated as work in progress and re-checked against the installed ACM release before production use.
- [ ] The actual query authorization model has been tested.
- [ ] Perses dashboards that should be team-scoped live in namespaces whose OpenShift RBAC matches that audience.
- [ ] Dashboard visibility has been tested separately from query access to the underlying metrics and logs.
- [ ] Admission policies have positive and negative test cases.
- [ ] Exceptions for platform controllers and system namespaces are explicit and justified.

### Operations

- [ ] The exact product versions and API schemas are documented.
- [ ] Preview features are clearly identified and approved for the intended use.
- [ ] A break-glass administrative path is tested.
- [ ] Revocation behavior has been verified.
- [ ] Changes are reviewed, auditable, and recoverable.

## 15\. Conclusion

Fine-grained RBAC across an ACM-managed OpenShift fleet is not simply a matter of creating the correct RoleBinding.

It requires an understanding of the complete authorization path: the identity presented by the user, the hub-side permissions that expose a capability, the managed-cluster RBAC that ultimately authorizes the request, and the service accounts used by controllers and automation.

Different workloads benefit from different approaches. Virtual machine permissions can often be managed centrally when roles and responsibilities repeat across a fleet. Application RBAC may be better owned by individual teams, with centralized policy distribution as an option. Observability needs a separate review of collection and query authorization. Fine-grained RBAC for observability and for logging is work in progress, so the current query and log behavior must be verified on the installed release rather than assumed. Namespace-scoped Perses dashboards add an OpenShift RBAC boundary for who can open a dashboard, and that boundary does not replace query authorization. Admission control can enforce restrictions that ordinary RBAC cannot express, including which objects may be deleted.

The most important security lesson is that **permissions to modify fleet-management resources can become permissions to grant access on managed clusters**.

Protect those control points as carefully as the spoke resources themselves.

A successful design is not merely one in which the intended users can perform their tasks. It is one in which unintended users and automation paths cannot obtain broader privileges than the platform team intended.

---

# Appendix A: Enable Fine-Grained RBAC

Some ACM releases require the `fine-grained-rbac` component to be enabled before the relevant virtualization role-assignment functionality is available.

The following illustrates the component configuration pattern. Verify the supported component configuration and API behavior for your installed release before applying it.

```
oc get multiclusterhub multiclusterhub \
  -n open-cluster-management -o yaml
```

If the component is not already present in `spec.overrides.components`, the following patch illustrates the append operation:

```
oc patch multiclusterhub multiclusterhub \
  -n open-cluster-management \
  --type=json \
  -p='[
    {
      "op": "add",
      "path": "/spec/overrides/components/-",
      "value": {
        "name": "fine-grained-rbac",
        "enabled": true
      }
    }
  ]'
```

**Important:** Do not append a duplicate component entry if `fine-grained-rbac` is already present. Update the existing entry instead.

After changing the configuration, confirm that the component becomes available and that the required API resources and ClusterRoles exist.

# Appendix B: Cluster-Wide MulticlusterRoleAssignment

This example illustrates a cluster-wide assignment for a group that administers virtual machines on clusters selected by a placement.

The API version and role names must match the installed ACM and OpenShift Virtualization versions.

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

With an empty or omitted `targetNamespaces` field, the controller's behavior is intended to provide cluster-wide access through the corresponding binding, subject to the API's supported semantics.

Before applying this example:

1. Confirm that the API resource exists.
2. Confirm that both ClusterRoles exist on every selected cluster.
3. Review the permissions in both roles.
4. Verify that the placement selects only intended clusters.
5. Confirm the resulting bindings on the managed clusters.

# Appendix C: Namespace-Scoped MulticlusterRoleAssignment

When the feature and role definitions support namespace-scoped assignments, a namespace list can restrict where the bindings are created.

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

This pattern should be used only after verifying the supported API schema and the scope of each role.

A static namespace list does not automatically expand when a new project is created. Define an ownership and update process so that the assignment does not become stale.

# Appendix D: Centralized Application RBAC with ACM Policies

This example illustrates the structure of an ACM policy that distributes application RBAC to selected managed clusters.

It defines the following intended access:

| Group | Intended access |
| --- | --- |
| `SreAdminGrp` | Cluster administrator |
| `AppX-AdminGrp` | Namespace administrator in `project-x` |
| `AppX-ViewGrp` | View access in `project-x` |
| `AppY-AdminGrp` | Namespace administrator in `project-y` |
| `AppY-ViewGrp` | View access in `project-y` |

**Security warning:** The `SreAdminGrp` ClusterRoleBinding grants `cluster-admin` on every selected cluster. Treat this as a high-privilege example, restrict the group and placement carefully, and replace it with narrower permissions if full cluster administration is unnecessary.

The policy uses `inform` as its initial remediation mode. After validating the rendered objects and the placement, an administrator can deliberately move to enforcement if appropriate.

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: Policy
metadata:
  name: policy-configure-appworkloads-rbac
  namespace: app-workloads
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
                apiVersion: user.openshift.io/v1
                kind: Group
                metadata:
                  name: SreAdminGrp
                users: []
            - complianceType: musthave
              objectDefinition:
                apiVersion: user.openshift.io/v1
                kind: Group
                metadata:
                  name: AppX-AdminGrp
                users: []
            - complianceType: musthave
              objectDefinition:
                apiVersion: user.openshift.io/v1
                kind: Group
                metadata:
                  name: AppX-ViewGrp
                users: []
            - complianceType: musthave
              objectDefinition:
                apiVersion: user.openshift.io/v1
                kind: Group
                metadata:
                  name: AppY-AdminGrp
                users: []
            - complianceType: musthave
              objectDefinition:
                apiVersion: user.openshift.io/v1
                kind: Group
                metadata:
                  name: AppY-ViewGrp
                users: []
            - complianceType: musthave
              objectDefinition:
                apiVersion: v1
                kind: Namespace
                metadata:
                  name: project-x
                  labels:
                    purpose: namespace-for-sample-app-x
            - complianceType: musthave
              objectDefinition:
                apiVersion: v1
                kind: Namespace
                metadata:
                  name: project-y
                  labels:
                    purpose: namespace-for-sample-app-y
            - complianceType: musthave
              objectDefinition:
                apiVersion: rbac.authorization.k8s.io/v1
                kind: ClusterRoleBinding
                metadata:
                  name: sre-admin-binding
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
                apiVersion: rbac.authorization.k8s.io/v1
                kind: RoleBinding
                metadata:
                  name: app-x-admin-binding
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
                apiVersion: rbac.authorization.k8s.io/v1
                kind: RoleBinding
                metadata:
                  name: app-x-view-binding
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
                apiVersion: rbac.authorization.k8s.io/v1
                kind: RoleBinding
                metadata:
                  name: app-y-admin-binding
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
                apiVersion: rbac.authorization.k8s.io/v1
                kind: RoleBinding
                metadata:
                  name: app-y-view-binding
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

### Before using this policy

- Create the `app-workloads` namespace on the hub.
- Confirm that the placement selects only the intended managed clusters.
- Ensure the relevant groups are managed through the intended identity provider.
- Review the policy's behavior for pre-existing namespaces and bindings.
- Test remediation and cleanup in a non-production environment.
- Confirm the exact `ConfigurationPolicy` and policy schema for your ACM release.

Do not assume that an empty group definition replaces an existing directory-managed group. Verify the effect on your identity configuration before enforcing the policy.

# Appendix E: Restrict Namespace Label Changes with Gatekeeper

The following example illustrates a Gatekeeper constraint that permits a non-system user to add the `argocd.argoproj.io/managed-by` label to a Namespace while rejecting other newly added label keys.

It is a starting point for testing, not a complete production policy.

The example deliberately focuses on newly added keys. It does not, by itself, prevent every possible change to existing labels or the removal of labels.

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8snamespacelabelchange
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

          not contains(
            lower(input.review.object.metadata.name),
            "openshift"
          )

          not startswith(
            input.review.userInfo.username,
            "system:"
          )

          new_labels := object.get(
            input.review.object.metadata,
            "labels",
            {}
          )

          old_meta := object.get(
            object.get(input.review, "oldObject", {}),
            "metadata",
            {}
          )

          old_labels := object.get(
            old_meta,
            "labels",
            {}
          )

          added := {
            key |
            key := object.keys(new_labels)[_]
            not key in object.keys(old_labels)
          }

          count(added) > 0

          added_label := added[_]

          added_label != "argocd.argoproj.io/managed-by"

          msg := sprintf(
            "Adding label key '%v' is not allowed on namespace '%v'. Only 'argocd.argoproj.io/managed-by' is permitted.",
            [
              added_label,
              input.review.object.metadata.name
            ]
          )
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

### Important validation requirements

Before applying this example:

1. Verify that the Gatekeeper and ConstraintTemplate API versions are supported by your installation.
2. Validate the Rego syntax against the Rego version used by your Gatekeeper release.
3. Test updates where an allowed label is added.
4. Test updates where a disallowed label is added.
5. Test updates where an existing label's value changes.
6. Test updates where an existing label is removed.
7. Test objects with no labels and objects with empty label values.
8. Confirm the behavior for system namespaces and controller identities.
9. Test the policy in audit or warning mode before enforcing rejection.

In particular, ensure the implementation checks key membership explicitly rather than relying on the truthiness of an existing label value. An existing label with an empty value must not be mistaken for a newly added key.

The exemption for namespaces whose names contain `openshift` is a broad exception. Review whether it is necessary and whether a more precise namespace allowlist is appropriate.

Similarly, exempting every username beginning with `system:` should not be treated as a substitute for reviewing controller permissions.

---

## References and Further Reading

Use the documentation corresponding to the exact product versions deployed in your environment.

- Red Hat Advanced Cluster Management documentation
- OpenShift Container Platform documentation
- Open Cluster Management documentation
- Open Policy Agent and Gatekeeper
- Argo CD documentation
- OpenShift GitOps documentation

For reproducibility, document the exact ACM, OpenShift, OpenShift Virtualization, OpenShift GitOps, and Gatekeeper versions used to test the examples.

The most useful contribution this article can make is to give platform engineers a repeatable way to reason about authorization across the entire fleet—not just whether an individual RoleBinding looks correct.
