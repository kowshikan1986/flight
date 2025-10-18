"""Management command to manually activate user accounts."""

from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User


class Command(BaseCommand):
    help = 'Manually activate user accounts by email address'

    def add_arguments(self, parser):
        parser.add_argument(
            'emails',
            nargs='*',
            type=str,
            help='Email addresses of users to activate'
        )
        parser.add_argument(
            '--list-unverified',
            action='store_true',
            help='List all unverified users'
        )

    def handle(self, *args, **options):
        # List unverified users
        if options['list_unverified']:
            unverified_users = User.objects.filter(email_verified=False)
            if not unverified_users.exists():
                self.stdout.write(self.style.SUCCESS('✅ No unverified users found!'))
            else:
                self.stdout.write(self.style.WARNING(f'Found {unverified_users.count()} unverified users:'))
                for user in unverified_users:
                    self.stdout.write(f'  - {user.email} (joined: {user.date_joined})')
            return

        # Activate users
        emails = options['emails']
        activated_count = 0
        
        for email in emails:
            try:
                user = User.objects.get(email__iexact=email)
                
                if user.email_verified:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  {email} is already verified')
                    )
                else:
                    user.email_verified = True
                    user.is_active = True
                    user.email_verified_at = timezone.now()
                    user.save(update_fields=['email_verified', 'is_active', 'email_verified_at'])
                    activated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Activated: {email}')
                    )
                    
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ User not found: {email}')
                )
        
        if activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'\n🎉 Successfully activated {activated_count} user(s)!')
            )
