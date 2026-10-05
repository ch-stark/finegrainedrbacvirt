# Demo: deploy this PolicySet with OpenShift GitOps

This walkthrough installs the Policy Generator into the hub's OpenShift GitOps (Argo CD) instance, then lets Argo CD generate and sync `virt-fine-grained-rbac` from Git.

Argo CD does not understand a `PolicyGenerator` manifest on its own. The community policy below adds the generator binary to the `openshift-gitops` Argo CD instance and grants the application controller permission to create `Policy`, `PolicySet`, `Placement`, and `PlacementBinding` objects.

```text
https://raw.githubusercontent.com/open-cluster-management-io/policy-collection/refs/heads/main/community/CM-Configuration-Management/policy-openshift-gitops-policygenerator.yaml
```

That policy is published as `remediationAction: inform`. This demo places it on the hub and sets it to `enforce`, so the `openshift-gitops` Argo CD object is actually updated.

## What you will have at the end

- OpenShift GitOps on the hub, with `kustomizeBuildOptions: --enable-alpha-plugins`.
- An Argo CD `Application` named `virt-fine-grained-rbac` tracking this directory.
- PolicySet `virt-fine-grained-rbac` in the `policies` namespace, enforced on the hub.
- Assignment policies present and disabled, until you edit the groups and turn them on.

## Before you start

- `oc` is logged in to an ACM 2.16+ hub, and the hub manages itself (`local-cluster=true`).
- The hub is in the `default` `ManagedClusterSet`. If it is not, change `clusterSet` in `input/bootstrap/namespace.yaml` before the Application syncs.
- OpenShift Virtualization is installed on the hub and on the clusters you will label `acm.io/virtualization=true`.
- This directory is on the branch Argo CD will read. The commands below use `https://github.com/ch-stark/policy-collection` and `main`. Change `GIT_REPO` and `GIT_REVISION` if you are demonstrating a different fork or branch.

```bash
export GIT_REPO=https://github.com/ch-stark/policy-collection.git
export GIT_REVISION=main
```

## 1. Install OpenShift GitOps

The Policy Generator policy patches an Argo CD instance that the GitOps operator has already created. Install the operator with the companion policy, placed on the hub.

```bash
oc create namespace policies --dry-run=client -o yaml | oc apply -f -

oc apply -n policies -f https://raw.githubusercontent.com/open-cluster-management-io/policy-collection/refs/heads/main/community/CM-Configuration-Management/policy-openshift-gitops.yaml
```

```bash
oc apply -n policies -f - <<'EOF'
apiVersion: cluster.open-cluster-management.io/v1beta2
kind: ManagedClusterSetBinding
metadata:
  name: default
  namespace: policies
spec:
  clusterSet: default
---
apiVersion: cluster.open-cluster-management.io/v1beta1
kind: Placement
metadata:
  name: placement-openshift-gitops-installed
  namespace: policies
spec:
  predicates:
    - requiredClusterSelector:
        labelSelector:
          matchExpressions:
            - key: local-cluster
              operator: In
              values:
                - "true"
---
apiVersion: policy.open-cluster-management.io/v1
kind: PlacementBinding
metadata:
  name: binding-openshift-gitops-installed
  namespace: policies
placementRef:
  name: placement-openshift-gitops-installed
  apiGroup: cluster.open-cluster-management.io
  kind: Placement
subjects:
  - name: openshift-gitops-installed
    apiGroup: policy.open-cluster-management.io
    kind: Policy
EOF
```

Wait until the operator policy is compliant and the GitOps server is up:

```bash
oc -n policies get policy openshift-gitops-installed
oc -n openshift-gitops rollout status deployment openshift-gitops-server
```

Skip this step if OpenShift GitOps is already installed and `oc -n openshift-gitops get argocd openshift-gitops` returns the instance.

## 2. Configure Argo CD with the Policy Generator

Apply the policy from `main` of `open-cluster-management-io/policy-collection`, bind it to the hub, and enforce it.

```bash
oc apply -n policies -f https://raw.githubusercontent.com/open-cluster-management-io/policy-collection/refs/heads/main/community/CM-Configuration-Management/policy-openshift-gitops-policygenerator.yaml

oc -n policies patch policy openshift-gitops-policygenerator --type merge \
  -p '{"spec":{"remediationAction":"enforce"}}'
```

```bash
oc apply -n policies -f - <<'EOF'
apiVersion: cluster.open-cluster-management.io/v1beta1
kind: Placement
metadata:
  name: placement-openshift-gitops-policygenerator
  namespace: policies
spec:
  predicates:
    - requiredClusterSelector:
        labelSelector:
          matchExpressions:
            - key: local-cluster
              operator: In
              values:
                - "true"
---
apiVersion: policy.open-cluster-management.io/v1
kind: PlacementBinding
metadata:
  name: binding-openshift-gitops-policygenerator
  namespace: policies
placementRef:
  name: placement-openshift-gitops-policygenerator
  apiGroup: cluster.open-cluster-management.io
  kind: Placement
subjects:
  - name: openshift-gitops-policygenerator
    apiGroup: policy.open-cluster-management.io
    kind: Policy
EOF
```

The policy resolves the generator image from the `acm-cli-downloads` deployment in `open-cluster-management`, extracts `PolicyGenerator` into the repo server, and sets `kustomizeBuildOptions` to `--enable-alpha-plugins`. It also creates `ClusterRole` `openshift-gitops-policy-admin` and binds it to `openshift-gitops-argocd-application-controller`.

Wait until the policy is compliant and the repo server has rolled out:

