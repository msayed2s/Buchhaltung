"""E-Mail-Versand von Rechnungen über einen SMTP-Server."""
import os
import smtplib
import mimetypes
from email.message import EmailMessage


def send_email(smtp, to_addr, subject, body, attachments=None):
    """Sendet eine E-Mail mit optionalen Anhängen.

    ``smtp`` ist das Einstellungs-Dict (host, port, user, password, from_addr,
    use_tls). Wirft bei Fehlern eine Exception (vom Aufrufer behandelt).
    """
    host = (smtp.get("host") or "").strip()
    if not host:
        raise ValueError("Es ist kein SMTP-Server hinterlegt. Bitte unter „Einstellungen“ eintragen.")
    if not to_addr:
        raise ValueError("Die E-Mail-Adresse des Kunden fehlt.")

    from_addr = (smtp.get("from_addr") or smtp.get("user") or "").strip()
    port = int(smtp.get("port") or 587)

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    for path in (attachments or []):
        if not path or not os.path.exists(path):
            continue
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(path, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(path))

    use_tls = bool(smtp.get("use_tls", True))
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            _login_send(server, smtp, msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            _login_send(server, smtp, msg)


def _login_send(server, smtp, msg):
    user = (smtp.get("user") or "").strip()
    password = smtp.get("password") or ""
    if user:
        server.login(user, password)
    server.send_message(msg)
