"""Sends plain-text email over SMTP with TLS."""
import smtplib
import ssl
from email.message import EmailMessage

from janitor.settings import Settings


class MailError(Exception):
    pass


def smtp_send(settings: Settings, password: str, message: EmailMessage) -> None:
    """Blocking. Run it in a thread."""
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context)
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    with smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=context)
        if settings.smtp_user:
            smtp.login(settings.smtp_user, password)
        smtp.send_message(message)


def build_message(settings: Settings, subject: str, body: str) -> EmailMessage:
    if not (settings.smtp_host and settings.mail_from and settings.mail_to):
        raise MailError("Email is not set up: fill in SMTP host, sender and recipient.")
    message = EmailMessage()
    message["From"], message["To"] = settings.mail_from, settings.mail_to
    message["Subject"] = f"[DockerJanitor] {subject}"
    message.set_content(body)
    return message
