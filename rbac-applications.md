# Application RBAC

Most application teams should receive a RoleBinding on the spoke and work there. Centralized distribution is for the platform team that wants one source of those bindings. This page is the short form. The reference is [Fine-Grained RBAC Across an ACM Fleet](rbac-acm-fleet.md), section 7 and appendix D.

## Recommended

Bind the team to `view` or `admin` in their project on the managed cluster. The group string must match the identity the spoke API evaluates. If those people log in on the spoke, use the same identity provider as the hub. If they only use the console, the hub token's groups are what the spoke binding must spell.

A developer who only works on the spoke does not need a cluster-set role and does not need a hub login. ACM can still monitor the cluster.

## When the hub should own the binding

An ACM `Policy` with a `ConfigurationPolicy` can create the same RoleBinding on selected clusters. Put `pruneObjectBehavior` on the `ConfigurationPolicy`. The parent `Policy` does not have that field.

Start with `remediationAction: inform`. Move to `enforce` after the rendered objects match what you intend.

Appendix D of the reference is a full example, including a `cluster-admin` binding for an SRE group. That binding is spoke cluster-admin on every selected cluster. Narrow it if the team does not need it.

Whoever can edit that policy can grant spoke permissions. Section 11 of the reference is the list of hub objects with that effect.

## What this does not cover

Opening Argo CD, or letting a team commit an ApplicationSet on the hub, is a different authorization system. That is [GitOps integration](rbac-gitops.md).

A namespace `admin` binding does not scope metrics queries. Section 9 of the reference separates console access, metric queries, and logs.
