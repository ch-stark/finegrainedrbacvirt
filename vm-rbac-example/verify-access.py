#!/usr/bin/env python3
"""Query explicit authorization attributes for the example VM access tiers."""
import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('context', help='Kubeconfig context for the managed cluster')
parser.add_argument('--hub-only', action='store_true',
                    help='Expect namespace listing from the hub fleet-console role')
parser.add_argument('--results', type=Path, help='Save detailed JSON observations')
args = parser.parse_args()
failures = []
observations = []
for tenant, suffix in [('a', 'operators'), ('b', 'operators'), ('c', 'viewers')]:
    ns = f'tenant-{tenant}-namespace'
    identity = ['--as=rbac-validation', f'--as-group=tenant-{tenant}-{suffix}',
                '--as-group=system:authenticated']

    def check(expected, verb, resource, namespace=None, subresource=None):
        name, _, group = resource.partition('.')
        attributes = {'verb': verb, 'resource': name, 'group': group}
        if namespace:
            attributes['namespace'] = namespace
        if subresource:
            attributes['subresource'] = subresource
        review = {'apiVersion': 'authorization.k8s.io/v1',
                  'kind': 'SelfSubjectAccessReview',
                  'spec': {'resourceAttributes': attributes}}
        cmd = ['oc', '--context', args.context, 'create',
               '--raw=/apis/authorization.k8s.io/v1/selfsubjectaccessreviews',
               '-f', '-'] + identity
        result = subprocess.run(cmd, input=json.dumps(review), text=True,
                                capture_output=True)
        try:
            status = json.loads(result.stdout).get('status', {})
            allowed = status.get('allowed')
        except (json.JSONDecodeError, AttributeError):
            status, allowed = {}, None
        passed = result.returncode == 0 and allowed is (expected == 'yes')
        observation = {'tenant': tenant, 'attributes': attributes,
                       'expectedAllowed': expected == 'yes', 'allowed': allowed,
                       'passed': passed, 'reason': status.get('reason', '')}
        if not passed:
            detail = (result.stderr or result.stdout).strip()
            failures.append(f'{tenant}: {verb} {resource}/{subresource or ""} '
                            f'in {namespace or "cluster scope"}: expected {expected}; '
                            f'allowed={allowed!r}; {detail}')
            observation['error'] = detail
        observations.append(observation)

    for verb in ['get', 'list', 'watch']:
        check('yes', verb, 'virtualmachines.kubevirt.io', ns)
    for verb in ['create', 'update', 'patch']:
        check('yes' if tenant == 'a' else 'no', verb, 'virtualmachines.kubevirt.io', ns)
    for action in ['start', 'stop', 'restart']:
        check('yes' if tenant in 'ab' else 'no', 'update',
              'virtualmachines.subresources.kubevirt.io', ns, action)
    for resource, verb, action in [
        ('virtualmachines.kubevirt.io', 'delete', None),
        ('virtualmachineinstances.subresources.kubevirt.io', 'get', 'console'),
        ('virtualmachineinstances.subresources.kubevirt.io', 'get', 'vnc'),
        ('virtualmachineinstances.subresources.kubevirt.io', 'update', 'pause'),
        ('virtualmachineinstancemigrations.kubevirt.io', 'create', None),
        ('secrets', 'get', None),
        ('rolebindings.rbac.authorization.k8s.io', 'create', None),
    ]:
        check('no', verb, resource, ns, action)
    for other in 'abc':
        if other != tenant:
            check('no', 'list', 'virtualmachines.kubevirt.io', f'tenant-{other}-namespace')
    check('yes' if args.hub_only else 'no', 'list', 'namespaces')

summary = {'context': args.context, 'hubOnly': args.hub_only,
           'checks': len(observations), 'failures': len(failures),
           'observations': observations}
if args.results:
    args.results.write_text(json.dumps(summary, indent=2) + '\n')
if failures:
    print('\n'.join(failures))
    raise SystemExit(f'{len(failures)} of {len(observations)} authorization checks failed')
print(f'PASS: {len(observations)} authorization checks on {args.context}')
