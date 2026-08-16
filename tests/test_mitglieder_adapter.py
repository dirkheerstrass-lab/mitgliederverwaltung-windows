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
    monkeypatch.setattr(mitglieder, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(mitglieder, "CSV_PATH", tmp_path / "data" / "mitglieder.csv")
    monkeypatch.setattr(mitglieder, "FOTOS_DIR", tmp_path / "data" / "fotos")
    monkeypatch.setattr(mitglieder, "ANHAENGE_DIR", tmp_path / "data" / "anhaenge")
    monkeypatch.setattr(mitglieder, "MAIL_LOG_DIR", tmp_path / "data" / "mail_log")
    monkeypatch.setattr(mitglieder, "ZAHLUNGEN_DIR", tmp_path / "data" / "zahlungen")
    monkeypatch.setattr(mitglieder, "BACKUPS_DIR", tmp_path / "backups")
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
    assert (temp_data_dir / "data" / "mitglieder.csv").exists()


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


def test_is_valid_iban():
    assert mitglieder.is_valid_iban("DE89 3704 0044 0532 0130 00") is True
    assert mitglieder.is_valid_iban("DE00000000000000000000") is False
    assert mitglieder.is_valid_iban("") is False


def test_validate_member_normalisiert_gueltige_iban(temp_data_dir):
    df = mitglieder.load_data()
    daten = _beispiel_daten(IBAN="de89 3704 0044 0532 0130 00")
    fehler = mitglieder.validate_member(daten, df)
    assert fehler == []
    assert daten["IBAN"] == "DE89370400440532013000"


def test_validate_member_lehnt_ungueltige_iban_ab(temp_data_dir):
    df = mitglieder.load_data()
    daten = _beispiel_daten(IBAN="DE00000000000000000000")
    fehler = mitglieder.validate_member(daten, df)
    assert any("IBAN" in f for f in fehler)


def test_log_und_list_zahlungen(temp_data_dir):
    mitglieder.log_zahlung("mitglied-1", "15.0", "2024-01-01", "Überweisung", "Testnotiz")
    verlauf = mitglieder.list_zahlungen("mitglied-1")
    assert len(verlauf) == 1
    assert verlauf[0]["betrag"] == "15.0"
    assert verlauf[0]["zahlungsart"] == "Überweisung"
    assert verlauf[0]["notiz"] == "Testnotiz"


def test_faellige_mitglieder_erkennt_ueberfaellige_zahlung(temp_data_dir):
    df = mitglieder.load_data()
    neuer_df = mitglieder.add_member(df, _beispiel_daten(
        Letzte_Zahlung="2020-01-01", Zahlungsrhythmus="monatlich", Beitragsbetrag="15.0",
    ))
    mitglieder.save_data(neuer_df)

    faellig = mitglieder.faellige_mitglieder(mitglieder.load_data())
    assert len(faellig) == 1
    assert faellig.iloc[0]["Faelligkeitsdatum"]

    text = mitglieder.build_kassierer_beitragsuebersicht(faellig)
    assert "Erika" in text


def test_build_sepa_mandat_pdf_erzeugt_bytes(temp_data_dir):
    df = mitglieder.load_data()
    neuer_df = mitglieder.add_member(df, _beispiel_daten(IBAN="DE89370400440532013000"))
    mitglieder.save_data(neuer_df)

    pdf_bytes = mitglieder.build_sepa_mandat_pdf(neuer_df.iloc[0])
    assert isinstance(pdf_bytes, (bytes, bytearray)) and len(pdf_bytes) > 0


def test_backup_und_restore_roundtrip(temp_data_dir):
    df = mitglieder.load_data()
    neuer_df = mitglieder.add_member(df, _beispiel_daten())
    mitglieder.save_data(neuer_df)

    backup_bytes = mitglieder.build_backup_zip()
    assert len(backup_bytes) > 0

    aktualisiert = mitglieder.delete_member(mitglieder.load_data(), neuer_df.iloc[0]["ID"])
    mitglieder.save_data(aktualisiert)
    assert len(mitglieder.load_data()) == 0

    mitglieder.restore_from_backup(backup_bytes)
    geladen = mitglieder.load_data()
    assert len(geladen) == 1
    assert geladen.iloc[0]["Vorname"] == "Erika"

    sicherheitsbackups = mitglieder.list_sicherheits_backups()
    assert len(sicherheitsbackups) == 1


def test_restore_from_backup_lehnt_ungueltiges_zip_ab(temp_data_dir):
    with pytest.raises(mitglieder.UngueltigesBackup):
        mitglieder.restore_from_backup(b"kein zip")


def test_adapter_ueberschreibt_backups_und_zahlungen_dir():
    """Regressionstest: BACKUPS_DIR/ZAHLUNGEN_DIR müssen explizit auf denselben
    Root wie DATA_DIR umgebogen werden, da mitglieder.py sie beim eigenen
    Import unabhängig von DATA_DIR aus seinem eigenen BASE_DIR ableitet."""
    assert mitglieder.BACKUPS_DIR.parent == mitglieder.DATA_DIR.parent
    assert mitglieder.ZAHLUNGEN_DIR == mitglieder.DATA_DIR / "zahlungen"


def test_adapter_frozen_mode_verankert_project_root_an_exe_ordner(monkeypatch):
    """PROJECT_ROOT (für sys.path/sys.executable-Auflösung, u. a. für die
    einmalige Datenmigration relevant) muss im PyInstaller-Onedir-Build am
    Ordner der .exe (sys.executable) hängen, nicht an Path(__file__) von
    mitglieder_adapter.py - dieser liegt im gebauten Programm in _internal/,
    nicht neben der .exe."""
    import importlib

    fake_exe = Path(tempfile.mkdtemp()) / "Mitgliederverwaltung.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    try:
        importlib.reload(adapter)
        assert adapter.PROJECT_ROOT == fake_exe.parent
    finally:
        monkeypatch.delattr(sys, "frozen", raising=False)
        importlib.reload(adapter)  # Modulzustand für nachfolgende Tests zurücksetzen


def test_daten_liegen_immer_in_appdata_unabhaengig_von_frozen(monkeypatch):
    """Regressionstest für den Datenverlust-Bug: data/ und backups/ dürfen
    NICHT im App-/Build-Ordner liegen (weder im Repo-Root noch neben der
    .exe), da PyInstaller beim Bauen (COLLECT) den kompletten Zielordner
    löscht und neu anlegt - das hat zuvor echte Mitgliederdaten bei jedem
    .exe-Neubau mitgelöscht. DATA_DIR/BACKUPS_DIR müssen immer unter
    %APPDATA%\\Mitgliederverwaltung liegen, unabhängig vom frozen-Status."""
    import importlib

    assert adapter.mitglieder.DATA_DIR == adapter.APPDATA_ROOT / "data"
    assert adapter.mitglieder.BACKUPS_DIR == adapter.APPDATA_ROOT / "backups"

    fake_exe = Path(tempfile.mkdtemp()) / "Mitgliederverwaltung.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    try:
        importlib.reload(adapter)
        assert adapter.mitglieder.DATA_DIR == adapter.APPDATA_ROOT / "data"
        assert adapter.mitglieder.BACKUPS_DIR == adapter.APPDATA_ROOT / "backups"
        # Insbesondere NICHT im (beim Bauen geloeschten) Ordner neben der .exe:
        assert adapter.mitglieder.DATA_DIR != fake_exe.parent / "data"
    finally:
        monkeypatch.delattr(sys, "frozen", raising=False)
        importlib.reload(adapter)


def test_einmalige_datenmigration_verschiebt_alte_daten(monkeypatch, tmp_path):
    """Simuliert eine alte Installation mit Daten neben der .exe (bzw. im
    Repo-Root) und prüft, dass die einmalige Migration sie zuverlässig nach
    %APPDATA% verschiebt, ohne Daten zu verlieren."""
    import importlib

    alter_projekt_ordner = tmp_path / "alte_installation"
    (alter_projekt_ordner / "data" / "fotos").mkdir(parents=True)
    (alter_projekt_ordner / "data" / "mitglieder.csv").write_text("ID,Vorname\n1,Erika\n", encoding="utf-8")
    (alter_projekt_ordner / "data" / "fotos" / "1.jpg").write_bytes(b"bilddaten")
    (alter_projekt_ordner / "backups").mkdir(parents=True)
    (alter_projekt_ordner / "backups" / "vor_restore_test.zip").write_bytes(b"PK\x03\x04")

    neuer_appdata_ordner = tmp_path / "neues_appdata" / "Mitgliederverwaltung"

    monkeypatch.setattr(adapter, "PROJECT_ROOT", alter_projekt_ordner)
    monkeypatch.setattr(adapter, "APPDATA_ROOT", neuer_appdata_ordner)
    monkeypatch.setattr(adapter, "_DATA_DIR", neuer_appdata_ordner / "data")
    monkeypatch.setattr(adapter, "_BACKUPS_DIR", neuer_appdata_ordner / "backups")

    meldung = adapter._einmalige_datenmigration()

    assert meldung is not None
    assert "Mitgliederdaten" in meldung and "Sicherheits-Backups" in meldung
    assert (neuer_appdata_ordner / "data" / "mitglieder.csv").read_text(encoding="utf-8") == "ID,Vorname\n1,Erika\n"
    assert (neuer_appdata_ordner / "data" / "fotos" / "1.jpg").read_bytes() == b"bilddaten"
    assert (neuer_appdata_ordner / "backups" / "vor_restore_test.zip").exists()
    assert not (alter_projekt_ordner / "data").exists(), "Alter Ordner sollte verschoben (nicht kopiert) worden sein"

    # Zweiter Aufruf (z. B. beim nächsten Programmstart) darf nichts mehr tun,
    # da im Zielordner schon Daten liegen und der alte Ordner nicht mehr existiert.
    meldung2 = adapter._einmalige_datenmigration()
    assert meldung2 is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
