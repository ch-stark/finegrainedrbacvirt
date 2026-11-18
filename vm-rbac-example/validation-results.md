# ACM 5.0 validation record

## Status

**Full ACM 5.0 multi-cluster deployment status: Not run.** A separate [hub-only test on ACM build 5.1.0-184](../validation/hub-only/results.md) has recorded results. The template below remains for the original topology and target version; its pending cells must not be populated from the narrower run. Complete it for a specific source commit and environment before calling that deployment validated.

## Local checks

The accompanying source has been checked locally for policy generation, MRA schema validity, explicit workload namespaces, role consistency, policy routing, controller-permission scope, direct-patch/setup-policy equivalence, and Markdown link integrity. The authorization script has passed syntax validation. Local rendering used Kustomize v5.8.1 and upstream PolicyGenerator v1.19.0; it does not test the ACM image inside Argo CD.

## Environment

| Field | Recorded value |
| --- | --- |
| Test date and operator | Not recorded |
| Source commit SHA | Not recorded |
| ACM version and image digest | Not recorded |
| OpenShift hub and managed-cluster versions | Not recorded |
| OpenShift Virtualization versions | Not recorded |
| OpenShift GitOps and Argo CD versions | Not recorded |
| Repository-server PolicyGenerator image digest | Not recorded |
| Hub ManagedCluster name | Expected `local-cluster`; not observed |
| Selected managed clusters and cluster-set membership | Not recorded |
| User identities and actual group memberships | Not recorded |
| Permitted fleet metadata visibility | Not defined |
| Admission controls governing VM references and devices | Not recorded |

## Deployment and permissions

| Check | Acceptance criterion | Observed result | Evidence |
| --- | --- | --- | --- |
| Argo CD plugin setup | New repository-server init container completes; plugin mounted and enabled | Not run | Pending |
| Source-based rendering | Application builds the reviewed Kustomization without generation errors | Not run | Pending |
| Placement decisions | Hub only on hub placement; only approved targets on spoke placement | Not run | Pending |
| Role and namespace baseline | Compliant on every selected managed cluster before grants | Not run | Pending |
| Role ownership and drift | One intended policy per destination; an extra rule is remediated in a disposable test | Not run | Pending |
| MRA reconciliation in `policies` | All intended assignments reconcile with explicit target namespaces | Not run | Pending |
| Generated RoleBindings | Intended groups, roles, namespaces, and clusters only | Not run | Pending |
| Managed-cluster authorization script | All expected capabilities and denials pass on every target | Not run | Pending |
| Actual-user authorization | Actual group memberships yield the intended permissions | Not run | Pending |
| Maintainer operations | Approved VM create/edit and lifecycle workflow succeeds | Not run | Pending |
| Lifecycle operator operations | Start/stop/restart succeeds; create/edit/delete denied | Not run | Pending |
| Viewer operations | Intended reads succeed; modifications and lifecycle operations denied | Not run | Pending |
| Console and VNC | Denied for all three example tiers | Not run | Pending |
| Hub-hosted workloads | Example assignments grant no workload access on the hub | Not run | Pending |

## Console and search visibility

Repeat each check for all three real-user groups and include both directions for the example teams. Do not infer console behavior from managed-cluster authorization queries.

| Check | Acceptance criterion | Observed result | Evidence |
| --- | --- | --- | --- |
| Own VM inventory and details | Authorized namespace workloads are accessible | Not run | Pending |
| Other-team inventory | No unauthorized VM data in lists, filters, or details | Not run | Pending |
| Search by known other-team VM name and namespace | No unauthorized VM data returned | Not run | Pending |
| Direct link to another team's VM | Unauthorized details remain inaccessible | Not run | Pending |
| Cluster and namespace names, counts, and metadata | Matches the separately approved metadata-visibility requirement | Not run | Pending |
| Role and assignment discovery | Required custom roles and assignments appear to authorized administrators | Not run | Pending |

Record the installed `acm-vm-fleet:view` rules and any additional group bindings alongside these observations. If the required metadata boundary cannot be met through the shared console, document the additional controls or different access path chosen before acceptance.

## Revocation and placement changes

| Check | Acceptance criterion | Observed result | Evidence |
| --- | --- | --- | --- |
| Explicit revoke transition | Intended MRA and hub console binding removed | Not run | Pending |
| Downstream cleanup | Former MRA-generated RoleBindings removed on every affected cluster | Not run | Pending |
| Former access | Real-user and synthetic checks deny the removed grants, accounting for other bindings | Not run | Pending |
| Previously selected clusters | Placement changes leave no unintended former grants | Not run | Pending |
| Workload retention | Namespaces and VMs retained unless separately offboarded | Not run | Pending |

## Acceptance decision

- Outcome: Not assessed.
- Remaining failures or exceptions: Not assessed.
- Evidence reviewed by: Not recorded.
- Next action: Validate on one selected managed cluster with disposable workloads before wider rollout.
