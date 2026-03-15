# Demystifying Fine-Grained RBAC for Virtualization in ACM 2.16

Red Hat Advanced Cluster Management (ACM) 2.16 brings crucial enhancements to the **Fleet Virtualization** experience, fundamentally shifting how administrators govern access to virtual machines across distributed environments.

By fully embracing **Fine-Grained Role-Based Access Control (RBAC)**, ACM transitions from a broad, Hub-centric authorization model to a strict, Spoke-centric approach that perfectly aligns with the principle of **least privilege**.

---

## The Core Mechanism: MulticlusterRoleAssignment (MRA)

The backbone of this fine-grained access is the **MulticlusterRoleAssignment (MRA) API**. Instead of manually configuring permissions on dozens of individual clusters, administrators create a single declarative MRA custom resource on the ACM Hub.

Once created, the underlying operator utilizes the **ClusterPermission API** to automatically generate and distribute standard Kubernetes resources down to the targeted managed clusters:

* **RoleBinding:** Used for namespace-scoped access.
* **ClusterRoleBinding:** Used for cluster-wide access.

---

## The Access Layer: How Users Interact

When a user accesses the Fleet Virtualization UI on the Hub cluster, they are looking at aggregated data. However, interacting with a specific Virtual Machine triggers a specific workflow:

1.  **The Request:** The user clicks to view or manage a VM.
2.  **The Cluster Proxy:** The request is routed through the **ACM Cluster Proxy**, which securely brokers the authenticated user's identity context to the managed (spoke) cluster.
3.  **The Evaluation:** The managed cluster's local Kubernetes API receives the proxy request and evaluates the user's identity string against the **RoleBindings** that ACM just pushed down.

> [!IMPORTANT]
> **Crucial Prerequisite:** For this proxy evaluation to succeed, the ACM Hub and all managed clusters must be configured with **identical Identity Providers (IdPs)** so that the user and group strings match perfectly.

---

## What is New in ACM 2.16?

The 2.16 release dramatically improves the user experience for managing these complex bindings:

* **Redesigned UI:** The role assignment modal in the ACM console has been completely overhauled for better usability.
* **Cluster Set Assignments:** Administrators can now easily apply MRA bindings to entire **Cluster Sets** directly from the UI, rather than selecting clusters individually.
* **Common Projects:** The new UI allows administrators to define a **"common project"** (namespace) across multiple clusters. This grants a user access to a specific namespace (e.g., `dev-project`) across the entire selected fleet in a single action.

---

## Role Definitions in ACM 2.16

In ACM 2.16, the default roles for managing OpenShift Virtualization (CNV) workloads are divided into standard virtualization roles and ACM-specific fine-grained extension roles.

### Standard OpenShift Virtualization Roles
These roles are installed automatically with the OpenShift Virtualization operator to grant core permissions on a cluster:

* **`kubevirt.io:view`**: Grants read-only access to view all Red Hat OpenShift Virtualization resources in your cluster.
* **`kubevirt.io:edit`**: Grants permissions to create, view, edit, and delete Red Hat OpenShift Virtualization resources in your cluster.
* **`kubevirt.io:admin`**: Grants permissions to create, view, edit, and delete virtualization resources, as well as access the HyperConverged custom resource in the `openshift-cnv` namespace.

### ACM-Specific Virtualization Roles
ACM extends the default CNV roles to provide specific access levels within the multicluster fleet virtualization interface. Depending on documentation context, these use either the `acm-vm-*` or `kubevirt.io-acm-*` naming convention:

| Role Name | Description |
| :--- | :--- |
| **`acm-vm-fleet:view`** | **Hub Prerequisite.** (aka `kubevirt.io-acm-hub:view`) Grants necessary permissions to view virtual machines in the multicluster fleet virtualization console. |
| **`acm-vm-fleet:admin`** | **Hub Prerequisite.** (aka `kubevirt.io-acm-hub:admin`) Grants permissions to view the console, perform cross-cluster live migrations, and execute administrative tasks. |
| **`acm-vm-extended:view`** | **Managed Extension.** (aka `kubevirt.io-acm-managed:view`) Grants extra view-only privileges to monitor VM operations and troubleshooting in the fleet console. |
| **`acm-vm-extended:admin`** | **Managed Extension.** (aka `kubevirt.io-acm-managed:admin`) Grants administrative permissions to troubleshoot and complete advanced configuration tasks. |
| **`acm-vm-cluster-migration:view`**| Grants permissions required to perform cross-cluster live migration readiness checks between source and destination clusters. |

---

## What to consider for "Brownfield" Environments

If you are transitioning to ACM 2.16 from older, single cluster RBAC models, beware of mixing permissions.

> [!CAUTION]
> If a user retains broad **Historical RBAC** roles on the Hub (such as `cluster-reader`), they will see all VMs across the fleet in the search-based summary views, but will abruptly hit an **"Access Denied"** error when drilling down into a specific VM.

### How to fully utilize Fine-Grained RBAC:

1.  **Drop broad Hub roles:** Remove the legacy cluster-wide permissions.
2.  **Assign the prerequisite role:** Give users the narrow `acm-vm-fleet:view` role on the Hub.
3.  **Use MRA:** Rely entirely on the MRA API to push specific workload roles (like `kubevirt.io:admin`) down to the downstream clusters.
