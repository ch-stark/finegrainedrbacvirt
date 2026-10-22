# OpenShift Virtualization RBAC

Use one `MulticlusterRoleAssignment` per group. Leave `ClusterPermission` to the controller. This page is the short form. The reference is [Fine-Grained RBAC Across an ACM Fleet](rbac-acm-fleet.md), section 6, the Quick start, and appendices A through C.

Role names and the schema below are from the ACM 2.17 fine-grained virtualization documentation. Enable the `fine-grained-rbac` component first. Appendix A of the reference shows the patch. Do not append a second component entry if one is already present.

## Roles

| Who | Hub | Managed cluster |
| --- | --- | --- |
| Viewer | `acm-vm-fleet:view` | `kubevirt.io:view` and `acm-vm-extended:view` |
| VM administrator | `acm-vm-fleet:view` | `kubevirt.io:admin` and `acm-vm-extended:admin` |
| Cross-cluster live migration | `acm-vm-fleet:admin` | `kubevirt.io:admin` and `acm-vm-extended:admin` on the source and the target. The 2.17 virtualization guide also lists `acm-vm-cluster-migration:view` on the target. |

`kubevirt.io:admin` includes `HyperConverged` in `openshift-cnv`. It is not OpenShift `cluster-admin`.

The hub role opens the fleet virtualization console. The managed-cluster roles authorize the API call, as the impersonated user.

## Namespace scope

List `targetNamespaces` when the team should administer one project. The controller creates a `RoleBinding` in each listed namespace. Omit the list when the role should be a `ClusterRoleBinding`.

The list does not grow when someone creates a project. Keep it only if the platform team will update it.

On each role assignment, ACM 2.17 uses `clusterSelection`. The Quick start in the reference is a complete namespace example. Confirm the field on your hub:

```
oc explain multiclusterroleassignment.spec.roleAssignments.clusterSelection
```

The `Placement` must exist first, and it should select only clusters where those ClusterRoles exist.

## Aggregation on OpenShift Virtualization 4.22

`kubevirt.io:view`, `kubevirt.io:edit`, and `kubevirt.io:admin` are aggregated into the default `view`, `edit`, and `admin` roles. A namespace administrator can receive virtualization rights from that aggregation. `kubevirt.io:migrate` is not aggregated. From OpenShift Virtualization 4.19, in-cluster live migration needs an explicit `kubevirt.io:migrate` binding.

## Check

On the spoke, `oc auth can-i get virtualmachines.kubevirt.io -n team-a-vms` as the hub user and group should succeed. The same check in a namespace outside `targetNamespaces` should fail. The spoke audit log for a console click should name the impersonated user.

Section 13 of the reference lists the usual `Forbidden` mismatches.
