"""SMTP email channel. With no SMTP_URL configured, messages are only logged."""

import smtplib
from email.message import EmailMessage
from urllib.parse import unquote, urlparse

from myziel.core.logging import get_logger

log = get_logger(__name__)


class EmailChannel:
    name = "email"

    def __init__(self, smtp_url: str, mail_from: str, timeout: float = 15):
        self.smtp_url = smtp_url
        self.mail_from = mail_from
        self.timeout = timeout

    def send(self, to: str, subject: str, body: str) -> None:
        if not self.smtp_url:
            log.info("email.not_configured", to=to, subject=subject, body=body)
            return
        url = urlparse(self.smtp_url)
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.mail_from, to, subject
        msg.set_content(body)
        if url.scheme == "smtps":
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                url.hostname or "", url.port or 465, timeout=self.timeout
            )
        else:
            server = smtplib.SMTP(url.hostname or "", url.port or 587, timeout=self.timeout)
            server.starttls()
        with server:
            if url.username:
                server.login(unquote(url.username), unquote(url.password or ""))
            server.send_message(msg)
        log.info("email.sent", to=to, subject=subject)
