# RHACM RBAC Architecture for VirtualMachines with PolicyGenerator

To implement the "Policy-to-UI" RBAC architecture using the PolicyGenerator, you provide the raw Kubernetes manifests for your ClusterRoles and MultiClusterRoleAssignment (MRA), and use a single PolicyGenerator configuration file to compile them into a unified PolicySet targeted at the correct Hub and Spoke clusters.

This guide demonstrates a **multi-tenant** setup where three different teams receive different levels of VM access through the same GitOps pipeline.

---

## 1. Directory Structure

Create a clean separation between the raw manifests intended for the Hub and those intended for the Spoke clusters. Each tenant gets its own MRA file:

```
vm-rbac-config/
├── kustomization.yaml
├── policy-generator.yaml
├── hub-manifests/
│   ├── 01-hub-clusterrole-execution.yaml
│   ├── 02-hub-clusterrole-admin.yaml
│   ├── 03-hub-mra-tenant-a.yaml
│   ├── 04-hub-mra-tenant-b.yaml
│   └── 05-hub-mra-tenant-c.yaml
└── spoke-manifests/
    ├── 01-spoke-clusterrole-execution.yaml
    └── 02-spoke-clusterrole-admin.yaml
```

## 2. Raw Kubernetes Manifests

These are standard Kubernetes YAML files. The PolicyGenerator will automatically convert them into compliance objects. We define two role tiers — both are minimal roles designed to be **layered on top of `kubevirt.io:view`**, which already provides read access to VMs, instances, DataVolumes, and other resources.

### `hub-manifests/01-hub-clusterrole-execution.yaml` — Execution Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-execution-role
  labels:
    # Mandatory label for RHACM Fleet Management UI discovery
    rbac.open-cluster-management.io/filter: vm-clusterroles
    clusterview.open-cluster-management.io/discoverable: "true"
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["subresources.kubevirt.io"]
    resources: ["virtualmachines/start", "virtualmachines/stop", "virtualmachines/restart"]
    verbs: ["update"]
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list", "watch"]
```

### `hub-manifests/02-hub-clusterrole-admin.yaml` — Admin Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-admin-role
  labels:
    rbac.open-cluster-management.io/filter: vm-clusterroles
    clusterview.open-cluster-management.io/discoverable: "true"
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines"]
    verbs: ["create", "update", "patch"]
  - apiGroups: ["subresources.kubevirt.io"]
    resources: ["virtualmachines/start", "virtualmachines/stop", "virtualmachines/restart"]
    verbs: ["update"]
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list", "watch"]
```

### `hub-manifests/03-hub-mra-tenant-a.yaml` — Tenant A: Full VM Admin

Tenant A operators can create, update, and manage VMs. Combined with `kubevirt.io:view`, they get full read access plus write permissions — but notably no `delete` verb.

```yaml
apiVersion: rbac.open-cluster-management.io/v1alpha1
kind: MultiClusterRoleAssignment
metadata:
  name: tenant-a-vm-assignment
  namespace: tenant-a-namespace
spec:
  subject:
    kind: Group
    name: "tenant-a-operators"
    apiGroup: rbac.authorization.k8s.io
  roles:
    - custom-vm-admin-role
    - kubevirt.io:view
```

### `hub-manifests/04-hub-mra-tenant-b.yaml` — Tenant B: Execution Only

Tenant B operators can start, stop, and restart VMs, but cannot create or delete them.

```yaml
apiVersion: rbac.open-cluster-management.io/v1alpha1
kind: MultiClusterRoleAssignment
metadata:
  name: tenant-b-vm-assignment
  namespace: tenant-b-namespace
spec:
  subject:
    kind: Group
    name: "tenant-b-operators"
    apiGroup: rbac.authorization.k8s.io
  roles:
    - custom-vm-execution-role
    - kubevirt.io:view
```

### `hub-manifests/05-hub-mra-tenant-c.yaml` — Tenant C: Read-Only

Tenant C viewers can only observe VM state; they have no write or execution permissions.

```yaml
apiVersion: rbac.open-cluster-management.io/v1alpha1
kind: MultiClusterRoleAssignment
metadata:
  name: tenant-c-vm-assignment
  namespace: tenant-c-namespace
spec:
  subject:
    kind: Group
    name: "tenant-c-viewers"
    apiGroup: rbac.authorization.k8s.io
  roles:
    - kubevirt.io:view
```

