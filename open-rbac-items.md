# Open RBAC items

Pulled out of [RBAC in ACM: the patterns you need](rbac-acm-fleet.md) on 21 October 2026, then filled from Jira.

Open means the status category is not Done. The project queries match `summary ~ "RBAC"`. A summary that does not contain that word is not in the project tables. Counts were taken from the Jira navigator on that date.

| Project | Query result |
| --- | --- |
| ACM (RHACM) | 34 |
| CNV (OpenShift Virtualization) | 20 |
| GITOPS | 3, all about removing `kube-rbac-proxy` |
| HOSTEDCP and HYPERSHIFT | No open issue whose summary contains RBAC |

## Removed from the fleet guide

These were the only issue keys in the guide. They are not all in the ACM summary table below.

| Item | What it tracks | What this pass could confirm |
| --- | --- | --- |
| [ACM-32299](https://redhat.atlassian.net/browse/ACM-32299) | One RBAC model for the ACM console and the Argo CD UI | Not in the open ACM summary search. Status was not re-opened. |
| RFE-9684 | Fine-grained RBAC for Argo CD applications inside the ACM UI | Request id only. Not a key in the ACM summary search. |
| RFE-10027 | `destinationServiceAccounts` impersonation in the argocd-agent resource proxy | Request id only. Not a key in the ACM summary search. |
| RFE-9986 | Same agent-proxy impersonation request | Request id only. Not a key in the ACM summary search. |
| [argocd-agent 1152](https://github.com/argoproj-labs/argocd-agent/issues/1152) | Agent Resource Proxy should use `destinationServiceAccounts` when specified | Open on GitHub |
| [ACM-47215](https://redhat.atlassian.net/browse/ACM-47215) | Fold migration ClusterRoles into the extended virtualization roles. The request spells the role `storagemigrate-multins` (hyphen). The console has shown an underscore. | Not in the open ACM summary search. Status was not re-opened. |

`destinationServiceAccounts` on the agent proxy is requested, not shipped. One RBAC model that covers the ACM console and the Argo CD UI is also requested, not shipped.

## RHACM

### Observability

| Key | Summary | Status | Parent |
| --- | --- | --- | --- |
| [ACM-19058](https://redhat.atlassian.net/browse/ACM-19058) | Advanced RBAC in Observability | In Progress | |
| [ACM-12474](https://redhat.atlassian.net/browse/ACM-12474) | MCOA Observability AuthZ (fine-grain RBAC) | In Progress | ACM-19058 |
| [ACM-35869](https://redhat.atlassian.net/browse/ACM-35869) | Fine-Grained Observability RBAC via MultiClusterRoleAssignment | Review | ACM-12474 |
| [ACM-48452](https://redhat.atlassian.net/browse/ACM-48452) | Enable fine-grained RBAC (MCRA) by default out of the box | New | |
| [ACM-48465](https://redhat.atlassian.net/browse/ACM-48465) | Feature gate for observability fine-grained RBAC enforcement, default off | New | ACM-12474 |
| [ACM-48463](https://redhat.atlassian.net/browse/ACM-48463) | Compose RBAC scope matchers with per-cluster tenancy matchers in a single producer | New | ACM-12474 |
| [ACM-48469](https://redhat.atlassian.net/browse/ACM-48469) | Point Grafana/Perses at the MCOA gateway and take rbac-query-proxy out of the query path | New | ACM-19058 |
| [ACM-48470](https://redhat.atlassian.net/browse/ACM-48470) | Cutover behaviour for existing metrics users when fine-grained RBAC is enabled | New | ACM-12474 |
| [ACM-48471](https://redhat.atlassian.net/browse/ACM-48471) | Scope fine-grained RBAC for Alertmanager (view and silence) | New | ACM-12474 |
| [ACM-48472](https://redhat.atlassian.net/browse/ACM-48472) | Scope fine-grained RBAC enforcement for traces | New | ACM-12474 |
| [ACM-48473](https://redhat.atlassian.net/browse/ACM-48473) | Update must-gather for the fine-grained RBAC enforcement path | New | ACM-12474 |
| [ACM-48475](https://redhat.atlassian.net/browse/ACM-48475) | Document known limitations and the enforcement model for fine-grained observability RBAC | New | ACM-12474 |
| [ACM-12525](https://redhat.atlassian.net/browse/ACM-12525) | Testing automation: Fine-grain RBAC feature | New | |
| [ACM-17474](https://redhat.atlassian.net/browse/ACM-17474) | Automation: verify fine-grained RBAC (2.11+) | New | ACM-18745 |
| [ACM-31143](https://redhat.atlassian.net/browse/ACM-31143) | Document how historical ACM RBAC role bindings interact with the fine-grained RBAC experience | Backlog | |

### Virtualization

| Key | Summary | Status |
| --- | --- | --- |
| [ACM-48321](https://redhat.atlassian.net/browse/ACM-48321) | Add Forklift Plan view permission to migration RBAC | In Progress |
| [ACM-47712](https://redhat.atlassian.net/browse/ACM-47712) | Spike: Investigate ClusterRole aggregation for CNV UI RBAC | New |
| [ACM-45327](https://redhat.atlassian.net/browse/ACM-45327) | Remove obsolete OpenShift Virtualization RBAC roles from ACM 2.16, 2.17, and 5.0+ documentation | New |

### GitOps

| Key | Summary | Status | Parent |
| --- | --- | --- | --- |
| [ACM-7925](https://redhat.atlassian.net/browse/ACM-7925) | Generate cluster secrets with the RBAC service account or user used by the Argo CD push model | New | |
| [ACM-14544](https://redhat.atlassian.net/browse/ACM-14544) | A ClusterRole for fine-grained ApplicationSet RBAC should not depend on AppSub | New | ACM-15003 |

### Console, search, and install RBAC

| Key | Summary | Status | Parent |
| --- | --- | --- | --- |
| [ACM-47307](https://redhat.atlassian.net/browse/ACM-47307) | Create cluster pool, Add credential, and Create placement stay enabled for users with no permissions | Testing | |
| [ACM-11615](https://redhat.atlassian.net/browse/ACM-11615) | RBAC Permissions Refinement | New | |
| [ACM-10001](https://redhat.atlassian.net/browse/ACM-10001) | MCH: prohibit wildcards in RBAC permissions | New | |
| [ACM-10002](https://redhat.atlassian.net/browse/ACM-10002) | MCE: prohibit wildcards in RBAC permissions | New | |
| [ACM-12787](https://redhat.atlassian.net/browse/ACM-12787) | Remove wildcards in RBAC permission for component resources | Backlog | ACM-11615 |
| [ACM-15086](https://redhat.atlassian.net/browse/ACM-15086) | Spike: MCE components with wildcard RBAC | Backlog | ACM-11615 |
| [ACM-15087](https://redhat.atlassian.net/browse/ACM-15087) | Spike: MCH components with wildcard RBAC | New | ACM-11615 |
| [ACM-4584](https://redhat.atlassian.net/browse/ACM-4584) | Add CI checks for controller RBAC | New | |
| [ACM-15360](https://redhat.atlassian.net/browse/ACM-15360) | Move RBAC attributes out of JSONB | New | ACM-21682 |
| [ACM-36405](https://redhat.atlassian.net/browse/ACM-36405) | Hive: network-policy RBAC in the operator CSV | New | ACM-36402 |
| [ACM-36461](https://redhat.atlassian.net/browse/ACM-36461) | Submariner: network-policy RBAC in the operator CSV | New | ACM-36458 |
| [ACM-47068](https://redhat.atlassian.net/browse/ACM-47068) | CVE-2026-56854 in `kube-rbac-proxy` for RHACM 5.1 | New | |
| [ACM-47691](https://redhat.atlassian.net/browse/ACM-47691) | Refactor RBAC setup to use AsUser() | In Progress | ACM-27437 |
| [ACM-48480](https://redhat.atlassian.net/browse/ACM-48480) | Check for RBAC SSE races | New | ACM-47956 |

## OpenShift Virtualization

Parent [CNV-63843](https://redhat.atlassian.net/browse/CNV-63843), "DP: More fine grained RBAC Roles", is open. Its parent is [VIRTSTRAT-721](https://redhat.atlassian.net/browse/VIRTSTRAT-721), fine-grained RBAC roles for VM operations via an admission webhook, Developer Preview.

| Key | Summary | Status | Parent |
| --- | --- | --- | --- |
| [CNV-63843](https://redhat.atlassian.net/browse/CNV-63843) | DP: More fine grained RBAC Roles | New | VIRTSTRAT-721 |
| [CNV-69722](https://redhat.atlassian.net/browse/CNV-69722) | Implement separation of RBAC roles | New | CNV-63843 |
| [CNV-69723](https://redhat.atlassian.net/browse/CNV-69723) | Update documentation after the role split | New | CNV-63843 |
| [CNV-69724](https://redhat.atlassian.net/browse/CNV-69724) | Update upstream docs after the role split | New | CNV-63843 |
| [CNV-23061](https://redhat.atlassian.net/browse/CNV-23061) | Audit virt-operator so it does not keep unnecessary RBAC rules | New | CNV-63843 |
| [CNV-86723](https://redhat.atlassian.net/browse/CNV-86723) | Middle-tier RBAC role for VM lifecycle operations | New | |
| [CNV-55980](https://redhat.atlassian.net/browse/CNV-55980) | RBAC at a folder level, with a VM tree and grouping | In Progress | |
| [CNV-78368](https://redhat.atlassian.net/browse/CNV-78368) | kubevirt-smart-inventory: tighter RBAC permission check | New | |
| [CNV-95785](https://redhat.atlassian.net/browse/CNV-95785) | HCO RBAC and proxy deployment wiring | New | CNV-95778 |
| [CNV-95797](https://redhat.atlassian.net/browse/CNV-95797) | Open the audit dashboard in Perses behind bundle and RBAC gates | New | CNV-95790 |
| [CNV-96105](https://redhat.atlassian.net/browse/CNV-96105) | RBAC for an unprivileged user in UDN scenarios | New | |
| [CNV-96778](https://redhat.atlassian.net/browse/CNV-96778) | SSP operator stopped restoring a modified os-images RBAC RoleBinding | New | |
| [CNV-99382](https://redhat.atlassian.net/browse/CNV-99382) | Investigate whether the operator CSV and Role RBAC match | New | CNV-73877 |
| [CNV-97043](https://redhat.atlassian.net/browse/CNV-97043) | Investigate RBAC CDI test failures | New | |
| [CNV-93483](https://redhat.atlassian.net/browse/CNV-93483) | QE: MCP tool authorization across users and namespaces | New | CNV-93479 |

vTPM Windows tests need an RBAC role in `validation-os-images`. The 4.22 item is [CNV-96371](https://redhat.atlassian.net/browse/CNV-96371) (Planning). The same summary is open as a backport on [CNV-96370](https://redhat.atlassian.net/browse/CNV-96370) (4.21), [CNV-96369](https://redhat.atlassian.net/browse/CNV-96369) (4.20), [CNV-96368](https://redhat.atlassian.net/browse/CNV-96368) (4.19), and [CNV-96367](https://redhat.atlassian.net/browse/CNV-96367) (4.18).

## GitOps

| Key | Summary | Status | Parent |
| --- | --- | --- | --- |
| [GITOPS-11010](https://redhat.atlassian.net/browse/GITOPS-11010) | GitOps-Promoter: remove kube-rbac-proxy | New | |
| [GITOPS-11399](https://redhat.atlassian.net/browse/GITOPS-11399) | Remove kube-rbac-proxy and migrate metrics security to controller-runtime auth | In Progress | GITOPS-11010 |
| [GITOPS-11401](https://redhat.atlassian.net/browse/GITOPS-11401) | Remove kube-rbac-proxy image references from the Helm chart and manifests | New | GITOPS-11399 |

Application RBAC for Argo CD on an ACM hub is in the RHACM table (`ACM-7925`, `ACM-14544`) and in the items removed from the guide.

## Hosted control planes

`HOSTEDCP` and `HYPERSHIFT` had no open issue whose summary contains RBAC on 21 October 2026. This pass did not search summaries that say "authorization" or "permission" without the word RBAC.
