import logging

from anymail.signals import tracking
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from frontend.models import MailLog, Profile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def handle_user_save(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


def log_email_event(event):
    MailLog.objects.create(
        metadata=event.esp_event,
        recipient=event.recipient,
        tags=event.tags,
        reject_reason=event.reject_reason,
        message_id=event.message_id,
        event_type=event.event_type,
        timestamp=event.timestamp,
    )


@receiver(tracking)
def handle_anymail_webhook(sender, event, esp_name, **kwargs):
    log_email_event(event)
    user = get_user_by_email(event.recipient)
    if event.tags and "monthly_update" in event.tags:
        logger.debug("Handling webhook from %s: %s" % (esp_name, event.__dict__))
        if user:
            if event.event_type == "delivered":
                user.profile.emails_received += 1
                user.profile.save()
            elif event.event_type == "opened":
                user.profile.emails_opened += 1
                user.profile.save()
            elif event.event_type == "clicked":
                user.profile.emails_clicked += 1
                user.profile.save()


def get_user_by_email(email):
    user = User.objects.filter(email=email)
    user = user and user[0]
    if not user:
        logger.warn("Could not find recipient %s" % email)
    return user or None
