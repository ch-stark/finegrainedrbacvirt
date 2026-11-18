# Fine-grained RBAC for virtualization with ACM 5.0

Examples and guidance for governing virtual machine access across managed clusters with Red Hat Advanced Cluster Management for Kubernetes.

## Start here

- [Govern VM access across clusters with ACM 5.0](virtrbacblog_v2.md) — the current walkthrough for namespace-scoped tenant access, policy delivery, verification, and revocation.
- [Tenant-scoped companion example](vm-rbac-example/README.md) — complete manifests, rendered first-stage policies, Argo CD configuration, and authorization checks.
- [Full Admin Fleet Virtualization example](examplefulladmin/README.md) — a separate cluster-wide administrative model. Its default wildcard role grants cluster-admin-equivalent access.

The tenant example starts with assignments disabled. Read its rollout and validation instructions before granting access.

## Additional guides

- [RBAC in ACM: the patterns you need](rbac-acm-fleet.md)
- [Fine-grained RBAC for virtualization](virtrbac.md)
- [Bring Your Own Role guide](customrbac.md)
- [Disabling KubeVirt role aggregation for maximum isolation](disable-role-aggregation.md)

## Related policy samples

[Dynamic fine-grained RBAC policy samples](https://github.com/brian-jarvis/bry-acm-policy-samples/tree/virt-dynamic-rbac/policies/virt-management/finegrained-dynamic-rbac)
