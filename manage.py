#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    # Jika Django belum ada di sys.path, otomatis panggil venv lokal proyek
    try:
        from django.core.management import execute_from_command_line
        # Atur default port & host runserver agar bisa diakses dari jaringan lokal (HP / perangkat lain)
        from django.core.management.commands.runserver import Command as runserver_command
        runserver_command.default_port = os.environ.get('PORT', os.environ.get('DJANGO_PORT', '8080'))
        runserver_command.default_addr = os.environ.get('DJANGO_HOST', '0.0.0.0')
    except ImportError as exc:
        import subprocess
        base_dir = Path(__file__).resolve().parent
        candidate_paths = [
            base_dir / '.venv' / 'Scripts' / 'python.exe',
            base_dir / 'venv' / 'Scripts' / 'python.exe',
            base_dir / '.venv' / 'bin' / 'python',
            base_dir / 'venv' / 'bin' / 'python',
        ]
        for venv_python in candidate_paths:
            if venv_python.is_file() and sys.executable.lower() != str(venv_python).lower():
                sys.exit(subprocess.call([str(venv_python)] + sys.argv))
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
