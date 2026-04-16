# Mastering Custom RBAC for Virtualization in ACM: A "Bring Your Own Role" Guide

In the world of cluster management, the default "Admin," "Edit," and "View" roles are often either too permissive or too restrictive. A common request from virtualization users is the ability to create and manage Virtual Machines (VMs) without the permission to delete them. Implementing this granular control within Advanced Cluster Management (ACM) requires a bit of finesse to ensure that the custom permissions propagate correctly across your fleet and integrate seamlessly with the user interface. Here is how to implement a "Bring Your Own Role" (BYOR) strategy for OpenShift Virtualization.

## 1. Defining the Custom Role

To achieve the "create but not delete" workflow, you need a custom ClusterRole. While you might be tempted to define every single permission, the best practice is to focus only on the specific actions you want to allow.

### The "Create-Only" Example

This role allows a user to define, start, and update a VM, but notably lacks the `delete` verb.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kubevirt-user-create
rules:
  # Permission to define and start the VM
- apiGroups: [kubevirt.io]
  resources: [virtualmachines]
  verbs: [get, list, watch, create, update, patch]
```

**Pro Tip:** Always remember that `virtualmachines` (the definition) and `virtualmachineinstances` (the running state) are separate resources. To see the running status or IP address of a VM, the user also needs access to the instances.

## 2. Making Custom Roles "UI-Aware"

One of the biggest hurdles in ACM is getting your custom roles to show up in the **Role Assignment** dropdown menu. The ACM console uses specific filters to decide which roles are relevant to virtualization.

To make your role visible in the UI, you must apply specific labels to the role on the Hub cluster:

- `rbac.open-cluster-management.io/filter: vm-clusterroles` -- This tells the UI that this role is a virtualization-specific role.
- `clusterview.open-cluster-management.io/discoverable: "true"` -- This ensures the search service can index the role for the UI.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kubevirt-user-create
  labels:
    rbac.open-cluster-management.io/filter: vm-clusterroles
    clusterview.open-cluster-management.io/discoverable: "true"
rules:
- apiGroups: [kubevirt.io]
  resources: [virtualmachines]
  verbs: [get, list, watch, create, update, patch]
```

## 3. Distributing Roles Across the Fleet

In a multicluster environment, the Hub cluster acts as the brain, but the permissions must physically exist on the Managed (Spoke) clusters where the VMs actually live.

There are several ways to push these roles down to your clusters, but they are not created equal:

### ACM Policies (Recommended)

This is the most flexible and visible method. You can create a single configuration policy that "stamps" your custom ClusterRole onto every cluster matching a specific label. It is easy to audit and manage at scale.

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: Policy
metadata:
  name: policy-kubevirt-create-role
  namespace: open-cluster-management
spec:
  remediationAction: enforce
  disabled: false
  policy-templates:
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: kubevirt-create-role
        spec:
          remediationAction: enforce
          object-templates:
            - complianceType: musthave
              objectDefinition:
                apiVersion: rbac.authorization.k8s.io/v1
                kind: ClusterRole
                metadata:
                  name: kubevirt-user-create
                rules:
                - apiGroups: [kubevirt.io]
                  resources: [virtualmachines]
                  verbs: [get, list, watch, create, update, patch]
```

### ClusterPermission API

A solid alternative that automatically handles the lifecycle of RBAC resources on managed clusters.

### AddonTemplates

While used internally by engineering teams to ship default roles, it is generally **not recommended** for custom customer implementations due to its complexity and internal-facing nature.

## 4. The "Layered Role" Strategy

The secret to a smooth user experience is **layering**. Instead of trying to build a single role that does everything, you should assign two roles to your users in the ACM UI:

1. **The Standard View Role:** Assign `kubevirt.io:view`. This provides all the "under-the-hood" read permissions required for the OpenShift Virtualization console to function (like viewing nodes, pods, and network attachments).

2. **The Custom Write Role:** Assign your custom `kubevirt-user-create` role. This adds the specific "Create" and "Update" powers on top of the view permissions.

By pairing these, you ensure the UI remains fully functional while strictly enforcing your "no-deletion" policy.

| Component | Role Used | Purpose |
|---|---|---|
| Console Navigation | `acm-vm-fleet:view` | Allows the user to see the Virtualization tab in ACM |
| Resource Visibility | `kubevirt.io:view` | Allows the user to see VM details and statuses |
| Custom Actions | `kubevirt-user-create` | Allows the user to create new VMs without delete rights |

## Final Thoughts

Custom RBAC in ACM doesn't have to be a "black box." By using Configuration Policies for distribution and UI Labels for visibility, you can create a tailored experience that fits your organization's security requirements. Stick to the layered approach -- using the default view roles as a foundation -- to save yourself the headache of troubleshooting missing read permissions.
