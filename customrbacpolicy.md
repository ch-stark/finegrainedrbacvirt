# RHACM RBAC Architecture for VirtualMachines with PolicyGenerator

This document outlines implementing a "Policy-to-UI" RBAC architecture using PolicyGenerator for managing virtual machine access across Red Hat Advanced Cluster Management (RHACM) Hub and Spoke clusters. It demonstrates a **multi-tenant** setup where different teams receive different levels of VM access.

## Directory Organization

The configuration separates Hub and Spoke manifests, with per-tenant MRA definitions:

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

## Hub Cluster Roles (UI Discovery)

Each Hub ClusterRole includes a mandatory label for RHACM Fleet Management UI discovery. We define two tiers: an **execution** role (start/stop/restart) and an **admin** role (full VM lifecycle including create and delete).

### Execution Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-execution-role
  labels:
    rbac.open-cluster-management.io/filter: vm-clusterroles
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines", "virtualmachineinstances"]
    verbs: ["get", "list", "watch", "start", "stop", "restart"]
```

### Admin Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-admin-role
  labels:
    rbac.open-cluster-management.io/filter: vm-clusterroles
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines", "virtualmachineinstances"]
    verbs: ["get", "list", "watch", "create", "delete", "update", "patch", "start", "stop", "restart"]
```

## MultiClusterRoleAssignments (Fleet Assignment per Tenant)

Each tenant gets its own MRA, binding the appropriate ClusterRole(s) to the tenant's group and namespace. This is the key to multi-tenancy: different groups receive different permission levels through the same PolicyGenerator pipeline.

### Tenant A — Full VM Admin

Tenant A operators manage the full VM lifecycle, including creating and deleting VMs.

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

### Tenant B — Execution Only

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

### Tenant C — Read-Only

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

## Multi-Tenant Summary

| Tenant | Group | Namespace | Roles | Effective Access |
|--------|-------|-----------|-------|-----------------|
| A | `tenant-a-operators` | `tenant-a-namespace` | `custom-vm-admin-role`, `kubevirt.io:view` | Full VM lifecycle (create, delete, start, stop, restart) |
| B | `tenant-b-operators` | `tenant-b-namespace` | `custom-vm-execution-role`, `kubevirt.io:view` | Start, stop, restart existing VMs |
| C | `tenant-c-viewers` | `tenant-c-namespace` | `kubevirt.io:view` | Read-only VM visibility |

## Spoke Cluster Roles (Remote Execution)

The Spoke ClusterRoles mirror the Hub definitions with matching names. Both tiers must be distributed so that MRA bindings resolve correctly on managed clusters.

### Execution Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-execution-role
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines", "virtualmachineinstances"]
    verbs: ["get", "list", "watch", "start", "stop", "restart"]
```

### Admin Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-admin-role
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines", "virtualmachineinstances"]
    verbs: ["get", "list", "watch", "create", "delete", "update", "patch", "start", "stop", "restart"]
```

## PolicyGenerator Configuration

The generator routes manifests to appropriate clusters via placement selectors. All tenant MRAs are bundled into a single Hub policy, while spoke clusters receive the ClusterRole definitions. You can optionally split spoke policies by environment to further restrict which roles are available on which clusters.

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: PolicyGenerator
metadata:
  name: vm-rbac-generator
policyDefaults:
  namespace: policies
  remediationAction: enforce
  complianceType: musthave
  policySets:
    - name: vm-fine-grained-rbac-policyset
      description: "Deploys Custom VM ClusterRoles and MultiClusterRoleAssignments for all tenants"
policies:
  - name: policy-hub-vm-rbac
    placement:
      labelSelector:
        matchExpressions:
          - key: name
            operator: In
            values: ["local-cluster"]
    manifests:
      - path: hub-manifests/01-hub-clusterrole-execution.yaml
      - path: hub-manifests/02-hub-clusterrole-admin.yaml
      - path: hub-manifests/03-hub-mra-tenant-a.yaml
      - path: hub-manifests/04-hub-mra-tenant-b.yaml
      - path: hub-manifests/05-hub-mra-tenant-c.yaml

  - name: policy-spoke-vm-rbac-production
    placement:
      labelSelector:
        matchLabels:
          env: production
    manifests:
      - path: spoke-manifests/01-spoke-clusterrole-execution.yaml
      - path: spoke-manifests/02-spoke-clusterrole-admin.yaml

  - name: policy-spoke-vm-rbac-staging
    placement:
      labelSelector:
        matchLabels:
          env: staging
    manifests:
      - path: spoke-manifests/01-spoke-clusterrole-execution.yaml
```

With environment-based placement, staging clusters only receive the execution role, while production clusters get both execution and admin roles. This adds another layer of protection: even if Tenant A has admin permissions via MRA, those permissions only take effect on clusters where the admin ClusterRole has been deployed.

## Kustomization Deployment

```yaml
generators:
  - policy-generator.yaml
```

The PolicyGenerator automatically produces the complete RHACM infrastructure including Policies, ConfigurationPolicies, Placements, PlacementBindings, and PolicySet groupings when processed by Argo CD or Kustomize.

## Adding a New Tenant

To onboard a new tenant, you only need to:

1. Create a new MRA YAML file in `hub-manifests/` with the tenant's group, namespace, and desired role(s).
2. Add the new file path to the `policy-hub-vm-rbac` manifests list in `policy-generator.yaml`.
3. Commit and push — Argo CD or your GitOps pipeline handles the rest.

No changes are needed on spoke clusters, since the ClusterRole definitions are already deployed. The MRA API handles creating the appropriate RoleBindings on managed clusters automatically.
