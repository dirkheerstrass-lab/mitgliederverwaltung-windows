"""Serienmail-Versand über ein bestehendes E-Mail-Konto (SMTP-Client).

Kein eigener Mailserver nötig — die App meldet sich wie ein normales
Mailprogramm (Outlook/Thunderbird) bei einem vorhandenen Postfach an.
Enthält keine Streamlit-Aufrufe (kein `st.*`), analog zu mitglieder.py.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

# Kurze Pause zwischen einzelnen Serienmail-Sends, damit auch bei größeren
# Verteilern (>100 Empfänger) keine Rate-Limits des E-Mail-Anbieters greifen
# (z. B. Gmail begrenzt Sends pro Minute zusätzlich zum Tageslimit).
SERIENMAIL_PAUSE_SEKUNDEN = 0.5


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


def kassierer_email(smtp_config: dict) -> str:
    """Liest die E-Mail-Adresse des Kassierers für die Sammel-Benachrichtigung
    bei fälligen Beiträgen aus einem bereits über smtp_konfiguration() geprüften
    Config-Dict (Feld 'kassierer_email'). Wirft SmtpNichtKonfiguriert, wenn sie
    fehlt - separat vom allgemeinen smtp_konfiguration()-Check, da dieses Feld
    nur für die Beitragsmahnung-Ansicht benötigt wird, nicht für den normalen
    Serienmail-Versand."""
    if not smtp_config.get("kassierer_email"):
        raise SmtpNichtKonfiguriert(
            "Kein 'kassierer_email' im [smtp]-Block von .streamlit/secrets.toml gefunden. "
            "Siehe .streamlit/secrets.toml.example."
        )
    return smtp_config["kassierer_email"]


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
    # Port 465 ist bei den meisten Anbietern "implizites SSL" (SMTPS) - die
    # Verbindung muss von Anfang an verschlüsselt sein, ein nachträgliches
    # starttls() wie bei Port 587 schlägt dort fehl. Alle anderen Ports
    # (587, 25, ...) laufen wie bisher über STARTTLS.
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            server.login(smtp_config["user"], smtp_config["passwort"])
            server.send_message(nachricht)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(smtp_config["user"], smtp_config["passwort"])
            server.send_message(nachricht)
