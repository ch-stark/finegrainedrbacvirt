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
  | oc apply -f -
```
To deploy the same set from Git with OpenShift GitOps, follow [demo.md](./demo.md).
`policy-virt-custom-roles-propagate` sets `hubTemplateOptions.serviceAccountName` to `policy-virt-hub-clusterroles` so the hub lookup runs as that ServiceAccount.
## Adding another custom role
