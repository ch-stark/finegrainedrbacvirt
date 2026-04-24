# Policy-to-UI RBAC Architecture with PolicyGenerator

To implement the "Policy-to-UI" RBAC architecture using the PolicyGenerator, you provide the raw Kubernetes manifests for your ClusterRoles and MultiClusterRoleAssignment (MRA), and use a single PolicyGenerator configuration file to compile them into a unified PolicySet targeted at the correct Hub and Spoke clusters.

---

## 1. Directory Structure

Create a clean separation between the raw manifests intended for the Hub and those intended for the Spoke clusters:

```
vm-rbac-config/
├── kustomization.yaml
├── policy-generator.yaml
├── hub-manifests/
│   ├── 01-hub-clusterrole.yaml
│   └── 02-hub-mra.yaml
└── spoke-manifests/
    └── 01-spoke-clusterrole.yaml
```

## 2. Raw Kubernetes Manifests

These are standard Kubernetes YAML files. The PolicyGenerator will automatically convert them into compliance objects.

### `hub-manifests/01-hub-clusterrole.yaml` — The UI Discovery Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-execution-role
  labels:
    # Mandatory label for RHACM Fleet Management UI discovery
    rbac.open-cluster-management.io/filter: vm-clusterroles
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines", "virtualmachineinstances"]
    verbs: ["get", "list", "watch", "start", "stop", "restart"]
```

### `hub-manifests/02-hub-mra.yaml` — The Fleet Assignment

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
    - custom-vm-execution-role
    - kubevirt.io:view
```

### `spoke-manifests/01-spoke-clusterrole.yaml` — The Remote Execution Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-vm-execution-role # Must match the MRA role name
rules:
  - apiGroups: ["kubevirt.io"]
    resources: ["virtualmachines", "virtualmachineinstances"]
    verbs: ["get", "list", "watch", "start", "stop", "restart"]
```

---

## 3. PolicyGenerator Configuration

The `policy-generator.yaml` defines the Hub policy and the Spoke policy, sets the cluster placements, and logically groups them into a PolicySet.

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
      description: "Deploys Custom VM ClusterRoles and MultiClusterRoleAssignments"
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
      - path: hub-manifests/01-hub-clusterrole.yaml
      - path: hub-manifests/02-hub-mra.yaml

  # --- 2. SPOKE POLICY ---
  - name: policy-spoke-vm-rbac
    placement:
      labelSelector:
        matchExpressions:
          - key: name
            operator: NotIn
            values: ["local-cluster"] # Targets ALL managed clusters EXCEPT the Hub
    manifests:
      - path: spoke-manifests/01-spoke-clusterrole.yaml
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