### Multi-Tenant Summary

| Tenant | Group | Namespace | Roles | Effective Access |
|--------|-------|-----------|-------|-----------------|
| A | `tenant-a-operators` | `tenant-a-namespace` | `custom-vm-admin-role`, `kubevirt.io:view` | Create, update, patch VMs + start/stop/restart |
| B | `tenant-b-operators` | `tenant-b-namespace` | `custom-vm-execution-role`, `kubevirt.io:view` | Start, stop, restart existing VMs |
| C | `tenant-c-viewers` | `tenant-c-namespace` | `kubevirt.io:view` | Read-only VM visibility |

### `spoke-manifests/01-spoke-clusterrole-execution.yaml` — Remote Execution Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-execution-role
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["subresources.kubevirt.io"]
    resources: ["virtualmachines/start", "virtualmachines/stop", "virtualmachines/restart"]
    verbs: ["update"]
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list", "watch"]
```

### `spoke-manifests/02-spoke-clusterrole-admin.yaml` — Remote Admin Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-admin-role
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines"]
    verbs: ["create", "update", "patch"]
  - apiGroups: ["subresources.kubevirt.io"]
    resources: ["virtualmachines/start", "virtualmachines/stop", "virtualmachines/restart"]
    verbs: ["update"]
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list", "watch"]
```

---

## 3. PolicyGenerator Configuration

The `policy-generator.yaml` defines the Hub policy and the Spoke policy, sets the cluster placements, and logically groups them into a PolicySet. All tenant MRAs are bundled into a single Hub policy.

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: PolicyGenerator
metadata:
  name: vm-rbac-generator
policyDefaults:
  namespace: policies         # The namespace on the Hub where policies reside
  remediationAction: enforce  # Instructs ACM to create the objects
  complianceType: musthave    # Ensures the objects exist exactly as defined
  policySets:
    # Automatically generates the PolicySet object linking the generated policies
    - name: vm-fine-grained-rbac-policyset
      description: "Deploys Custom VM ClusterRoles and MultiClusterRoleAssignments for all tenants"
policies:
  # --- 1. HUB POLICY ---
  - name: policy-hub-vm-rbac
    placement:
      labelSelector:
        matchExpressions:
          - key: name
            operator: In
            values: ["local-cluster"] # Targets ONLY the Hub
    manifests:
      - path: hub-manifests/01-hub-clusterrole-execution.yaml
      - path: hub-manifests/02-hub-clusterrole-admin.yaml
      - path: hub-manifests/03-hub-mra-tenant-a.yaml
      - path: hub-manifests/04-hub-mra-tenant-b.yaml
      - path: hub-manifests/05-hub-mra-tenant-c.yaml

  # --- 2. SPOKE POLICY ---
  - name: policy-spoke-vm-rbac
    placement:
      labelSelector:
        matchExpressions:
          - key: name
            operator: NotIn
            values: ["local-cluster"] # Targets ALL managed clusters EXCEPT the Hub
    manifests:
      - path: spoke-manifests/01-spoke-clusterrole-execution.yaml
      - path: spoke-manifests/02-spoke-clusterrole-admin.yaml
```

---

## 4. Kustomization File

Trigger the PolicyGenerator using a `kustomization.yaml` file:

```yaml
generators:
  - policy-generator.yaml
```

## How to Deploy

When Argo CD (or standard Kustomize) processes this directory, the PolicyGenerator plugin will natively emit the complex RHACM Policies, ConfigurationPolicies, Placements, PlacementBindings, and the PolicySet grouping.

Because the generator handles the boilerplate, your GitOps repository remains clean — containing only the raw RBAC rules and a simple routing configuration.

## Adding a New Tenant

To onboard a new tenant, you only need to:

1. Create a new MRA YAML file in `hub-manifests/` with the tenant's group, namespace, and desired role(s).
2. Add the new file path to the `policy-hub-vm-rbac` manifests list in `policy-generator.yaml`.
3. Commit and push — Argo CD or your GitOps pipeline handles the rest.

No changes are needed on spoke clusters, since the ClusterRole definitions are already deployed. The MRA API handles creating the appropriate RoleBindings on managed clusters automatically.
