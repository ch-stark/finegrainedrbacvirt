# Optional OpenShift Virtualization roles (opt-in)

These ClusterRoles are **not** deployed by the default PolicyGenerator configuration.
Enable the roles your teams need by applying the manifests directly or by uncommenting
the corresponding paths in `policy-generator.yaml`.

All optional roles are designed to be **layered on top of `kubevirt.io:view`**, which
provides baseline read access to VMs, instances, DataVolumes, and related resources.

| Role | Use case | Typical base role |
| --- | --- | --- |
| `custom-vm-execution-role` | Start, stop, restart VMs | `kubevirt.io:view` |
| `custom-vm-admin-role` | Create and update VMs (no delete) | `kubevirt.io:view` |
| `custom-vm-snapshot-role` | Create and restore disk snapshots | `kubevirt.io:view` |
| `custom-vm-migration-role` | In-cluster live migration | `kubevirt.io:view` |
| `custom-vm-storage-role` | Manage DataVolumes, PVCs, hot-plug disks | `kubevirt.io:view` |
| `custom-vm-console-role` | Serial console, VNC, guest OS info | `kubevirt.io:view` |

## Apply manually

```bash
# Hub (UI discovery labels)
oc apply -f hub-manifests/optional/

# Managed clusters (via ACM policy, or apply on each spoke)
oc apply -f spoke-manifests/optional/
```

## Enable via PolicyGenerator

Add the desired manifest paths under the hub and spoke policies in
`policy-generator.yaml`, then re-apply the kustomization.

## Assign to users

Create a `MulticlusterRoleAssignment` pairing the custom role with `kubevirt.io:view`
for the target group, namespace, and clusters. Example for the execution role:

```yaml
apiVersion: rbac.open-cluster-management.io/v1beta1
kind: MulticlusterRoleAssignment
metadata:
  name: example-vm-execution-assignment
  namespace: open-cluster-management-global-set
spec:
  subject:
    kind: Group
    name: vm-operators
    apiGroup: rbac.authorization.k8s.io
  roleAssignments:
    - name: kubevirt-view
      clusterRole: kubevirt.io:view
      targetNamespaces:
        - my-vm-namespace
      clusterSelection:
        type: placements
        placements:
          - name: all-clusters
            namespace: open-cluster-management-global-set
    - name: custom-vm-execution
      clusterRole: custom-vm-execution-role
      targetNamespaces:
        - my-vm-namespace
      clusterSelection:
        type: placements
        placements:
          - name: all-clusters
            namespace: open-cluster-management-global-set
```

Hub console prerequisite for all fleet virtualization users:

```bash
oc create clusterrolebinding vm-operators-fleet-view \
  --clusterrole=acm-vm-fleet:view \
  --group=vm-operators
```
