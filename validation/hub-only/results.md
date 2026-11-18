# Hub-only live validation on 18 November 2026

## Outcome

The authorized hub-only run passed the policy-generation, namespace-scoped authorization, VM API, drift-remediation, and revocation/restoration checks described below. It used ACM **5.1.0-184**, not an ACM 5.0 hub. It is a single-cluster control-plane test, not full validation of the article's multi-cluster topology or running guests.

The Application is left synchronized at the restored source revision, with all three example assignments ready. Disposable VM and VMI objects have been removed. The installed GitOps and virtualization operators, enabled fine-grained RBAC component, example namespaces, policies, roles, assignments, and validation Application remain for inspection.

## Environment and scope

| Component | Observed value |
| --- | --- |
| ACM | `5.1.0-184` |
| Multicluster engine | `5.1.0-193` |
| OpenShift | `5.0.1` |
| OpenShift GitOps operator | `1.22.3`, Succeeded |
| OpenShift Virtualization operator | `5.0.0`, Succeeded |
| Target | Self-managed `local-cluster` only |
| Nodes | Three AWS `m6a.2xlarge` nodes |
| Allocatable KVM devices | `0` on all three nodes |
| Setup identity | `kube:admin` |
| Tested workload identities | Synthetic users with explicit example groups, using Kubernetes impersonation |

The PolicyGenerator init container used `registry.redhat.io/rhacm2/multicluster-operators-subscription-rhel9:v5.0`, resolved to digest `sha256:01322ba0fd669d824779e6262319ceff43d0ded5b50c1c05f62b1cc82caee29e`, and completed with exit code `0`. See [environment evidence](evidence/environment.json).

## Adaptations for the authorized hub-only test

The original multi-cluster source remains separate from this overlay. The overlay changes `vm-rbac-spokes` to select `local-cluster` and disables `vm-rbac-hub-roles`, so the baseline policy is the sole manager of the custom roles on that cluster. The management namespace remains `policies`. Bootstrap resources were applied separately, and Argo CD ran the source Kustomization through the configured PolicyGenerator plugin.

The current overlay represents the restored second-stage configuration: its assignment policy is enabled. It is not the initial disabled-grant state. Use the stage-one commit below when reproducing that checkpoint.

## Source revisions

| Checkpoint | Configuration commit |
| --- | --- |
| Baseline with assignments disabled | [`5c84367`](https://github.com/ch-stark/finegrainedrbacvirt/commit/5c843671436c02c1deee99dd4dbceb192a679cab) |
| Enable assignments | [`db0b43d`](https://github.com/ch-stark/finegrainedrbacvirt/commit/db0b43d1e40bd7772f6b6cda6e7238e60aec08dd) |
| Correct authorization probes and revoke Tenant B | [`d2198c4`](https://github.com/ch-stark/finegrainedrbacvirt/commit/d2198c4b832ad5d012df870040c84f27f1dcc6c0) |
| Restore Tenant B | [`f5f158e`](https://github.com/ch-stark/finegrainedrbacvirt/commit/f5f158e46976f0b8db1ebafc69b8ecd1fac9beab) |

## Observed results

| Check | Result | Evidence |
| --- | --- | --- |
| Argo CD source generation and sync | Succeeded; final state `Synced` | [Final state](evidence/final-state.json) |
| Role/namespace baseline | `Compliant` before assignment enablement | [Stage one](evidence/stage1-policies.json) |
| MRAs in `policies` | Three resources ready; five role assignments active on `local-cluster` | [Assignments](evidence/stage2-assignments.json) |
| Generated workload bindings | Five RoleBindings with intended namespaces, roles, and groups | [Bindings](evidence/stage2-bindings.json) |
| Authorization suite after restoration | **57/57 passed** using explicit SelfSubjectAccessReview attributes and `--hub-only` | [Authorization results](evidence/authorization-results.json) |
| VM API requests | **18/18 passed** after virtualization webhooks became ready | [API results](evidence/vm-api-results.json) |
| Rule drift | Inert test rule observed in patch response and removed before the follow-up check | [Drift result](evidence/drift-results.json) |
| Tenant B revocation | MRA, two workload bindings, and fleet binding removed; VM-list, start, and namespace-list permissions denied | [Revocation](evidence/revocation-results.json) |
| Restoration | Three MRAs ready; enabled policies compliant; authorization suite passed again | [Final state](evidence/final-state.json) |
| Disposable workload cleanup | No validation VM or VMI objects remain | [Cleanup](evidence/cleanup.json) |

The API checks exercised actual requests under impersonated example identities: maintainer VM creation and patching succeeded; lifecycle/viewer creation and editing were denied; deletion and cross-team reads were denied. The lifecycle operator's start and stop requests returned HTTP `202`.

## What the first run exposed

The original `oc auth can-i` form mis-resolved lifecycle resources through client discovery, querying the wrong authorization group. The checker now sends explicit `group`, `resource`, and `subresource` attributes to the SelfSubjectAccessReview API. A direct authorization query confirmed that `virtualmachines/start` is permitted in `subresources.kubevirt.io` and denied in `kubevirt.io` for the lifecycle identity.

The hub's installed `acm-vm-fleet:view` role grants `get/list/watch` on namespaces and ConfigMaps. Namespace listing therefore differs from a spoke-only workload test. The new `--hub-only` checker mode expects the hub grant rather than silently skipping that check. Namespace listing was denied again when Tenant B's fleet binding was revoked.

The first VM API run passed 16 of 18 checks. Start failed with HTTP `500` because the kubemacpool webhook had no ready endpoint; stop then returned `409` because the VM had not started. After its pod became ready, a fresh run passed all 18 checks. The [first-attempt observations](evidence/vm-api-results-first-attempt.json) are retained rather than hidden.

## Remaining validation

- **Running guests and complete lifecycle operations:** Not established. The VMI reached `Scheduling`, with an unschedulable condition reporting insufficient KVM devices. API acceptance is distinct from a running guest. See [guest scheduling](evidence/guest-scheduling.json).
- **Separate managed clusters and remote propagation:** Not tested; only the self-managed hub was registered.
- **ACM 5.0 hub compatibility:** Not established by this run; record the actual installed ACM build above.
- **Real identity-provider membership, browser console, search, direct-link visibility, and role discovery:** Not tested with real tenant logins. Synthetic API impersonation does not replace these checks.
- **Full provisioning workflows and admission guardrails:** Not tested. Disposable VMs had minimal halted specifications without guest disks. Storage imports, approved Secret/ConfigMap references, networking, devices, and admission rules need environment-specific validation.

The result supports the tested hub-only control-plane behavior. Complete the remaining checks in the article's [validation record](../../vm-rbac-example/validation-results.md) before accepting a broader deployment.
