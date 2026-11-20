from anymail.signals import AnymailTrackingEvent, tracking
from django.test import TestCase
from frontend.models import MailLog, User
from mock import patch


def send_event(**kwargs):
    sender = None
    event = AnymailTrackingEvent(**kwargs)
    esp_name = "supermail"
    tracking.send(sender, event=event, esp_name=esp_name)
    return event


class TestAnymailReceiver(TestCase):
    fixtures = ["bookmark_alerts", "measures"]

    @patch("frontend.signals.handlers.logger")
    def test_missing_user_logged(self, mock_logger):
        send_event(
            event_type="test_event",
            recipient="p@q.com",
            tags=["monthly_update"],
            message_id="foo",
        )
        mock_logger.warn.assert_any_call("Could not find recipient p@q.com")

    @patch("frontend.signals.handlers.logger")
    def test_delivered(self, mock_logger):
        send_event(
            event_type="delivered",
            recipient=User.objects.first().email,
            tags=["monthly_update"],
            message_id="foo",
        )
        self.assertEqual(User.objects.first().profile.emails_received, 1)

    @patch("frontend.signals.handlers.logger")
    def test_opened(self, mock_logger):
        send_event(
            event_type="opened",
            recipient=User.objects.first().email,
            tags=["monthly_update"],
            message_id="foo",
        )
        self.assertEqual(User.objects.first().profile.emails_opened, 1)

    @patch("frontend.signals.handlers.logger")
    def test_clicked(self, mock_logger):
        send_event(
            event_type="clicked",
            recipient=User.objects.first().email,
            tags=["monthly_update"],
            message_id="foo",
        )
        self.assertEqual(User.objects.first().profile.emails_clicked, 1)

    @patch("frontend.signals.handlers.logger")
    def test_maillog(self, mock_logger):
        metadata = {
            "user-agent": "tofu",
            "subject": ["tempeh"],
            "campaign_name": "aquafaba",
            "email_id": "seitan",
        }
        send_event(
            event_type="frobbed",
            recipient=User.objects.first().email,
            tags=["monthly_update"],
            esp_event=metadata,
            message_id="foo",
        )
        log = MailLog.objects.first()
        self.assertEqual(log.tags, ["monthly_update"])
        self.assertEqual(log.message_id, "foo")
        self.assertEqual(log.recipient, "foo@baz.com")
        self.assertEqual(log.event_type, "frobbed")
        self.assertEqual(log.metadata, metadata)
