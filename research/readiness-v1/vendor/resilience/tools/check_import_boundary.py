"""Fresh-interpreter import-boundary test; no live services or private inputs.

The parent supplies this project's root as the only argument and launches with
``-I -S -B``. This test tool imports core source only, never other project tools,
state, account data, legacy applications, or network/SDK/process modules. Normal
stdlib/core import-loader file reads remain necessary; core IO is checked by AST
in test_boundaries.py. JSON diagnostics contain module names, not absolute paths.
"""
import builtins
import importlib
import json
import sys


CORE_MODULES = ('authorization', 'decision', 'execution', 'exits', 'money',
                'numbers', 'risk', 'temporal')
EXPECTED = frozenset(('faraz_core',) + tuple('faraz_core.' + name for name in CORE_MODULES))
BANNED_ROOTS = frozenset({
    'metatrader5', 'mt5', 'amin_mt5', 'oldapp', 'old_app', 'legacy', 'legacy_engine',
    'socket', '_socket', 'ssl', '_ssl', 'socketserver', 'requests', 'http', 'urllib',
    'urllib3', 'httpx', 'aiohttp', 'ftplib', 'smtplib', 'poplib', 'imaplib',
    'subprocess', 'multiprocessing', 'ctypes', 'win32api', 'keyring', 'webbrowser',
    'tools', 'runpaths', 'run_tests', 'run_offline_demo',
})


class BoundaryViolation(ImportError):
    pass


def main():
    phase = 'INITIALIZATION'
    report = {'success': False}
    try:
        if len(sys.argv) != 2:
            raise BoundaryViolation('PROJECT_ROOT_ARGUMENT_REQUIRED')
        root = sys.argv[1]
        report.update(isolated=bool(sys.flags.isolated), site_disabled=bool(sys.flags.no_site),
                      bytecode_disabled=bool(sys.dont_write_bytecode))
        if not all(report[name] for name in ('isolated', 'site_disabled', 'bytecode_disabled')):
            raise BoundaryViolation('ISOLATED_FRESH_INTERPRETER_REQUIRED')
        preloaded = sorted(name for name in sys.modules
                           if name == 'faraz_core' or name.startswith('faraz_core.'))
        report['preloaded_core_modules'] = preloaded
        if preloaded:
            raise BoundaryViolation('CORE_WAS_ALREADY_CACHED')
        if any(name.split('.')[0].lower() in BANNED_ROOTS for name in sys.modules):
            raise BoundaryViolation('FORBIDDEN_MODULE_ALREADY_CACHED')
        original_import = builtins.__import__
        forbidden_core_attempts = []
        fresh = set()

        def reject(name):
            if name.split('.')[0].lower() in BANNED_ROOTS:
                if phase == 'CORE_IMPORTS':
                    forbidden_core_attempts.append(name)
                raise BoundaryViolation('FORBIDDEN_MODULE')

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            reject(name)
            return original_import(name, globals, locals, fromlist, level)

        class ImportGuard:
            def find_spec(self, fullname, path=None, target=None):
                reject(fullname)
                if fullname == 'faraz_core' or fullname.startswith('faraz_core.'):
                    fresh.add(fullname)
                return None

        finder = ImportGuard()
        builtins.__import__ = guarded_import
        sys.meta_path.insert(0, finder)

        def audit_guard(event, args):
            if event.startswith('socket.') or event in (
                    'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'ctypes.dlopen'):
                if phase == 'CORE_IMPORTS':
                    forbidden_core_attempts.append('AUDIT:' + event)
                raise BoundaryViolation('FORBIDDEN_AUDIT_EVENT')

        sys.addaudithook(audit_guard)
        phase = 'GUARD_SELF_CHECK'
        checks = []
        # Instrument actual forbidden module names without loading those modules.
        # Both import routes must fail before a finder/loader can execute them.
        for name in ('socket', 'MetaTrader5', 'amin_mt5', 'tools.run_offline_demo'):
            for method, loader in (('builtin', guarded_import), ('importlib', importlib.import_module)):
                try:
                    loader(name)
                except BoundaryViolation:
                    checks.append({'module': name, 'method': method, 'blocked': True})
                else:
                    raise BoundaryViolation('IMPORT_GUARD_SELF_CHECK_FAILED')
        report['guard_self_checks'] = checks
        try:
            sys.audit('socket.faraz_test_sentinel')
        except BoundaryViolation:
            report['socket_audit_guard_verified'] = True
        else:
            raise BoundaryViolation('SOCKET_AUDIT_GUARD_SELF_CHECK_FAILED')

        # -I excludes cwd/PYTHONPATH and -S skips site/.pth startup. Only this
        # explicit root is added, after guards and their self-checks are active.
        sys.path.insert(0, root)
        phase = 'CORE_IMPORTS'
        for name in CORE_MODULES:
            importlib.import_module('faraz_core.' + name)
        imported = sorted(name for name in sys.modules
                          if name == 'faraz_core' or name.startswith('faraz_core.'))
        normalized_root = root.replace('\\', '/').rstrip('/').casefold()
        for name in imported:
            suffix = '/faraz_core/__init__.py' if name == 'faraz_core' else '/' + name.replace('.', '/') + '.py'
            origin = (sys.modules[name].__spec__.origin or '').replace('\\', '/').casefold()
            if origin != normalized_root + suffix.casefold():
                raise BoundaryViolation('CORE_ORIGIN_OUTSIDE_KNOWN_PROJECT')
        report.update(imported_core_modules=imported, fresh_core_imports=sorted(fresh),
                      all_core_imports_fresh=fresh == EXPECTED,
                      forbidden_attempts_during_core=forbidden_core_attempts,
                      guard_still_installed=(builtins.__import__ is guarded_import
                                             and sys.meta_path[0] is finder))
        if (set(imported) != EXPECTED or fresh != EXPECTED or forbidden_core_attempts
                or not report['guard_still_installed']):
            raise BoundaryViolation('FRESH_IMPORT_BOUNDARY_NOT_VERIFIED')
        report['success'] = True
    except Exception as error:
        # Avoid publishing argv, user-profile paths, tracebacks, or private data.
        report.update(success=False, failure_phase=phase, failure_type=type(error).__name__)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['success'] is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
