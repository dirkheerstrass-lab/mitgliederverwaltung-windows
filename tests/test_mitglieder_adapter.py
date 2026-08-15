# test_mitglieder_adapter.py
"""
Tests für die Datenschicht: mitglieder_adapter.py bindet mitglieder.py/mailer.py
ein und leitet sie auf ein eigenes, temporäres Datenverzeichnis um, damit Tests
nicht auf das lokale data/-Verzeichnis zugreifen.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mitglieder_adapter as adapter  # noqa: E402
from mitglieder_adapter import mitglieder, LocalUploadedFile  # noqa: E402


@pytest.fixture
def temp_data_dir(monkeypatch, tmp_path):
    """Leitet mitglieder.DATA_DIR etc. auf ein temporäres Verzeichnis um."""
    monkeypatch.setattr(mitglieder, "DATA_DIR", tmp_path)
    monkeypatch.setattr(mitglieder, "CSV_PATH", tmp_path / "mitglieder.csv")
    monkeypatch.setattr(mitglieder, "FOTOS_DIR", tmp_path / "fotos")
    monkeypatch.setattr(mitglieder, "ANHAENGE_DIR", tmp_path / "anhaenge")
    monkeypatch.setattr(mitglieder, "MAIL_LOG_DIR", tmp_path / "mail_log")
    return tmp_path


def _beispiel_daten(**overrides) -> dict:
    daten = {spalte: "" for spalte in mitglieder.COLUMNS}
    daten.update({
        "Vorname": "Erika",
        "Nachname": "Musterfrau",
        "E-Mail": "erika@example.com",
        "Eintrittsdatum": "2022-06-01",
        "Mitgliedsstatus": "aktiv",
    })
    daten.update(overrides)
    return daten


def test_load_data_erstellt_leere_csv(temp_data_dir):
    df = mitglieder.load_data()
    assert list(df.columns) == mitglieder.COLUMNS
    assert len(df) == 0
    assert (temp_data_dir / "mitglieder.csv").exists()


def test_add_and_load_member(temp_data_dir):
    df = mitglieder.load_data()
    neuer_df = mitglieder.add_member(df, _beispiel_daten())
    mitglieder.save_data(neuer_df)

    geladen = mitglieder.load_data()
    assert len(geladen) == 1
    assert geladen.iloc[0]["Vorname"] == "Erika"
    assert geladen.iloc[0]["ID"]


def test_update_member(temp_data_dir):
    df = mitglieder.load_data()
    neuer_df = mitglieder.add_member(df, _beispiel_daten())
    mitglieder.save_data(neuer_df)
    mitglied_id = neuer_df.iloc[0]["ID"]

    aktualisiert = mitglieder.update_member(neuer_df, mitglied_id, {"Mitgliedsstatus": "inaktiv", "Notizen": "Test"})
    mitglieder.save_data(aktualisiert)

    geladen = mitglieder.load_data()
    assert geladen.iloc[0]["Mitgliedsstatus"] == "inaktiv"
    assert geladen.iloc[0]["Notizen"] == "Test"


def test_delete_member(temp_data_dir):
    df = mitglieder.load_data()
    neuer_df = mitglieder.add_member(df, _beispiel_daten())
    mitglieder.save_data(neuer_df)
    mitglied_id = neuer_df.iloc[0]["ID"]

    aktualisiert = mitglieder.delete_member(neuer_df, mitglied_id)
    mitglieder.save_data(aktualisiert)

    geladen = mitglieder.load_data()
    assert len(geladen) == 0


def test_validate_member_erkennt_fehlende_pflichtfelder(temp_data_dir):
    df = mitglieder.load_data()
    fehler = mitglieder.validate_member({"Vorname": "", "Nachname": ""}, df)
    assert any("Vorname" in f for f in fehler)
    assert any("Nachname" in f for f in fehler)


def test_local_uploaded_file_adapter(tmp_path):
    quelle = tmp_path / "foto.jpg"
    quelle.write_bytes(b"testinhalt")

    upload = LocalUploadedFile(quelle)
    assert upload.name == "foto.jpg"
    assert upload.size == len(b"testinhalt")
    assert upload.getbuffer() == b"testinhalt"


def test_save_and_get_photo(temp_data_dir, tmp_path):
    quelle = tmp_path / "quelle_foto.png"
    quelle.write_bytes(b"bilddaten")

    mitglieder.save_photo("mitglied-1", LocalUploadedFile(quelle))
    pfad = mitglieder.get_photo_path("mitglied-1")

    assert pfad is not None
    assert pfad.read_bytes() == b"bilddaten"


def test_save_and_list_attachment(temp_data_dir, tmp_path):
    quelle = tmp_path / "dokument.pdf"
    quelle.write_bytes(b"%PDF-1.4")

    mitglieder.save_attachment("mitglied-1", LocalUploadedFile(quelle))
    anhaenge = mitglieder.list_attachments("mitglied-1")

    assert len(anhaenge) == 1
    assert anhaenge[0].name == "dokument.pdf"


def test_smtp_config_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "SMTP_CONFIG_FILE", tmp_path / "smtp_config.json")
    assert adapter.load_smtp_config() == {}

    adapter.save_smtp_config({"host": "smtp.example.com", "port": "587", "user": "u", "passwort": "p", "absender": "a@example.com"})
    geladen = adapter.load_smtp_config()
    assert geladen["host"] == "smtp.example.com"


def test_export_excel_und_pdf_erzeugen_bytes(temp_data_dir):
    df = mitglieder.load_data()
    neuer_df = mitglieder.add_member(df, _beispiel_daten())
    mitglieder.save_data(neuer_df)

    excel_bytes = mitglieder.export_excel(neuer_df)
    pdf_bytes = mitglieder.export_pdf(neuer_df)

    assert isinstance(excel_bytes, (bytes, bytearray)) and len(excel_bytes) > 0
    assert isinstance(pdf_bytes, (bytes, bytearray)) and len(pdf_bytes) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
