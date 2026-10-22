# GitOps integration

OpenShift RBAC and Argo CD RBAC are separate. A cluster-set role does not open the Argo CD UI. An Argo CD role does not create the spoke binding for the developer. This page is the short form. The reference is [Fine-Grained RBAC Across an ACM Fleet](rbac-acm-fleet.md), section 8.

## Recommended

If developers work on their own clusters, give them no hub login and no Argo CD role. ACM monitors and, if you choose, delivers RoleBindings with a policy. See [Application RBAC](rbac-applications.md).

Open the hub and Argo CD only when the customer allows centralized application management.

## If the team uses Argo CD on the hub

Leave `policy.default` empty. Map groups to roles explicitly. `policy.default: role:readonly` gives every authenticated user read access to every project.

Keep the control-plane namespace out of a tenant `AppProject` `sourceNamespaces`.

The spoke still sees a service account. An AppProject limits repositories, destinations, and resource kinds. It does not make the developer that service account. Test the audit identity for a sync before you describe it as the human who clicked.

Where the installed OpenShift GitOps release supports ApplicationSets outside the control-plane namespace, set both `spec.sourceNamespaces` and `spec.applicationSet.sourceNamespaces`. Confirm whether wildcards are accepted on that version before you depend on one. Adding a namespace to the list lets ApplicationSets there be reconciled. Treat that as a privileged change.

## Declarative RBAC

Git can hold the `MulticlusterRoleAssignment`, the `Placement`, and the ACM `Policy` that distributes spoke RoleBindings. Applying those objects is the same privilege as creating them on the hub. Review who can sync the namespace that contains them. Section 11 of the reference lists the objects.

Agent-based sync and impersonation of a destination service account are version-sensitive. Read the OpenShift GitOps and Argo CD notes for the release you run, and check the spoke audit log, before you document which identity a sync uses.
