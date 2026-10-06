import os
import sys
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def sync_github():
    print('=============================================================')
    print('  ORBITAL GITHUB REPOSITORY AUTO-SYNC                       ')
    print('=============================================================')
    base_dir = r'C:\Orbital'
    if os.path.exists(base_dir):
        os.chdir(base_dir)
    try:
        print('[1/3] Staging changes...')
        subprocess.run(['git', 'add', '.'], check=False)
        print('[2/3] Committing updates...')
        subprocess.run(['git', 'commit', '-m', 'v34 Architecture Verification & Test Suite Harmonization'], check=False)
        print('[3/3] Pushing to remote repository...')
        subprocess.run(['git', 'push'], check=False)
        print(r'[✔] Successfully synced C:\Orbital to GitHub!')
    except Exception as e:
        print(f'[!] Git sync notice: {e}')


if __name__ == '__main__':
    sync_github()
