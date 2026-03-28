# Demystifying Fine-Grained RBAC for Virtualization in ACM 2.16

Red Hat Advanced Cluster Management (ACM) 2.16 introduces a pivotal shift in **Fleet Virtualization**. It moves away from broad, Hub-centric authorization toward a strict, Spoke-centric model. This ensures that your virtualization administrators have exactly the power they need—and not a shred more—aligning perfectly with the principle of **least privilege**.

---

## The Architecture: How Fine-Grained RBAC Works

The transition to fine-grained control relies on a "Declare Once, Apply Everywhere" philosophy. This is managed through two primary layers: the policy engine and the identity proxy.

### 1. The Policy Engine: MulticlusterRoleAssignment (MRA)
The **MulticlusterRoleAssignment (MRA) API** is the brain of the operation. Instead of manually touching dozens of individual clusters, an admin creates one declarative MRA resource on the ACM Hub. 

The Hub then uses the **ClusterPermission API** to "push" the necessary permissions down to the managed clusters as standard Kubernetes resources:
* **RoleBinding:** For granular, namespace-scoped access.
* **ClusterRoleBinding:** For broad, cluster-wide access.



### 2. The Access Layer: The Proxy Workflow
When a user interacts with a Virtual Machine (VM) in the ACM console, they aren't just looking at a static report; they are interacting with a live resource on a remote cluster. 

1. **The Request:** User clicks "Start VM" or "Console" on the Hub UI.
2. **The Broker:** The **ACM Cluster Proxy** securely carries the user’s identity context to the managed cluster.
3. **The Enforcement:** The managed cluster’s local API evaluates that identity against the **RoleBindings** pushed down by the MRA.

> [!IMPORTANT]
> **Identity is Key:** For this to work, the ACM Hub and all managed clusters must use **identical Identity Providers (IdPs)**. If the user strings don't match exactly across the fleet, the proxy evaluation will fail.

---

## What’s New in ACM 2.16?

The 2.16 release focuses on making these complex "Spoke-centric" permissions easier to manage through a refined user interface.

* **Streamlined Role Assignment:** A completely overhauled UI modal makes it intuitive to map users to roles.
* **Cluster Set Scaling:** You can now apply an MRA to an entire **Cluster Set** at once. If you add a new cluster to that set later, it automatically inherits the correct RBAC.
* **The "Common Project" Shortcut:** Admins can define a namespace (e.g., `dev-app-vms`) that exists across multiple clusters and grant access to it in a single click.

---

## Understanding the Roles: Hub vs. Managed

In ACM 2.16, roles are split between those that live on the **Hub** (to let you see the UI) and those that live on the **Managed Clusters** (to let you do the work).

### Standard Virtualization Roles (Applied to Managed Clusters)
These are the core OpenShift Virtualization roles that determine what a user can do to a VM:
* **`kubevirt.io:view`**: Read-only access to VM resources.
* **`kubevirt.io:edit`**: Create, edit, and delete VMs.
* **`kubevirt.io:admin`**: Full control, including the HyperConverged operator configuration.

### ACM Fleet Extension Roles
These roles act as the "connective tissue" between the Hub and the Spokes:

| Role Name | Location | Purpose |
| :--- | :--- | :--- |
| **`acm-vm-fleet:view`** | **Hub** | **Required.** Allows the user to see the "Virtualization" menu and VM list in the ACM console. |
| **`acm-vm-fleet:admin`** | **Hub** | **Required for Power Users.** Allows cross-cluster migrations and fleet-wide admin tasks. |
| **`acm-vm-extended:view`**| **Managed** | Provides extra metadata for troubleshooting specific to the ACM console view. |
| **`acm-vm-cluster-migration:view`** | **Managed** | Required on both source and destination clusters to validate if a VM is ready to move. |

---

## Pro-Tip: Navigating "Brownfield" Transitions

If you are upgrading to 2.16 from an older version, watch out for "Ghost Permissions."

> [!CAUTION]
> If a user has a legacy `cluster-reader` role on the Hub, they might see a list of all VMs in the search results. However, because they lack the specific **MRA-pushed roles** on the managed clusters, they will get an **"Access Denied"** error the moment they try to click on a VM.

### The Migration Path:
1. **Sunset the "Big" Roles:** Remove broad cluster-wide permissions from the Hub.
2. **Assign the Hub Prerequisite:** Give users `acm-vm-fleet:view` on the Hub so they can see the dashboard.
3. **Deploy MRAs:** Use the MRA API to grant specific access (like `kubevirt.io:edit`) only on the clusters where that user actually has workloads.
