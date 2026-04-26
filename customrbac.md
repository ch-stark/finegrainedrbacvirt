# Mastering Custom RBAC for Virtualization in ACM: A "Bring Your Own Role" Guide

In the world of cluster management, the default "Admin," "Edit," and "View" roles are often either too permissive or too restrictive. A common request from virtualization users is the ability to create and manage Virtual Machines (VMs) without the permission to delete them. Implementing this granular control within Advanced Cluster Management (ACM) requires a bit of finesse to ensure that the custom permissions propagate correctly across your fleet and integrate seamlessly with the user interface. Here is how to implement a "Bring Your Own Role" (BYOR) strategy for OpenShift Virtualization.

To implement a custom role in the ACM 2.16 Fine-Grained RBAC framework, you need to create a specific prerequisite ClusterRoleBinding on the Hub cluster and then define and distribute your custom ClusterRole. Here is the step-by-step process.

## Step 1: Create the Prerequisite Hub ClusterRoleBinding

Before a user can interact with the multicluster Fleet Virtualization console, they must have the prerequisite Hub role. Create a standard ClusterRoleBinding directly on the Hub cluster to grant the user access to the UI.

**Note:** The available Hub roles are `acm-vm-fleet:view` and `acm-vm-fleet:admin`. These are **prerequisite roles for the CNV Fleet Virtualization UI only** -- they do not grant actual VirtualMachine permissions on managed clusters. The `admin` variant adds extra permissions needed by CCLM administrators. For the vast majority of use cases (95%+), `acm-vm-fleet:view` is sufficient. Actual VM create/manage/delete permissions are controlled through the `kubevirt.io:view`, `kubevirt.io:edit`, and `kubevirt.io:admin` roles assigned via MRA in Step 4.

```bash
oc create clusterrolebinding <binding-name> \
  --clusterrole=acm-vm-fleet:view \
  --user=<username>
```

This is a **mandatory prerequisite** -- without this binding, the user will not see the Virtualization tab in the ACM console at all, regardless of any other roles they may have.

## Step 2: Define and Label the Custom Role on the Hub

Define your custom ClusterRole (e.g., `kubevirt-user-create`) on the Hub cluster. This role allows a user to define, start, and update a VM, but notably lacks the `delete` verb.

To ensure this custom role appears in the ACM Fleet Management RBAC UI dropdown, you **must** include the `rbac.open-cluster-management.io/filter: vm-clusterroles` label.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kubevirt-user-create
  labels:
    # This label is strictly required for the role to appear in the ACM RBAC UI dropdown
    rbac.open-cluster-management.io/filter: vm-clusterroles
    clusterview.open-cluster-management.io/discoverable: "true"
rules:
  # Permission to create, update, and patch VMs (no delete)
- apiGroups: [kubevirt.io]
  resources: [virtualmachines]
  verbs: [create, update, patch]
  # Permission to start/stop/restart VMs
- apiGroups: [subresources.kubevirt.io]
  resources: [virtualmachines/start, virtualmachines/stop, virtualmachines/restart]
  verbs: [update]
  # Permission to list namespaces (needed by the console)
- apiGroups: [""]
  resources: [namespaces]
  verbs: [get, list, watch]
```

This is a **minimal role designed to be layered on top of `kubevirt.io:view`** (assigned in Step 4). The `kubevirt.io:view` role already provides read access to VMs, instances, DataVolumes, and other resources. This custom role only adds the write verbs (`create`, `update`, `patch`) that are missing from the view role, deliberately excluding `delete`.

**Optional:** If users also need to create disks as part of the VM creation wizard, you can extend the role with additional rules:

```yaml
  # Optional: Permission to create disks during VM creation
- apiGroups: [cdi.kubevirt.io]
  resources: [datavolumes]
  verbs: [create]
- apiGroups: [""]
  resources: [persistentvolumeclaims]
  verbs: [create]
```

**Pro Tip:** Always remember that `virtualmachines` (the definition) and `virtualmachineinstances` (the running state) are separate resources. The `kubevirt.io:view` role already covers read access to both, so your custom role only needs to add the write permissions you want to grant.

## Step 3: Distribute the Custom Role to Managed Clusters

For Fine-Grained RBAC to work via the ACM Cluster Proxy, the execution role must exist directly on the managed (spoke) clusters. You must push the custom ClusterRole down to your targeted managed clusters.

There are several ways to achieve this, but they are not created equal:

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
                  verbs: [create, update, patch]
                - apiGroups: [subresources.kubevirt.io]
                  resources: [virtualmachines/start, virtualmachines/stop, virtualmachines/restart]
                  verbs: [update]
                - apiGroups: [""]
                  resources: [namespaces]
                  verbs: [get, list, watch]
```

### ClusterPermission API

A solid alternative that automatically handles the lifecycle of RBAC resources on managed clusters.

### AddonTemplates

While used internally by engineering teams to ship default roles, it is generally **not recommended** for custom customer implementations due to its complexity and internal-facing nature.

## Step 4: Bind the Roles Using the ACM UI (MulticlusterRoleAssignment)

The most efficient method is to pair your custom role with the default `kubevirt.io:view` role to minimize the read-only permissions you have to manually manage.

1. In the ACM console, navigate to **Fleet Management -> Identities**.
2. Click on the target user or group and click **Create role assignment**.
3. **Assign the Standard View Role:** Select the desired clusters and namespaces, and assign the default `kubevirt.io:view` role. This securely grants the underlying read-only permissions needed for the UI to display the VMs and instances.
4. **Assign the Custom Create Role:** Repeat the role assignment process for the same clusters and namespaces, but this time select your custom `kubevirt-user-create` role from the dropdown menu.

When applied, the **MulticlusterRoleAssignment (MRA)** API will automatically translate these assignments and push the necessary standard Kubernetes RoleBindings or ClusterRoleBindings down to the selected managed clusters.

### The Layered Role Summary

| Component | Role Used | Purpose |
|---|---|---|
| Console Navigation | `acm-vm-fleet:view` | Allows the user to see the Virtualization tab in ACM (Step 1) |
| Resource Visibility | `kubevirt.io:view` | Allows the user to see VM details and statuses (Step 4) |
| Custom Actions | `kubevirt-user-create` | Allows the user to create new VMs without delete rights (Step 4) |

## Final Thoughts

Custom RBAC in ACM doesn't have to be a "black box." By creating the prerequisite Hub ClusterRoleBinding (Step 1), labeling your custom role for UI visibility (Step 2), distributing it via Configuration Policies (Step 3), and binding roles through the MRA-powered ACM UI (Step 4), you can create a tailored experience that fits your organization's security requirements. Stick to the layered approach -- using `kubevirt.io:view` as a foundation -- to save yourself the headache of troubleshooting missing read permissions.
