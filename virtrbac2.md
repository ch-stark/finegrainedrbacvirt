# Demystifying Fine-Grained RBAC for Virtualization in ACM 2.16

Red Hat Advanced Cluster Management (ACM) 2.16 supports fine-grained role-based access control (RBAC) specifically tailored for OpenShift Virtualization workloads. This introduces a pivotal shift in fleet virtualization, allowing administrators to grant users the exact privileges needed to view, manage, or migrate virtual machines at both the namespace and cluster levels across managed clusters.

By fully embracing this Spoke-centric approach, your virtualization administrators are granted exactly the power they need—aligning perfectly with the principle of **least privilege**.

---

## The Architecture: How Fine-Grained RBAC Works

The transition to fine-grained control relies on a declarative philosophy managed through two primary mechanisms:

### 1. The Policy Engine: MulticlusterRoleAssignment (MRA)
The **MulticlusterRoleAssignment (MRA)** API provides a declarative method for defining RBAC across a multicluster environment. Instead of manually configuring dozens of individual clusters, an administrator creates a centralized MRA definition on the Hub cluster. 

When the MRA is applied, the system automatically creates the corresponding standard Kubernetes RBAC bindings—either a `RoleBinding` (for namespace-scoped access) or a `ClusterRoleBinding` (for cluster-scoped access)—on the selected managed clusters.

### 2. The Access Layer: The Proxy Workflow
When a user interacts with a Virtual Machine (VM) in the ACM console, they are connecting to a live resource on a remote cluster. 
1. **The Fleet View:** The high-level tree view and VM summary pages retrieve data from **ACM Search**.
2. **The Request & Proxy:** When you click on a specific VM to view details or initiate an action, the request uses the **ACM Cluster Proxy** to securely tunnel to the spoke cluster.
3. **The Enforcement:** The proxy checks your identity against the RBAC bindings residing directly on that spoke cluster. 

> [!IMPORTANT]
> **Strict Prerequisites:** For fine-grained RBAC to function, the ACM Hub and all managed clusters must be configured with **identical identities** (users, groups, and group memberships). This ensures that an identity authenticated on the hub cluster maps correctly to the same identity on the managed clusters. Additionally, the Hub must be self-managed, and the OpenShift Virtualization operator must be installed on the Hub and any targeted managed clusters.

---

## Understanding the Roles: Core vs. Extensions

In ACM 2.16, permissions are constructed using a combination of standard OpenShift Virtualization roles and specialized ACM extension roles. 

### Standard Virtualization Roles (Installed by the Operator)
These roles are installed automatically with the virtualization operator to grant core VM permissions:
* **`kubevirt.io:view`**: Grants read-only access to view all OpenShift Virtualization resources in your cluster
* **`kubevirt.io:edit`**: Grants permissions to create, view, edit, and delete OpenShift Virtualization resources.
* **`kubevirt.io:admin`**: Grants full permissions to resources, including access to the `HyperConverged` custom resource in the `openshift-cnv` namespace.

### Fine-Grained ACM Roles
ACM provides specialized roles to provide specific access levels within the multicluster fleet virtualization interface:

| Role Name | Description |
| :--- | :--- |
| **`acm-vm-fleet:view`** | A prerequisite role applied to the Hub that provides the permissions required to view the fleet virtualization console. |
| **`acm-vm-fleet:admin`** | A prerequisite role applied to the Hub granting permissions to view the console and perform cross-cluster live migrations and related tasks. |
| **`acm-vm-extended:view`**| Extends the default `kubevirt.io` roles on the managed cluster. Grants permissions to view configurations, status, and details in the console, and enables read-only troubleshooting [14, 15]. |
| **`acm-vm-extended:admin`**| Extends the default `kubevirt.io` roles on the managed cluster. Grants administrative permissions to troubleshoot and complete configuration tasks in the console. |
| **`acm-vm-cluster-migration:view`** | Grants the permissions required for cross-cluster live migration readiness checks between source and destination clusters. |

---

## Real-World Scenarios: Applying the Roles

The Red Hat documentation provides specific blueprints for assigning these roles based on your management requirements. Using the MRA API, you can push these exact matrices down to your clusters.

### Scenario 1: Least Privilege Console Visibility
Grant a user or group the absolute minimum permissions required to view virtual machines in the fleet virtualization console.
* **Hub Cluster (`ClusterRoleBinding`):** `acm-vm-fleet:view`.
* **Managed Cluster (`RoleBinding`):** `kubevirt.io:view`.

### Scenario 2: Administrative Privilege 
Grant a user or group the permissions required to view, troubleshoot, and manage virtual machine resources [17-19].
* **Hub Cluster (`ClusterRoleBinding`):** `acm-vm-fleet:view`.
* **Managed Cluster (`RoleBinding`):** `kubevirt.io:admin` and `acm-vm-extended:admin`.

### Scenario 3: Cross-Cluster Live Migration
Grant the permissions required to perform live migrations of virtual machines across cluster boundaries . Note that permissions must be applied to both the origin and target clusters.
* **Hub Cluster (`ClusterRoleBinding`):** `acm-vm-fleet:admin` .
* **Source & Destination Clusters (`RoleBinding`):** `kubevirt.io:admin` and `acm-vm-extended:admin`.
* **Source & Destination Clusters (`ClusterRoleBinding`):** `acm-vm-cluster-migration:view` (Required for readiness checks).

---

## Pro-Tip: Navigating "Brownfield" Transitions and Ghost Permissions

If you are transitioning to ACM 2.16 Fine-Grained RBAC from older "Historical ACM RBAC" models, you must be careful of mixed permissions. 

> [!CAUTION]
> **The "Access Denied" Illusion:** If a user has a broad historical role on the Hub (such as `cluster-reader` or `cluster-admin`), they will see a summary of all VMs across the fleet. However, because they lack the specific fine-grained bindings on the spoke clusters, they will abruptly hit an **"Access Denied"** error when they click on a specific VM.

**Why does this happen?**
Historical RBAC relies purely on Hub-side permissions, granting broad visibility into the indexed **ACM Search** database. However, Fine-Grained RBAC utilizes the **ACM Cluster Proxy** to evaluate actual permissions directly on the spoke cluster. 

To fully utilize Fine-Grained RBAC and enforce the principle of least privilege, you should replace broad Hub read permissions with the specialized `acm-vm-fleet:view` Hub role, and rely entirely on the MRA API to distribute access strictly to the namespaces where the user needs it.
