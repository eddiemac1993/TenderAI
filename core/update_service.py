import subprocess

from django.conf import settings
from django.core.cache import cache


UPDATE_CACHE_KEY = 'tenderai_update_status'
UPDATE_CACHE_SECONDS = 15 * 60


def web_updates_enabled():
    return settings.DEBUG


def run_command(args, timeout=30):
    result = subprocess.run(
        args,
        cwd=settings.BASE_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git_value(args, default=''):
    code, stdout, _ = run_command(args, timeout=10)
    if code != 0:
        return default
    return stdout.strip()


def get_update_status(force_fetch=False):
    if not web_updates_enabled():
        return {'enabled': False, 'available': False, 'message': 'Web updates are only enabled locally.'}

    if not force_fetch:
        cached = cache.get(UPDATE_CACHE_KEY)
        if cached:
            return cached

    status = {
        'enabled': True,
        'available': False,
        'behind': 0,
        'ahead': 0,
        'branch': '',
        'upstream': '',
        'dirty': False,
        'message': '',
    }

    inside = git_value(['git', 'rev-parse', '--is-inside-work-tree'])
    if inside != 'true':
        status['message'] = 'This folder is not a Git repository.'
        cache.set(UPDATE_CACHE_KEY, status, UPDATE_CACHE_SECONDS)
        return status

    status['branch'] = git_value(['git', 'branch', '--show-current'], 'main')
    status['upstream'] = git_value(['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], 'origin/main')

    if force_fetch:
        code, _, stderr = run_command(['git', 'fetch', '--quiet', 'origin'], timeout=60)
        if code != 0:
            status['message'] = stderr or 'Could not check GitHub for updates.'
            cache.set(UPDATE_CACHE_KEY, status, UPDATE_CACHE_SECONDS)
            return status

    behind = git_value(['git', 'rev-list', '--count', f'HEAD..{status["upstream"]}'], '0')
    ahead = git_value(['git', 'rev-list', '--count', f'{status["upstream"]}..HEAD'], '0')
    status['behind'] = int(behind or 0)
    status['ahead'] = int(ahead or 0)
    status['available'] = status['behind'] > 0

    tracked_changes = git_value(['git', 'status', '--porcelain', '--untracked-files=no'])
    status['dirty'] = bool(tracked_changes.strip())
    if status['available']:
        status['message'] = f'{status["behind"]} update(s) available from GitHub.'
    else:
        status['message'] = 'TenderAI is up to date.'

    cache.set(UPDATE_CACHE_KEY, status, UPDATE_CACHE_SECONDS)
    return status


def run_safe_update():
    status = get_update_status(force_fetch=True)
    if not status.get('enabled'):
        return False, status['message']
    if status.get('dirty'):
        return False, 'Update stopped because local code files have changes. Your data is safe, but commit or stash code changes first.'
    if not status.get('available'):
        return True, 'TenderAI is already up to date.'

    steps = [
        (['git', 'pull', '--ff-only'], 120),
        (['python', '-m', 'pip', 'install', '-r', 'requirements.txt'], 300),
        (['python', 'manage.py', 'migrate'], 300),
        (['python', 'manage.py', 'collectstatic', '--noinput'], 300),
    ]
    output = []
    for args, timeout in steps:
        code, stdout, stderr = run_command(args, timeout=timeout)
        output.append(f'> {" ".join(args)}')
        if stdout:
            output.append(stdout)
        if stderr:
            output.append(stderr)
        if code != 0:
            cache.delete(UPDATE_CACHE_KEY)
            return False, '\n'.join(output)

    cache.delete(UPDATE_CACHE_KEY)
    return True, '\n'.join(output)
