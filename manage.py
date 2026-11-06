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

        # Format tampilan link server agar menampilkan localhost & IP lokal yang valid (menghindari ERR_ADDRESS_INVALID pada 0.0.0.0)
        orig_on_bind = runserver_command.on_bind

        def custom_on_bind(self, server_port):
            if self.addr in ("0.0.0.0", "0"):
                from datetime import datetime
                from django.conf import settings
                import socket

                quit_command = "CTRL-BREAK" if sys.platform == "win32" else "CONTROL-C"
                now = datetime.now().strftime("%B %d, %Y - %X")
                version = self.get_version()

                lan_ip = None
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.settimeout(0.5)
                    s.connect(("8.8.8.8", 80))
                    lan_ip = s.getsockname()[0]
                    s.close()
                except Exception:
                    pass

                msg = [
                    f"{now}",
                    f"Django version {version}, using settings {settings.SETTINGS_MODULE!r}",
                    f"Starting development server:",
                    f"  👉 Komputer/Laptop : {self.protocol}://localhost:{server_port}/",
                ]
                if lan_ip:
                    msg.append(f"  👉 HP / Jaringan   : {self.protocol}://{lan_ip}:{server_port}/")

                admin_slug = getattr(settings, 'ADMIN_URL_PATH', 'portal-rahasia-admin').strip('/')
                if admin_slug:
                    msg.append(f"  🔒 Portal Admin    : {self.protocol}://localhost:{server_port}/{admin_slug}/")

                msg.append(f"Quit the server with {quit_command}.\n")
                print("\n".join(msg), file=self.stdout)
            else:
                orig_on_bind(self, server_port)

        runserver_command.on_bind = custom_on_bind
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
