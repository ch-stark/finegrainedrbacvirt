#!/usr/bin/env python3
"""Run with an administrator context: python3 verify-access.py MANAGED_CONTEXT."""
import subprocess
import sys
if len(sys.argv) != 2:
    sys.exit(__doc__)
ctx = sys.argv[1]
failures = []
count = 0
for tenant, suffix in [('a', 'operators'), ('b', 'operators'), ('c', 'viewers')]:
    ns = f'tenant-{tenant}-namespace'
    identity = ['--as=rbac-validation', f'--as-group=tenant-{tenant}-{suffix}',
                '--as-group=system:authenticated']
    def check(expected, verb, resource, namespace=None, subresource=None):
        global count
        cmd = ['oc', '--context', ctx, 'auth', 'can-i', verb, resource] + identity
        if namespace:
            cmd += ['--namespace', namespace]
        if subresource:
            cmd += ['--subresource', subresource]
        result = subprocess.run(cmd, text=True, capture_output=True)
        answer = result.stdout.strip()
        count += 1
        if answer != expected or result.returncode != (0 if expected == 'yes' else 1):
            failures.append(f'{tenant}: {verb} {resource}/{subresource or ""} '
                            f'in {namespace or "cluster scope"}: expected {expected}; '
                            f'got {answer!r}; {result.stderr.strip()}')
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
    check('no', 'list', 'namespaces')
if failures:
    print('\n'.join(failures))
    sys.exit(f'{len(failures)} of {count} authorization checks failed')
print(f'PASS: {count} authorization checks on {ctx}')
