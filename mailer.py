"""Serienmail-Versand über ein bestehendes E-Mail-Konto (SMTP-Client).

Kein eigener Mailserver nötig — die App meldet sich wie ein normales
Mailprogramm (Outlook/Thunderbird) bei einem vorhandenen Postfach an.
Enthält keine Streamlit-Aufrufe (kein `st.*`), analog zu mitglieder.py.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage


class SmtpNichtKonfiguriert(Exception):
    """Wird ausgelöst, wenn der [smtp]-Block in secrets.toml fehlt oder unvollständig ist."""


def smtp_konfiguration(secrets) -> dict:
    if "smtp" not in secrets:
        raise SmtpNichtKonfiguriert(
            "Kein [smtp]-Block in .streamlit/secrets.toml gefunden. "
            "Siehe .streamlit/secrets.toml.example für die nötigen Felder."
        )
    smtp = secrets["smtp"]
    pflichtfelder = ["host", "port", "user", "passwort", "absender"]
    fehlend = [f for f in pflichtfelder if not smtp.get(f)]
    if fehlend:
        raise SmtpNichtKonfiguriert(
            f"[smtp]-Block unvollständig, es fehlen: {', '.join(fehlend)}."
        )
    return dict(smtp)


def send_mail(
    smtp_config: dict,
    empfaenger: str,
    betreff: str,
    text: str,
    anhang_bytes: bytes | None = None,
    anhang_dateiname: str = "anhang.pdf",
) -> None:
    """Verschickt eine einzelne E-Mail über den konfigurierten SMTP-Server.
    Wirft eine Exception bei Fehlschlag (z. B. ungültige Adresse, Auth-Fehler) -
    der Aufrufer entscheidet, ob das den Gesamtlauf abbricht oder übersprungen wird."""
    nachricht = EmailMessage()
    nachricht["Subject"] = betreff
    nachricht["From"] = smtp_config["absender"]
    nachricht["To"] = empfaenger
    nachricht.set_content(text)

    if anhang_bytes is not None:
        nachricht.add_attachment(
            anhang_bytes, maintype="application", subtype="pdf", filename=anhang_dateiname
        )

    host = smtp_config["host"]
    port = int(smtp_config["port"])
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(smtp_config["user"], smtp_config["passwort"])
        server.send_message(nachricht)
