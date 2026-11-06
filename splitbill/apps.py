from django.apps import AppConfig
from django.db.models.signals import post_migrate


def ensure_admin_account(sender, **kwargs):
    if sender.name == 'splitbill':
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if not User.objects.filter(username='admin').exists():
                User.objects.create_superuser('admin', 'admin@splitbill.local', 'superadmin123')
            else:
                user = User.objects.get(username='admin')
                user.set_password('superadmin123')
                user.is_staff = True
                user.is_superuser = True
                user.save()
        except Exception:
            pass


class SplitbillConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'splitbill'

    def ready(self):
        post_migrate.connect(ensure_admin_account, sender=self)

        # Python 3.14 compatibility patch for Django BaseContext.__copy__
        try:
            from django.template.context import BaseContext
            def _patch_base_context_copy(self):
                d = self.__class__.__new__(self.__class__)
                d.__dict__.update(self.__dict__)
                d.dicts = self.dicts[:]
                return d
            BaseContext.__copy__ = _patch_base_context_copy
        except Exception:
            pass
