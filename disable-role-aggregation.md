# Disabling KubeVirt Role Aggregation for Maximum Isolation

This guide extends the [Fine-Grained RBAC for Virtualization](virtrbac.md) blog and covers how to disable the default KubeVirt role aggregation in OpenShift Virtualization, giving cluster administrators full control over who can access virtual machine resources.

## The Problem: Implicit VM Access Through Role Aggregation

By default, the OpenShift Virtualization operator installs its ClusterRoles with Kubernetes [aggregation labels](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#aggregated-clusterroles). This means:

- Any user who is a namespace **admin** automatically inherits `kubevirt.io:admin` permissions
- Any user who is a namespace **editor** automatically inherits `kubevirt.io:edit` permissions
- Any user who is a namespace **viewer** automatically inherits `kubevirt.io:view` permissions

This happens silently—namespace admins can create, modify, and delete VMs in their namespace without any explicit VM-related role grant. For many organizations, especially those in regulated industries or with strict separation of duties, this implicit access is unacceptable.

### How Aggregation Works Under the Hood

The KubeVirt operator creates ClusterRoles like:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kubevirt.io:admin
  labels:
    rbac.authorization.k8s.io/aggregate-to-admin: "true"
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines", "virtualmachineinstances", ...]
    verbs: ["get", "list", "watch", "create", "update", "delete", "patch"]
```

The label `rbac.authorization.k8s.io/aggregate-to-admin: "true"` causes Kubernetes to automatically merge these rules into the built-in `admin` ClusterRole. The same pattern applies to `edit` and `view`.


## User Stories

### US-1: Cluster Administrator — Disable Aggregation

> "As a **cluster administrator**, I want to **disable KubeVirt role aggregation cluster-wide**, so that **namespace admins, editors, and viewers do not automatically inherit VM permissions**, and I can grant VM access explicitly only to users who need it."

**Acceptance Criteria:**
- A supported mechanism exists to disable role aggregation (e.g., HyperConverged CR field, annotation, or policy)
- After disabling, users with only `admin`/`edit`/`view` namespace roles have zero VM permissions
- The setting persists across operator reconciliation loops and upgrades
- The change can be reverted (re-enabling aggregation restores implicit access)

### US-2: Cluster Administrator — Preserve Explicit Bindings

> "As a **security-conscious cluster administrator**, I want to **ensure that disabling role aggregation does not break existing explicit RoleBindings** that directly reference `kubevirt.io:*` roles, so that **users who were intentionally granted VM access retain it while implicit access is removed.**"

**Acceptance Criteria:**
- Existing `RoleBinding` or `ClusterRoleBinding` resources that directly reference `kubevirt.io:admin`, `kubevirt.io:edit`, or `kubevirt.io:view` continue to function
- Existing MRA-managed bindings continue to function
- Only the aggregation path (implicit inheritance via namespace roles) is affected

### US-3: VM Owner — Retain Explicit Access

> "As a **VM owner**, I want to **retain my explicitly-granted VM permissions even when role aggregation is disabled**, so that **my day-to-day VM management workflow is unaffected by the policy change.**"

**Acceptance Criteria:**
- Users with direct `kubevirt.io:*` RoleBindings see no change in behavior
- The ACM console continues to function for users with explicit bindings
- No manual re-creation of bindings is required

### US-4: Fleet Administrator — Control Aggregation Across Clusters via ACM

> "As a **cluster administrator managing multiple clusters via ACM**, I want to **control the role aggregation setting per managed cluster through a policy or MRA configuration**, so that **I can enforce consistent least-privilege VM access across my fleet.**"

**Acceptance Criteria:**
- The aggregation toggle can be managed declaratively from the ACM Hub
- A `ConfigurationPolicy` or equivalent mechanism can enforce the setting across selected managed clusters
- Drift detection alerts when a managed cluster's aggregation setting deviates from the desired state


## Comparison: With vs. Without Role Aggregation

| Aspect | With Aggregation (default) | Without Aggregation |
|---|---|---|
| Namespace admin VM access | Automatic — full VM admin | None — must be explicitly granted |
| Namespace editor VM access | Automatic — full VM edit | None — must be explicitly granted |
| Namespace viewer VM access | Automatic — read-only VM access | None — must be explicitly granted |
| Operational overhead | Lower for VM-heavy organizations | Higher — requires explicit MRA/RoleBinding management |
| Security posture | Broader implicit access | Strict least-privilege enforcement |
| Compliance alignment | May not satisfy separation-of-duties requirements | Aligns with regulated industry requirements |
| Explicit `kubevirt.io:*` bindings | Work as expected | Work as expected (unaffected) |
| MRA-managed bindings | Work as expected | Work as expected (unaffected) |


## Technical Approaches

There are several possible mechanisms for disabling role aggregation. The right choice depends on upstream support and organizational constraints.

### Option A: HyperConverged CR Toggle (Preferred)

The cleanest approach is a first-class toggle in the HyperConverged custom resource:

```yaml
apiVersion: hco.kubevirt.io/v1beta1
kind: HyperConverged
metadata:
  name: kubevirt-hyperconverged
  namespace: openshift-cnv
spec:
  roleAggregation: disabled   # "enabled" (default) | "disabled"
```

When set to `disabled`, the operator would remove the `aggregate-to-*` labels from its managed ClusterRoles. This approach:
- Survives operator reconciliation and upgrades
- Is declarative and auditable
- Can be enforced via ACM `ConfigurationPolicy`

> [!NOTE]
> This requires an upstream enhancement to the HyperConverged operator. Track progress in the relevant KubeVirt/HCO enhancement proposals.

### Option B: ACM ConfigurationPolicy (Fleet-Wide Enforcement)

Use an ACM governance policy to enforce label removal across managed clusters:

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: Policy
metadata:
  name: disable-kubevirt-role-aggregation
  namespace: open-cluster-management-policies
spec:
  remediationAction: enforce
  disabled: false
  policy-templates:
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: remove-kubevirt-aggregation-labels
        spec:
          remediationAction: enforce
          severity: high
          object-templates:
            - complianceType: musthave
              objectDefinition:
                apiVersion: rbac.authorization.k8s.io/v1
                kind: ClusterRole
                metadata:
                  name: kubevirt.io:admin
                  labels:
                    rbac.authorization.k8s.io/aggregate-to-admin: "false"
            - complianceType: musthave
              objectDefinition:
                apiVersion: rbac.authorization.k8s.io/v1
                kind: ClusterRole
                metadata:
                  name: kubevirt.io:edit
                  labels:
                    rbac.authorization.k8s.io/aggregate-to-edit: "false"
            - complianceType: musthave
              objectDefinition:
                apiVersion: rbac.authorization.k8s.io/v1
                kind: ClusterRole
                metadata:
                  name: kubevirt.io:view
                  labels:
                    rbac.authorization.k8s.io/aggregate-to-view: "false"
```

> [!CAUTION]
> **Operator Reconciliation Conflict:** The OpenShift Virtualization operator may continuously reconcile these labels back to `"true"`. This creates a "fight" between the policy engine and the operator. Until a native HCO toggle exists (Option A), test this approach thoroughly in a non-production environment to understand reconciliation behavior.

### Option C: Manual ClusterRole Patch (Single Cluster)

For testing or single-cluster environments, you can patch the ClusterRoles directly:

```bash
# Remove aggregation labels from all kubevirt.io ClusterRoles
for role in kubevirt.io:admin kubevirt.io:edit kubevirt.io:view; do
  oc patch clusterrole "$role" --type=json -p \
    '[{"op":"remove","path":"/metadata/labels/rbac.authorization.k8s.io~1aggregate-to-admin"},
      {"op":"remove","path":"/metadata/labels/rbac.authorization.k8s.io~1aggregate-to-edit"},
      {"op":"remove","path":"/metadata/labels/rbac.authorization.k8s.io~1aggregate-to-view"}]' \
    2>/dev/null
done
```

> [!WARNING]
> This change will likely be reverted on the next operator reconciliation cycle. Use this only for validation and testing.


## Migration Guide: Safely Disabling Role Aggregation

> [!WARNING]
> Disabling role aggregation is a **breaking change** for any user who currently relies on implicit VM access through their namespace role. Follow this checklist carefully.

### Step 1: Audit Current Access

Identify all users who currently access VMs through aggregated roles:

```bash
# List all RoleBindings that reference the built-in admin/edit/view ClusterRoles
# These users currently have IMPLICIT VM access via aggregation
oc get rolebindings -A -o json | jq -r '
  .items[] |
  select(.roleRef.name == "admin" or .roleRef.name == "edit" or .roleRef.name == "view") |
  "\(.metadata.namespace)\t\(.roleRef.name)\t\(.subjects[]?.name // "N/A")"
' | sort | column -t
```

```bash
# List all RoleBindings that directly reference kubevirt.io:* roles
# These users have EXPLICIT VM access and will NOT be affected
oc get rolebindings -A -o json | jq -r '
  .items[] |
  select(.roleRef.name | startswith("kubevirt.io:")) |
  "\(.metadata.namespace)\t\(.roleRef.name)\t\(.subjects[]?.name // "N/A")"
' | sort | column -t
```

### Step 2: Create Explicit Bindings for Users Who Need VM Access

For each user identified in Step 1 who should retain VM access, create an MRA or explicit RoleBinding:

```yaml
apiVersion: rbac.open-cluster-management.io/v1alpha1
kind: MulticlusterRoleAssignment
metadata:
  name: vm-access-for-team-a
  namespace: open-cluster-management
spec:
  clusterSelector:
    matchLabels:
      env: production
  subjects:
    - kind: Group
      name: team-a-vm-admins
      apiGroup: rbac.authorization.k8s.io
  roleBindings:
    - namespace: team-a-workloads
      roleRef:
        kind: ClusterRole
        name: kubevirt.io:admin
        apiGroup: rbac.authorization.k8s.io
```

### Step 3: Disable Role Aggregation

Apply the chosen mechanism (Option A, B, or C from above).

### Step 4: Verify

```bash
# Confirm aggregation labels are removed
oc get clusterrole kubevirt.io:admin -o jsonpath='{.metadata.labels}' | jq .

# Test as a namespace admin — should NOT have VM access
oc auth can-i get virtualmachines -n <namespace> --as=<namespace-admin-user>
# Expected: "no"

# Test as an explicitly-bound user — should still have VM access
oc auth can-i get virtualmachines -n <namespace> --as=<explicitly-bound-user>
# Expected: "yes"
```

### Step 5: Monitor

Set up ongoing compliance monitoring to detect drift:
- If using ACM Policy (Option B): The policy engine reports compliance status automatically
- If using HCO toggle (Option A): Use an `InformPolicy` to verify the HCO CR setting across clusters


## Relationship to Fine-Grained RBAC

Disabling role aggregation is the natural complement to ACM Fine-Grained RBAC. Together they form a complete least-privilege model:

1. **Fine-Grained RBAC** (described in [virtrbac.md](virtrbac.md)) provides the mechanism to **explicitly grant** VM access through the MRA API and spoke-cluster bindings
2. **Disabled Role Aggregation** (this document) removes the **implicit grant** path, ensuring that the only way to get VM access is through explicit assignment

Without disabling aggregation, fine-grained RBAC is additive but not exclusive—users still get implicit access through their namespace roles. Disabling aggregation closes that gap and makes the MRA the single source of truth for VM access.


## Open Questions

- **Upstream support timeline:** When will the HyperConverged operator support a native `roleAggregation` toggle? This is the most sustainable path.
- **Granularity:** Should it be possible to disable aggregation selectively (e.g., disable for `admin` but keep for `view`)? Or is all-or-nothing sufficient?
- **Cluster-scoped vs. namespace-scoped:** Should the toggle apply cluster-wide, or could it be namespace-scoped (e.g., disable aggregation only in sensitive namespaces)?
- **Upgrade behavior:** If aggregation is disabled and the operator is upgraded, does the new operator version re-enable aggregation? How is this handled?
