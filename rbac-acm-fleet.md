# Proposal: Fine-Grained RBAC Across an ACM-Managed OpenShift Fleet

## Working Title

**Fine-Grained RBAC Across an ACM Fleet: Security Boundaries, Practical Patterns, and Common Pitfalls**

## Summary

Managing access across a fleet of OpenShift clusters is more complex than creating roles and role bindings. With Red Hat Advanced Cluster Management (ACM), authorization can span the management hub, managed-cluster APIs, GitOps controllers, and the services that connect users to workloads.

This article presents a practical approach to designing fine-grained, auditable access control across an ACM-managed fleet, with particular attention to OpenShift Virtualization, application workloads, and observability.

Rather than focusing exclusively on individual RBAC resources, it explains how authorization decisions interact across the hub and managed clusters, how centralized policy distribution affects security boundaries, and how to avoid unintentionally granting broader privileges through controllers and automation.

## Why This Matters

Platform teams need to delegate operational responsibilities without granting unnecessary cluster-wide privileges. A user may need to inspect a virtual machine, manage workloads in a particular namespace, or access monitoring data without receiving broad administrative access to a managed cluster.

Achieving this consistently requires understanding more than Kubernetes RBAC in isolation. Hub-side permissions, managed-cluster roles, identity propagation, policy placement, and GitOps automation can all influence the effective access available to a user or controller.

This article addresses these challenges through concrete implementation patterns, trade-off analysis, and security-focused examples.

## What the Article Covers

- **Authorization architecture:** The distinction between hub-side and managed-cluster authorization, including how user identity and permissions flow through the system.
- **Practical RBAC patterns:** Approaches for delegating access to OpenShift Virtualization, application workloads, and observability resources.
- **Centralized versus decentralized management:** The benefits and risks of managing permissions through ACM policies, managed-cluster configuration, and GitOps workflows.
- **Security boundaries:** How permissions to modify policies, ManifestWorks, role assignments, or GitOps configuration can indirectly enable privileged actions on managed clusters.
- **Validation and troubleshooting:** Practical commands, YAML examples, and diagnostic techniques for investigating authorization failures.
- **Operational recommendations:** A checklist covering least privilege, policy scope, identity management, auditability, and safe rollout.

## What Makes This Article Different

The focus is on the **effective security model**, not merely the syntax of RBAC resources.

A configuration that appears appropriately scoped at the hub may still enable powerful actions on a managed cluster through a controller or policy mechanism. Understanding these indirect privilege paths is essential when designing secure fleet-wide delegation.

The article therefore treats authorization as an end-to-end system: from the identity making a request, through the relevant hub-side controls and automation, to the permissions ultimately enforced by the managed-cluster API.

## Intended Audience

- OpenShift and Kubernetes platform engineers
- ACM and fleet-management administrators
- Platform security and identity engineers
- Teams implementing multi-tenant OpenShift Virtualization environments
- Engineers responsible for GitOps-based cluster configuration and governance

## Format and Deliverables

The article combines architectural explanations with practical examples, including YAML manifests, command-line validation, troubleshooting scenarios, and a security checklist.

Version-dependent features and preview limitations will be clearly identified, with references to the relevant product documentation.

The accompanying GitHub repository will serve as the reference implementation and provide version history for the examples.

## Expected Outcome

Readers should leave with a clearer understanding of how authorization works across an ACM-managed fleet, how to choose an appropriate delegation model, and how to identify privilege-escalation paths before deploying their configuration in production.

The goal is to help platform teams implement access control that is not only functional, but also understandable, auditable, and aligned with the principle of least privilege.