```bash
oc -n policies get policy openshift-gitops-policygenerator
oc -n openshift-gitops get argocd openshift-gitops -o jsonpath='{.spec.kustomizeBuildOptions}{"\n"}'
oc -n openshift-gitops rollout status deployment openshift-gitops-repo-server
```

The build options line should be `--enable-alpha-plugins`.

This PolicySet's kustomization also applies a `Namespace` and a `ManagedClusterSetBinding`. Those are outside the policy admin role. Grant the application controller those two types before the Application syncs:

```bash
oc apply -f - <<'EOF'
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: openshift-gitops-policyset-bootstrap
rules:
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list", "watch", "create", "update", "patch"]
  - apiGroups: ["cluster.open-cluster-management.io"]
    resources: ["managedclustersetbindings"]
    verbs: ["get", "list", "watch", "create", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: openshift-gitops-policyset-bootstrap
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: openshift-gitops-policyset-bootstrap
subjects:
  - kind: ServiceAccount
    name: openshift-gitops-argocd-application-controller
    namespace: openshift-gitops
EOF
```

## 3. Sync this PolicySet

`kustomization.yml` lists `policyGenerator.yaml` as a generator. Argo CD builds that path with the plugin installed in the previous step. Do not point the Application at a raw directory of Kubernetes manifests; the generator input is not valid to apply by itself.

```bash
oc apply -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: virt-fine-grained-rbac
  namespace: openshift-gitops
spec:
  project: default
  source:
    repoURL: ${GIT_REPO}
    targetRevision: ${GIT_REVISION}
    path: policygenerator/policy-sets/community/virt-fine-grained-rbac
  destination:
    server: https://kubernetes.default.svc
    namespace: policies
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF
```

Watch the Application until it is Synced and Healthy:

```bash
oc -n openshift-gitops get application virt-fine-grained-rbac
```

In the OpenShift console, open **Applications** on the `openshift-gitops` Argo CD instance. `virt-fine-grained-rbac` should show the generated `Policy`, `PolicySet`, `Placement`, and `PlacementBinding` resources. Status fields that the governance controllers write back are ignored on compare because the kustomization sets `argocd.argoproj.io/compare-options: IgnoreExtraneous`.

## 4. Show the result on the hub

```bash
oc -n policies get policyset virt-fine-grained-rbac
oc -n policies get policy
oc -n policies get placement,placementbinding
oc get clusterrole custom-vm-execution-role custom-vm-admin-role custom-vm-snapshot-role \
  custom-vm-migration-role custom-vm-storage-role custom-vm-console-role
```

On a first sync you should see these policies. The four assignment policies stay **disabled**.

| Policy | What to point at in the demo |
| --- | --- |
| `policy-virt-fine-grained-rbac-enable` | `fine-grained-rbac` enabled on `MultiClusterHub` |
| `policy-virt-custom-roles` | six custom `ClusterRole` objects on the hub, with the Fleet Management labels |
| `policy-virt-hub-lookup-rbac` | ServiceAccount `policy-virt-hub-clusterroles` |
| `policy-virt-clusters-placement` | Placement `virt-clusters`, selector `acm.io/virtualization=true` |
| `policy-virt-custom-roles-propagate` | copies those labeled hub roles onto OpenShift managed clusters |
| `policy-virt-assign-view`, `policy-virt-assign-admin`, `policy-virt-assign-cclm`, `policy-virt-assign-custom-execution` | disabled until the group names are edited |

`policy-virt-clusters-placement` is compliant even when it selects no clusters. The propagate policy has nothing to copy onto until a managed cluster is labeled.

## 5. Select a virt cluster

```bash
oc label managedcluster <cluster-name> acm.io/virtualization=true --overwrite
oc -n policies get placementdecision -l cluster.open-cluster-management.io/placement=virt-clusters
```

After the decision lists the cluster, `policy-virt-custom-roles-propagate` creates the same custom `ClusterRole` objects there. Default `kubevirt.io:*` and `acm-vm-*` roles are installed by OpenShift Virtualization and by the fine-grained RBAC component. This PolicySet does not recreate them.

## 6. Optional: enable one assignment

Leave this for a second scene. Edit the group in Git, push to `GIT_REVISION`, and Argo CD syncs the change.

1. In `input/assignments/view.yaml`, replace `virt-viewers` with a group that exists on the hub and on the labeled clusters.
2. In `policyGenerator.yaml`, set `disabled: false` on `policy-virt-assign-view`.
3. Commit and push.

`team-vms` must already exist on the selected clusters. A missing `kubevirt.io:view` on a selected cluster makes that binding fail.

## Clean up

The Application is set to `prune: false`, so deleting it leaves the generated policies in place.

```bash
oc -n openshift-gitops delete application virt-fine-grained-rbac
oc -n policies delete policyset virt-fine-grained-rbac
oc -n policies delete policy -l open-cluster-management.io/policy-set=virt-fine-grained-rbac
```

To remove the GitOps configuration as well:

```bash
oc -n policies patch policy openshift-gitops-policygenerator --type merge \
  -p '{"spec":{"remediationAction":"inform"}}'
oc -n policies delete policy openshift-gitops-policygenerator openshift-gitops-installed
oc -n policies delete placementbinding binding-openshift-gitops-policygenerator binding-openshift-gitops-installed
oc -n policies delete placement placement-openshift-gitops-policygenerator placement-openshift-gitops-installed
oc delete clusterrolebinding openshift-gitops-policyset-bootstrap
oc delete clusterrole openshift-gitops-policyset-bootstrap
```

Inform on `openshift-gitops-policygenerator` stops enforcement. It does not revert the Argo CD plugin settings that were already applied. Remove those from the `openshift-gitops` Argo CD instance if the cluster should go back to stock GitOps.
