# gui.py
"""
PyQt5-Oberfläche der Windows-Desktop-Version der Mitgliederverwaltung.

Nutzt dieselbe Datenschicht wie die Web-App (mitglieder.py, mailer.py aus dem
Projekt-Root, eingebunden über mitglieder_adapter.py) — Feldschema, Validierung,
Exporte, Foto-/Anhang-Handling und Serienmail-Logik sind identisch zur Web-App.

Aufbau (analog zu den drei Ansichten der Web-App):
- Übersicht: Metriken, Geburtstage/Jubiläen, Filter, Tabelle, Bearbeiten-Dialog, Exporte
- Neues Mitglied: Formular (gleiche Felder wie Bearbeiten, ohne Foto/Anhänge/Mail-Log)
- Serienmail: Mehrfachauswahl + Versand über SMTP
"""

import sys
import time
from pathlib import Path
from datetime import date

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QCheckBox,
    QDateEdit,
    QDoubleSpinBox,
    QGroupBox,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QFileDialog,
    QAbstractItemView,
    QInputDialog,
)

import mitglieder_adapter as adapter
from mitglieder_adapter import mitglieder, mailer, LocalUploadedFile

COLUMNS = mitglieder.COLUMNS

# Wird bei jedem Fix erhöht: kleine Fixes -> Nachkommastelle (1.00 -> 1.01),
# größere/strukturelle Änderungen -> Vorkommastelle (1.05 -> 2.00, Nachkommastelle zurück auf 00).
VERSION = "1.00"


# ---------------------------------------------------------------------------
# Hilfsfunktionen für Datumsfelder (optional/verpflichtend, ISO-Format)
# ---------------------------------------------------------------------------
def _iso_to_qdate(iso_text: str) -> QDate | None:
    d = mitglieder.parse_datum(iso_text or "")
    if d is None:
        return None
    return QDate(d.year, d.month, d.day)


def _qdate_to_iso(qdate: QDate) -> str:
    return date(qdate.year(), qdate.month(), qdate.day()).isoformat()


class OptionalDateEdit(QWidget):
    """QDateEdit mit einer 'kein Datum'-Checkbox, für optionale Datumsfelder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.date_edit = QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setMinimumDate(QDate(1900, 1, 1))
        self.date_edit.setMaximumDate(QDate(2100, 12, 31))
        self.date_edit.setDate(QDate.currentDate())
        self.empty_check = QCheckBox("kein Datum", self)
        self.empty_check.setChecked(True)
        self.empty_check.toggled.connect(lambda checked: self.date_edit.setEnabled(not checked))
        self.date_edit.setEnabled(False)
        layout.addWidget(self.date_edit)
        layout.addWidget(self.empty_check)

    def set_iso(self, iso_text: str):
        qd = _iso_to_qdate(iso_text)
        if qd is None:
            self.empty_check.setChecked(True)
        else:
            self.date_edit.setDate(qd)
            self.empty_check.setChecked(False)

    def get_iso(self) -> str:
        if self.empty_check.isChecked():
            return ""
        return _qdate_to_iso(self.date_edit.date())


# ---------------------------------------------------------------------------
# Gemeinsames Formular (genutzt von "Neues Mitglied" und dem Bearbeiten-Dialog)
# ---------------------------------------------------------------------------
class MemberFormWidget(QWidget):
    """Enthält alle Mitgliedsfelder aus mitglieder.COLUMNS außer der ID,
    gegliedert in 3 Tabs analog zur Web-App: Persönliche Daten,
    Gruppen & Mitgliedschaft, Konto & SEPA."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        self.tabs.addTab(self._build_persoenliche_daten_tab(), "Persönliche Daten")
        self.tabs.addTab(self._build_gruppen_tab(), "Gruppen && Mitgliedschaft")
        self.tabs.addTab(self._build_konto_sepa_tab(), "Konto && SEPA")

    # -----------------------------------------------------------------------
    def _build_persoenliche_daten_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)

        grid = QGridLayout()
        outer.addLayout(grid)

        col1 = QFormLayout()
        self.anrede = QComboBox()
        self.anrede.addItems(mitglieder.ANREDE_OPTIONEN)
        col1.addRow("Anrede:", self.anrede)
        self.vorname = QLineEdit()
        col1.addRow("Vorname *:", self.vorname)
        self.nachname = QLineEdit()
        col1.addRow("Nachname *:", self.nachname)
        self.email = QLineEdit()
        col1.addRow("E-Mail *:", self.email)
        self.telefon = QLineEdit()
        col1.addRow("Telefon:", self.telefon)
        self.mitgliedsnummer = QLineEdit()
        col1.addRow("Mitgliedsnummer:", self.mitgliedsnummer)
        grid.addLayout(col1, 0, 0)

        col2 = QFormLayout()
        self.strasse = QLineEdit()
        col2.addRow("Straße:", self.strasse)
        self.plz = QLineEdit()
        col2.addRow("PLZ:", self.plz)
        self.stadt = QLineEdit()
        col2.addRow("Stadt:", self.stadt)
        self.geburtstag = OptionalDateEdit()
        col2.addRow("Geburtstag:", self.geburtstag)
        grid.addLayout(col2, 0, 1)

        einwilligung_box = QGroupBox("Einwilligung")
        einwilligung_layout = QHBoxLayout(einwilligung_box)
        self.einwilligung = QCheckBox("Einwilligung zur Foto-/Datenspeicherung liegt vor")
        einwilligung_layout.addWidget(self.einwilligung)
        self.einwilligung_datum = OptionalDateEdit()
        einwilligung_layout.addWidget(QLabel("Datum:"))
        einwilligung_layout.addWidget(self.einwilligung_datum)
        outer.addWidget(einwilligung_box)

        vertreter_box = QGroupBox("Angaben zum gesetzlichen Vertreter (falls minderjährig)")
        vertreter_layout = QFormLayout(vertreter_box)
        self.vertreter_name = QLineEdit()
        vertreter_layout.addRow("Name:", self.vertreter_name)
        self.vertreter_telefon = QLineEdit()
        vertreter_layout.addRow("Telefon:", self.vertreter_telefon)
        self.vertreter_email = QLineEdit()
        vertreter_layout.addRow("E-Mail:", self.vertreter_email)
        outer.addWidget(vertreter_box)

        outer.addWidget(QLabel("Notizen:"))
        self.notizen = QTextEdit()
        self.notizen.setMaximumHeight(80)
        outer.addWidget(self.notizen)
        outer.addStretch(1)
        return tab

    # -----------------------------------------------------------------------
    def _build_gruppen_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)

        mitgliedschaft_box = QGroupBox("Mitgliedschaft")
        mitgliedschaft_layout = QFormLayout(mitgliedschaft_box)
        self.eintrittsdatum = QDateEdit()
        self.eintrittsdatum.setCalendarPopup(True)
        self.eintrittsdatum.setDisplayFormat("dd.MM.yyyy")
        self.eintrittsdatum.setMinimumDate(QDate(1900, 1, 1))
        self.eintrittsdatum.setMaximumDate(QDate(2100, 12, 31))
        self.eintrittsdatum.setDate(QDate.currentDate())
        mitgliedschaft_layout.addRow("Eintrittsdatum *:", self.eintrittsdatum)
        self.austrittsdatum = OptionalDateEdit()
        mitgliedschaft_layout.addRow("Austrittsdatum:", self.austrittsdatum)
        self.status = QComboBox()
        self.status.addItems(mitglieder.STATUS_OPTIONEN)
        mitgliedschaft_layout.addRow("Mitgliedsstatus *:", self.status)
        outer.addWidget(mitgliedschaft_box)

        status_box = QGroupBox("Gruppen")
        status_layout = QVBoxLayout(status_box)
        self.gruppen_list = QListWidget()
        self.gruppen_list.setSelectionMode(QAbstractItemView.NoSelection)
        for gruppe in mitglieder.GRUPPEN_OPTIONEN:
            item = QListWidgetItem(gruppe)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.gruppen_list.addItem(item)
        self.gruppen_list.setMaximumHeight(120)
        status_layout.addWidget(self.gruppen_list)
        outer.addWidget(status_box)

        nummern_box = QGroupBox("Funktion & weitere Nummern")
        nummern_layout = QFormLayout(nummern_box)
        self.funktion = QLineEdit()
        nummern_layout.addRow("Funktion im Verein:", self.funktion)
        self.dkv = QLineEdit()
        nummern_layout.addRow("DKV-Nummer:", self.dkv)
        self.nwdv = QLineEdit()
        nummern_layout.addRow("NWDV-Nummer:", self.nwdv)
        self.gameshot = QLineEdit()
        nummern_layout.addRow("Game-Shot-Nummer:", self.gameshot)
        outer.addWidget(nummern_box)
        outer.addStretch(1)
        return tab

    # -----------------------------------------------------------------------
    def _build_konto_sepa_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)

        beitrag_box = QGroupBox("Beitragsverwaltung")
        beitrag_layout = QFormLayout(beitrag_box)
        self.zahlungsrhythmus = QComboBox()
        self.zahlungsrhythmus.addItems(mitglieder.ZAHLUNGSRHYTHMUS_OPTIONEN)
        beitrag_layout.addRow("Zahlungsrhythmus:", self.zahlungsrhythmus)
        self.beitragsbetrag = QDoubleSpinBox()
        self.beitragsbetrag.setRange(0, 100000)
        self.beitragsbetrag.setDecimals(2)
        self.beitragsbetrag.setSingleStep(0.5)
        self.beitragsbetrag.setSuffix(" €")
        beitrag_layout.addRow("Beitragsbetrag:", self.beitragsbetrag)
        self.letzte_zahlung = OptionalDateEdit()
        beitrag_layout.addRow("Letzte Zahlung:", self.letzte_zahlung)
        self.naechste_faellig_label = QLabel("")
        beitrag_layout.addRow("Nächste Zahlung fällig:", self.naechste_faellig_label)
        self.letzte_zahlung.date_edit.dateChanged.connect(self._update_naechste_faellig)
        self.letzte_zahlung.empty_check.toggled.connect(self._update_naechste_faellig)
        self.zahlungsrhythmus.currentTextChanged.connect(self._update_naechste_faellig)
        outer.addWidget(beitrag_box)

        sepa_box = QGroupBox("SEPA-Mandat")
        sepa_layout = QFormLayout(sepa_box)
        self.iban = QLineEdit()
        self.iban.setPlaceholderText("z. B. DE89 3704 0044 0532 0130 00")
        sepa_layout.addRow("IBAN:", self.iban)
        self.kontoinhaber = QLineEdit()
        self.kontoinhaber.setPlaceholderText("Falls abweichend vom Mitgliedsnamen")
        sepa_layout.addRow("Kontoinhaber:", self.kontoinhaber)
        self.sepa_referenz = QLineEdit()
        sepa_layout.addRow("Mandatsreferenz:", self.sepa_referenz)
        self.sepa_datum = OptionalDateEdit()
        sepa_layout.addRow("Mandatsdatum:", self.sepa_datum)
        outer.addWidget(sepa_box)
        outer.addStretch(1)
        return tab

    def _update_naechste_faellig(self, *_args):
        naechste = mitglieder.compute_next_due(self.letzte_zahlung.get_iso(), self.zahlungsrhythmus.currentText())
        if naechste:
            qd = _iso_to_qdate(naechste)
            self.naechste_faellig_label.setText(qd.toString("dd.MM.yyyy") if qd else naechste)
        else:
            self.naechste_faellig_label.setText("-")

    # -- Daten aus dem Formular auslesen --
    def get_data(self) -> dict:
        gruppen = []
        for i in range(self.gruppen_list.count()):
            item = self.gruppen_list.item(i)
            if item.checkState() == Qt.Checked:
                gruppen.append(item.text())
        return {
            "Anrede": self.anrede.currentText(),
            "Vorname": self.vorname.text().strip(),
            "Nachname": self.nachname.text().strip(),
            "E-Mail": self.email.text().strip(),
            "Telefon": self.telefon.text().strip(),
            "Mitgliedsnummer": self.mitgliedsnummer.text().strip(),
            "Straße": self.strasse.text().strip(),
            "PLZ": self.plz.text().strip(),
            "Stadt": self.stadt.text().strip(),
            "Geburtstag": self.geburtstag.get_iso(),
            "Eintrittsdatum": _qdate_to_iso(self.eintrittsdatum.date()),
            "Austrittsdatum": self.austrittsdatum.get_iso(),
            "Gruppen": ";".join(gruppen),
            "Mitgliedsstatus": self.status.currentText(),
            "DKV-Nummer": self.dkv.text().strip(),
            "NWDV-Nummer": self.nwdv.text().strip(),
            "Game-Shot-Nummer": self.gameshot.text().strip(),
            "Funktion": self.funktion.text().strip(),
            "Einwilligung_Fotos_Daten": "Ja" if self.einwilligung.isChecked() else "Nein",
            "Einwilligung_Datum": self.einwilligung_datum.get_iso(),
            "Vertreter_Name": self.vertreter_name.text().strip(),
            "Vertreter_Telefon": self.vertreter_telefon.text().strip(),
            "Vertreter_E-Mail": self.vertreter_email.text().strip(),
            "Notizen": self.notizen.toPlainText().strip(),
            "Zahlungsrhythmus": self.zahlungsrhythmus.currentText(),
            "Beitragsbetrag": str(self.beitragsbetrag.value()),
            "Letzte_Zahlung": self.letzte_zahlung.get_iso(),
            "IBAN": self.iban.text().strip(),
            "Kontoinhaber": self.kontoinhaber.text().strip(),
            "SEPA_Mandatsreferenz": self.sepa_referenz.text().strip(),
            "SEPA_Mandatsdatum": self.sepa_datum.get_iso(),
        }

    # -- Formular mit vorhandenen Werten vorbelegen (Bearbeiten-Modus) --
    def set_data(self, member: dict):
        self.anrede.setCurrentText(member.get("Anrede", ""))
        self.vorname.setText(member.get("Vorname", ""))
        self.nachname.setText(member.get("Nachname", ""))
        self.email.setText(member.get("E-Mail", ""))
        self.telefon.setText(member.get("Telefon", ""))
        self.mitgliedsnummer.setText(member.get("Mitgliedsnummer", ""))
        self.strasse.setText(member.get("Straße", ""))
        self.plz.setText(member.get("PLZ", ""))
        self.stadt.setText(member.get("Stadt", ""))
        self.geburtstag.set_iso(member.get("Geburtstag", ""))
        eintritt = _iso_to_qdate(member.get("Eintrittsdatum", ""))
        self.eintrittsdatum.setDate(eintritt or QDate.currentDate())
        self.austrittsdatum.set_iso(member.get("Austrittsdatum", ""))

        vorhandene_gruppen = [g.strip() for g in member.get("Gruppen", "").split(";") if g.strip()]
        for i in range(self.gruppen_list.count()):
            item = self.gruppen_list.item(i)
            item.setCheckState(Qt.Checked if item.text() in vorhandene_gruppen else Qt.Unchecked)

        status = member.get("Mitgliedsstatus", "")
        if status in mitglieder.STATUS_OPTIONEN:
            self.status.setCurrentText(status)
        self.dkv.setText(member.get("DKV-Nummer", ""))
        self.nwdv.setText(member.get("NWDV-Nummer", ""))
        self.gameshot.setText(member.get("Game-Shot-Nummer", ""))
        self.funktion.setText(member.get("Funktion", ""))
        self.einwilligung.setChecked(member.get("Einwilligung_Fotos_Daten", "") == "Ja")
        self.einwilligung_datum.set_iso(member.get("Einwilligung_Datum", ""))
        self.vertreter_name.setText(member.get("Vertreter_Name", ""))
        self.vertreter_telefon.setText(member.get("Vertreter_Telefon", ""))
        self.vertreter_email.setText(member.get("Vertreter_E-Mail", ""))
        self.notizen.setPlainText(member.get("Notizen", ""))
        rhythmus = member.get("Zahlungsrhythmus", "")
        if rhythmus in mitglieder.ZAHLUNGSRHYTHMUS_OPTIONEN:
            self.zahlungsrhythmus.setCurrentText(rhythmus)
        try:
            self.beitragsbetrag.setValue(float(member.get("Beitragsbetrag") or 0))
        except (TypeError, ValueError):
            self.beitragsbetrag.setValue(0)
        self.letzte_zahlung.set_iso(member.get("Letzte_Zahlung", ""))
        self.iban.setText(member.get("IBAN", ""))
        self.kontoinhaber.setText(member.get("Kontoinhaber", ""))
        self.sepa_referenz.setText(member.get("SEPA_Mandatsreferenz", ""))
        self.sepa_datum.set_iso(member.get("SEPA_Mandatsdatum", ""))
        self._update_naechste_faellig()


# ---------------------------------------------------------------------------
# Bearbeiten-Dialog (Foto, Anhänge, Mail-Verlauf, Exporte, Löschen)
# ---------------------------------------------------------------------------
class MemberEditDialog(QDialog):
    def __init__(self, parent, mitglied_id: str, member: dict):
        super().__init__(parent)
        self.mitglied_id = mitglied_id
        self.setWindowTitle(f"Bearbeiten: {member.get('Vorname', '')} {member.get('Nachname', '')}")
        self.resize(700, 800)
        self._deleted = False

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, stretch=1)

        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)

        self.form = MemberFormWidget()
        self.form.set_data(member)
        content_layout.addWidget(self.form)

        # --- Foto ---
        foto_box = QGroupBox("Foto")
        foto_layout = QHBoxLayout(foto_box)
        self.foto_label = QLabel()
        self.foto_label.setFixedSize(120, 120)
        self.foto_label.setStyleSheet("border: 1px solid gray;")
        self.foto_label.setAlignment(Qt.AlignCenter)
        foto_layout.addWidget(self.foto_label)
        foto_btns = QVBoxLayout()
        self.foto_waehlen_btn = QPushButton("Foto auswählen...")
        self.foto_waehlen_btn.clicked.connect(self._foto_auswaehlen)
        self.foto_loeschen_btn = QPushButton("Foto löschen")
        self.foto_loeschen_btn.clicked.connect(self._foto_loeschen)
        foto_btns.addWidget(self.foto_waehlen_btn)
        foto_btns.addWidget(self.foto_loeschen_btn)
        foto_layout.addLayout(foto_btns)
        content_layout.addWidget(foto_box)
        self._foto_aktualisieren()

        # --- Anhänge ---
        anhang_box = QGroupBox("Anhänge")
        anhang_layout = QVBoxLayout(anhang_box)
        self.anhang_list = QListWidget()
        anhang_layout.addWidget(self.anhang_list)
        anhang_btns = QHBoxLayout()
        self.anhang_hinzufuegen_btn = QPushButton("Anhang hinzufügen...")
        self.anhang_hinzufuegen_btn.clicked.connect(self._anhang_hinzufuegen)
        self.anhang_oeffnen_btn = QPushButton("Öffnen")
        self.anhang_oeffnen_btn.clicked.connect(self._anhang_oeffnen)
        self.anhang_loeschen_btn = QPushButton("Löschen")
        self.anhang_loeschen_btn.clicked.connect(self._anhang_loeschen)
        anhang_btns.addWidget(self.anhang_hinzufuegen_btn)
        anhang_btns.addWidget(self.anhang_oeffnen_btn)
        anhang_btns.addWidget(self.anhang_loeschen_btn)
        anhang_layout.addLayout(anhang_btns)
        content_layout.addWidget(anhang_box)
        self._anhaenge_aktualisieren()

        # --- Mail-Verlauf ---
        mail_box = QGroupBox("Mail-Verlauf")
        mail_layout = QVBoxLayout(mail_box)
        self.mail_list = QListWidget()
        mail_layout.addWidget(self.mail_list)
        content_layout.addWidget(mail_box)
        self._mail_log_aktualisieren()

        # --- Zahlung erfassen ---
        zahlung_box = QGroupBox("Zahlung erfassen")
        zahlung_layout = QVBoxLayout(zahlung_box)
        zahlung_form = QFormLayout()
        self.zahlung_datum = QDateEdit()
        self.zahlung_datum.setCalendarPopup(True)
        self.zahlung_datum.setDisplayFormat("dd.MM.yyyy")
        self.zahlung_datum.setMinimumDate(QDate(1900, 1, 1))
        self.zahlung_datum.setMaximumDate(QDate(2100, 12, 31))
        self.zahlung_datum.setDate(QDate.currentDate())
        zahlung_form.addRow("Datum:", self.zahlung_datum)
        self.zahlung_betrag = QDoubleSpinBox()
        self.zahlung_betrag.setRange(0, 100000)
        self.zahlung_betrag.setDecimals(2)
        self.zahlung_betrag.setSingleStep(0.5)
        self.zahlung_betrag.setSuffix(" €")
        try:
            self.zahlung_betrag.setValue(float(member.get("Beitragsbetrag") or 0))
        except (TypeError, ValueError):
            pass
        zahlung_form.addRow("Betrag:", self.zahlung_betrag)
        self.zahlung_art = QComboBox()
        self.zahlung_art.addItems(mitglieder.ZAHLUNGSART_OPTIONEN)
        zahlung_form.addRow("Zahlungsart:", self.zahlung_art)
        self.zahlung_notiz = QLineEdit()
        zahlung_form.addRow("Notiz (optional):", self.zahlung_notiz)
        zahlung_layout.addLayout(zahlung_form)
        self.zahlung_erfassen_btn = QPushButton("Zahlung erfassen")
        self.zahlung_erfassen_btn.clicked.connect(self._zahlung_erfassen)
        zahlung_layout.addWidget(self.zahlung_erfassen_btn)

        self.zahlungsverlauf_list = QListWidget()
        zahlung_layout.addWidget(QLabel("Zahlungsverlauf:"))
        zahlung_layout.addWidget(self.zahlungsverlauf_list)
        content_layout.addWidget(zahlung_box)
        self._zahlungsverlauf_aktualisieren()

        # --- Exporte ---
        export_box = QGroupBox("Export")
        export_layout = QHBoxLayout(export_box)
        self.vcard_btn = QPushButton("📇 vCard exportieren")
        self.vcard_btn.clicked.connect(self._vcard_exportieren)
        self.ausweis_btn = QPushButton("🪪 Mitgliedsausweis (PDF)")
        self.ausweis_btn.clicked.connect(self._ausweis_exportieren)
        self.sepa_btn = QPushButton("🏦 SEPA-Mandat (PDF)")
        self.sepa_btn.clicked.connect(self._sepa_mandat_exportieren)
        export_layout.addWidget(self.vcard_btn)
        export_layout.addWidget(self.ausweis_btn)
        export_layout.addWidget(self.sepa_btn)
        content_layout.addWidget(export_box)

        # --- Löschen ---
        self.loeschen_btn = QPushButton("Mitglied löschen")
        self.loeschen_btn.setStyleSheet("color: darkred;")
        self.loeschen_btn.clicked.connect(self._mitglied_loeschen)
        content_layout.addWidget(self.loeschen_btn)

        # --- Dialog-Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._speichern)
        self.button_box.rejected.connect(self.reject)
        outer.addWidget(self.button_box)

    # -- aktueller DataFrame-Zugriff --
    def _current_member(self) -> dict | None:
        df = mitglieder.load_data()
        treffer = df[df["ID"] == self.mitglied_id]
        return treffer.iloc[0] if not treffer.empty else None

    def _foto_aktualisieren(self):
        from PyQt5.QtGui import QPixmap

        pfad = mitglieder.get_photo_path(self.mitglied_id)
        if pfad and pfad.exists():
            pix = QPixmap(str(pfad))
            self.foto_label.setPixmap(pix.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.foto_label.setPixmap(QPixmap())
            self.foto_label.setText("Kein Foto")

    def _foto_auswaehlen(self):
        pfad, _ = QFileDialog.getOpenFileName(self, "Foto auswählen", "", "Bilder (*.jpg *.jpeg *.png)")
        if not pfad:
            return
        mitglieder.save_photo(self.mitglied_id, LocalUploadedFile(pfad))
        self._foto_aktualisieren()

    def _foto_loeschen(self):
        mitglieder.delete_photo(self.mitglied_id)
        self._foto_aktualisieren()

    def _anhaenge_aktualisieren(self):
        self.anhang_list.clear()
        for pfad in mitglieder.list_attachments(self.mitglied_id):
            item = QListWidgetItem(pfad.name)
            item.setData(Qt.UserRole, str(pfad))
            self.anhang_list.addItem(item)

    def _anhang_hinzufuegen(self):
        pfade, _ = QFileDialog.getOpenFileNames(self, "Anhänge hinzufügen")
        if not pfade:
            return
        fehler = []
        for pfad in pfade:
            uploaded = LocalUploadedFile(pfad)
            fehlermeldung = mitglieder.validate_attachment(uploaded)
            if fehlermeldung:
                fehler.append(f"{Path(pfad).name}: {fehlermeldung}")
            else:
                mitglieder.save_attachment(self.mitglied_id, uploaded)
        if fehler:
            QMessageBox.warning(self, "Nicht alle Anhänge gespeichert", "\n".join(fehler))
        self._anhaenge_aktualisieren()

    def _anhang_oeffnen(self):
        item = self.anhang_list.currentItem()
        if not item:
            return
        import os

        os.startfile(item.data(Qt.UserRole))

    def _anhang_loeschen(self):
        item = self.anhang_list.currentItem()
        if not item:
            return
        mitglieder.delete_attachment(self.mitglied_id, item.text())
        self._anhaenge_aktualisieren()

    def _mail_log_aktualisieren(self):
        self.mail_list.clear()
        eintraege = mitglieder.list_mail_log(self.mitglied_id)
        if not eintraege:
            self.mail_list.addItem("Noch keine Serienmail an dieses Mitglied gesendet.")
            return
        for eintrag in eintraege:
            symbol = "✔" if eintrag.get("erfolgreich") else "✘"
            text = f"{symbol} {eintrag.get('betreff', '')} — {eintrag.get('zeitstempel', '')}"
            if not eintrag.get("erfolgreich") and eintrag.get("fehler"):
                text += f" (Fehler: {eintrag['fehler']})"
            self.mail_list.addItem(text)

    def _zahlungsverlauf_aktualisieren(self):
        self.zahlungsverlauf_list.clear()
        eintraege = mitglieder.list_zahlungen(self.mitglied_id)
        if not eintraege:
            self.zahlungsverlauf_list.addItem("Noch keine Zahlung erfasst.")
            return
        for eintrag in eintraege:
            text = (
                f"{eintrag.get('datum', '')} — {eintrag.get('betrag', '')} € "
                f"({eintrag.get('zahlungsart', '')})"
            )
            if eintrag.get("notiz"):
                text += f" — {eintrag['notiz']}"
            self.zahlungsverlauf_list.addItem(text)

    def _zahlung_erfassen(self):
        if self.zahlung_betrag.value() <= 0:
            QMessageBox.warning(self, "Eingabefehler", "Bitte einen Betrag größer als 0 € eingeben.")
            return
        datum_iso = _qdate_to_iso(self.zahlung_datum.date())
        mitglieder.log_zahlung(
            self.mitglied_id,
            str(self.zahlung_betrag.value()),
            datum_iso,
            self.zahlung_art.currentText(),
            self.zahlung_notiz.text().strip(),
        )
        # Nur Letzte_Zahlung wird aktualisiert (verschiebt die nächste
        # Fälligkeit) - der laufende Beitragsbetrag bleibt unangetastet, auch
        # wenn eine Zahlung z. B. wegen einer Nachzahlung/Teilzahlung von
        # diesem Betrag abweicht. Der tatsächlich gezahlte Betrag steht im
        # Zahlungsverlauf.
        df = mitglieder.load_data()
        aktualisiert = mitglieder.update_member(df, self.mitglied_id, {"Letzte_Zahlung": datum_iso})
        mitglieder.save_data(aktualisiert)
        self.zahlung_notiz.clear()
        self.form.letzte_zahlung.set_iso(datum_iso)
        self._zahlungsverlauf_aktualisieren()
        QMessageBox.information(self, "Erfolg", "Zahlung wurde erfasst.")

    def _vcard_exportieren(self):
        member = self._current_member()
        if member is None:
            return
        ziel, _ = QFileDialog.getSaveFileName(
            self, "vCard speichern", f"{member['Vorname']}_{member['Nachname']}.vcf", "vCard (*.vcf)"
        )
        if ziel:
            Path(ziel).write_text(mitglieder.build_vcard(member), encoding="utf-8")
            QMessageBox.information(self, "Erfolg", "vCard wurde gespeichert.")

    def _sepa_mandat_exportieren(self):
        member = self._current_member()
        if member is None:
            return
        ziel, _ = QFileDialog.getSaveFileName(
            self, "SEPA-Mandat speichern",
            f"sepa_mandat_{member['Vorname']}_{member['Nachname']}.pdf", "PDF (*.pdf)",
        )
        if ziel:
            Path(ziel).write_bytes(mitglieder.build_sepa_mandat_pdf(member))
            QMessageBox.information(self, "Erfolg", "SEPA-Mandat wurde gespeichert.")

    def _ausweis_exportieren(self):
        member = self._current_member()
        if member is None:
            return
        ziel, _ = QFileDialog.getSaveFileName(
            self, "Mitgliedsausweis speichern", f"ausweis_{member['Vorname']}_{member['Nachname']}.pdf", "PDF (*.pdf)"
        )
        if ziel:
            Path(ziel).write_bytes(mitglieder.build_mitgliedsausweis(member))
            QMessageBox.information(self, "Erfolg", "Mitgliedsausweis wurde gespeichert.")

    def _mitglied_loeschen(self):
        member = self._current_member()
        name = f"{member['Vorname']} {member['Nachname']}" if member is not None else self.mitglied_id
        antwort = QMessageBox.question(
            self,
            "Löschen bestätigen",
            f"Wirklich {name} inkl. Foto und Anhängen endgültig löschen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return
        df = mitglieder.load_data()
        aktualisiert = mitglieder.delete_member(df, self.mitglied_id)
        mitglieder.save_data(aktualisiert)
        self._deleted = True
        self.accept()

    def _speichern(self):
        if self._deleted:
            self.accept()
            return
        df = mitglieder.load_data()
        data = self.form.get_data()
        fehler = mitglieder.validate_member(data, df, editing_id=self.mitglied_id)
        if fehler:
            QMessageBox.warning(self, "Eingabefehler", "\n".join(f"- {f}" for f in fehler))
            return
        aktualisiert = mitglieder.update_member(df, self.mitglied_id, data)
        mitglieder.save_data(aktualisiert)
        self.accept()


# ---------------------------------------------------------------------------
# Übersicht (Tabelle + Filter + Metriken + Geburtstage/Jubiläen)
# ---------------------------------------------------------------------------
class UebersichtPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)

        self.metrics_label = QLabel()
        layout.addWidget(self.metrics_label)

        self.gruppen_metrics_label = QLabel()
        layout.addWidget(self.gruppen_metrics_label)

        anstehend_layout = QHBoxLayout()
        geb_box = QGroupBox("Geburtstage (nächste 30 Tage)")
        geb_layout = QVBoxLayout(geb_box)
        self.geburtstage_list = QListWidget()
        geb_layout.addWidget(self.geburtstage_list)
        anstehend_layout.addWidget(geb_box)

        jub_box = QGroupBox("Mitgliedschaftsjubiläen (dieses Jahr)")
        jub_layout = QVBoxLayout(jub_box)
        self.jubilaeen_list = QListWidget()
        jub_layout.addWidget(self.jubilaeen_list)
        anstehend_layout.addWidget(jub_box)
        layout.addLayout(anstehend_layout)

        filter_layout = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Alle"] + mitglieder.STATUS_OPTIONEN)
        self.status_filter.currentTextChanged.connect(self.refresh_table)
        self.gruppe_filter = QComboBox()
        self.gruppe_filter.addItems(["Alle"] + mitglieder.GRUPPEN_OPTIONEN)
        self.gruppe_filter.currentTextChanged.connect(self.refresh_table)
        self.suche_edit = QLineEdit()
        self.suche_edit.setPlaceholderText("Suche (Name)")
        self.suche_edit.textChanged.connect(self.refresh_table)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.status_filter)
        filter_layout.addWidget(QLabel("Gruppe:"))
        filter_layout.addWidget(self.gruppe_filter)
        filter_layout.addWidget(self.suche_edit)
        layout.addLayout(filter_layout)

        anzeige_spalten = [c for c in COLUMNS if c != "ID"]
        self.anzeige_spalten = anzeige_spalten
        self.table = QTableWidget()
        self.table.setColumnCount(len(anzeige_spalten))
        self.table.setHorizontalHeaderLabels(anzeige_spalten)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self.edit_selected)
        layout.addWidget(self.table, stretch=1)

        btn_layout = QHBoxLayout()
        self.bearbeiten_btn = QPushButton("Bearbeiten (Doppelklick)")
        self.bearbeiten_btn.clicked.connect(self.edit_selected)
        self.excel_export_btn = QPushButton("📊 Als Excel exportieren")
        self.excel_export_btn.clicked.connect(self.excel_exportieren)
        self.pdf_export_btn = QPushButton("📄 Als PDF exportieren")
        self.pdf_export_btn.clicked.connect(self.pdf_exportieren)
        btn_layout.addWidget(self.bearbeiten_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.excel_export_btn)
        btn_layout.addWidget(self.pdf_export_btn)
        layout.addLayout(btn_layout)

    def _gefiltertes_df(self):
        df = mitglieder.load_data()
        if self.status_filter.currentText() != "Alle":
            df = df[df["Mitgliedsstatus"] == self.status_filter.currentText()]
        if self.gruppe_filter.currentText() != "Alle":
            df = df[df["Gruppen"].str.contains(self.gruppe_filter.currentText(), na=False)]
        suche = self.suche_edit.text().strip()
        if suche:
            maske = (
                df["Vorname"].str.contains(suche, case=False, na=False)
                | df["Nachname"].str.contains(suche, case=False, na=False)
            )
            df = df[maske]
        return df

    def refresh_table(self):
        df_gesamt = mitglieder.load_data()
        gesamt = len(df_gesamt)
        status_zahlen = mitglieder.status_anzahl(df_gesamt)
        teile = [f"Gesamt: {gesamt}"] + [f"{status.capitalize()}: {anzahl}" for status, anzahl in status_zahlen.items()]
        self.metrics_label.setText("   |   ".join(teile))

        gruppen_zahlen = {
            gruppe: int(df_gesamt["Gruppen"].str.contains(gruppe, na=False).sum())
            for gruppe in ["Aktive Mitglieder", "Fördernde Mitglieder"]
        }
        self.gruppen_metrics_label.setText(
            "   |   ".join(f"{gruppe}: {anzahl}" for gruppe, anzahl in gruppen_zahlen.items())
        )

        self.geburtstage_list.clear()
        geb_df = mitglieder.naechste_geburtstage(df_gesamt)
        if geb_df.empty:
            self.geburtstage_list.addItem("Keine anstehenden Geburtstage.")
        else:
            for _, zeile in geb_df.iterrows():
                self.geburtstage_list.addItem(f"{zeile['Name']} — {zeile['Datum']} (in {zeile['In Tagen']} Tagen)")

        self.jubilaeen_list.clear()
        jub_df = mitglieder.mitgliedschaftsjubilaeen(df_gesamt)
        if jub_df.empty:
            self.jubilaeen_list.addItem("Keine Jubiläen dieses Jahr.")
        else:
            for _, zeile in jub_df.iterrows():
                self.jubilaeen_list.addItem(f"{zeile['Name']} — {zeile['Jahre dabei']} Jahre dabei")

        gefiltert = self._gefiltertes_df().reset_index(drop=True)
        self._gefiltert_ids = gefiltert["ID"].tolist()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(gefiltert))
        for row, (_, member) in enumerate(gefiltert.iterrows()):
            for col, spalte in enumerate(self.anzeige_spalten):
                self.table.setItem(row, col, QTableWidgetItem(str(member.get(spalte, ""))))
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def _selected_member_id(self) -> str | None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        # Name-basierter Rückbezug ist unzuverlässig bei Sortierung -> stattdessen
        # Vor-/Nachname + Mitgliedsnummer aus der Zeile lesen und im DataFrame nachschlagen.
        vorname_idx = self.anzeige_spalten.index("Vorname")
        nachname_idx = self.anzeige_spalten.index("Nachname")
        nummer_idx = self.anzeige_spalten.index("Mitgliedsnummer")
        vorname = self.table.item(row, vorname_idx).text()
        nachname = self.table.item(row, nachname_idx).text()
        nummer = self.table.item(row, nummer_idx).text()
        df = mitglieder.load_data()
        treffer = df[(df["Vorname"] == vorname) & (df["Nachname"] == nachname) & (df["Mitgliedsnummer"] == nummer)]
        if treffer.empty:
            return None
        return treffer.iloc[0]["ID"]

    def edit_selected(self):
        mitglied_id = self._selected_member_id()
        if not mitglied_id:
            QMessageBox.information(self, "Auswahl fehlt", "Bitte wählen Sie ein Mitglied zum Bearbeiten.")
            return
        df = mitglieder.load_data()
        treffer = df[df["ID"] == mitglied_id]
        if treffer.empty:
            QMessageBox.critical(self, "Fehler", "Mitglied nicht gefunden.")
            return
        dlg = MemberEditDialog(self, mitglied_id, treffer.iloc[0].to_dict())
        if dlg.exec_() == QDialog.Accepted:
            self.refresh_table()

    def excel_exportieren(self):
        ziel, _ = QFileDialog.getSaveFileName(self, "Excel exportieren", "mitglieder.xlsx", "Excel (*.xlsx)")
        if ziel:
            Path(ziel).write_bytes(mitglieder.export_excel(self._gefiltertes_df()))
            QMessageBox.information(self, "Erfolg", "Excel-Export wurde gespeichert.")

    def pdf_exportieren(self):
        ziel, _ = QFileDialog.getSaveFileName(self, "PDF exportieren", "mitglieder.pdf", "PDF (*.pdf)")
        if ziel:
            Path(ziel).write_bytes(mitglieder.export_pdf(self._gefiltertes_df()))
            QMessageBox.information(self, "Erfolg", "PDF-Export wurde gespeichert.")


# ---------------------------------------------------------------------------
# Neues Mitglied
# ---------------------------------------------------------------------------
class NeuesMitgliedPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        outer = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, stretch=1)
        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)

        self.form = MemberFormWidget()
        content_layout.addWidget(self.form)

        foto_box = QGroupBox("Foto (optional)")
        foto_layout = QHBoxLayout(foto_box)
        self.foto_pfad = None
        self.foto_pfad_label = QLabel("Kein Foto ausgewählt")
        foto_waehlen_btn = QPushButton("Foto auswählen...")
        foto_waehlen_btn.clicked.connect(self._foto_auswaehlen)
        foto_layout.addWidget(self.foto_pfad_label, stretch=1)
        foto_layout.addWidget(foto_waehlen_btn)
        content_layout.addWidget(foto_box)

        anhang_box = QGroupBox("Anhänge (optional)")
        anhang_layout = QVBoxLayout(anhang_box)
        self.anhang_liste = []
        self.anhang_label = QLabel("Keine Anhänge ausgewählt")
        anhang_waehlen_btn = QPushButton("Anhänge auswählen...")
        anhang_waehlen_btn.clicked.connect(self._anhaenge_auswaehlen)
        anhang_layout.addWidget(self.anhang_label)
        anhang_layout.addWidget(anhang_waehlen_btn)
        content_layout.addWidget(anhang_box)

        self.hinzufuegen_btn = QPushButton("Mitglied hinzufügen")
        self.hinzufuegen_btn.clicked.connect(self._hinzufuegen)
        outer.addWidget(self.hinzufuegen_btn)

    def _foto_auswaehlen(self):
        pfad, _ = QFileDialog.getOpenFileName(self, "Foto auswählen", "", "Bilder (*.jpg *.jpeg *.png)")
        if pfad:
            self.foto_pfad = pfad
            self.foto_pfad_label.setText(Path(pfad).name)

    def _anhaenge_auswaehlen(self):
        pfade, _ = QFileDialog.getOpenFileNames(self, "Anhänge auswählen")
        if pfade:
            self.anhang_liste = pfade
            self.anhang_label.setText(f"{len(pfade)} Datei(en) ausgewählt")

    def _hinzufuegen(self):
        df = mitglieder.load_data()
        data = self.form.get_data()
        fehler = mitglieder.validate_member(data, df)

        anhang_uploads = [LocalUploadedFile(p) for p in self.anhang_liste]
        for upload in anhang_uploads:
            fehlermeldung = mitglieder.validate_attachment(upload)
            if fehlermeldung:
                fehler.append(fehlermeldung)

        if fehler:
            QMessageBox.warning(self, "Eingabefehler", "\n".join(f"- {f}" for f in fehler))
            return

        neuer_df = mitglieder.add_member(df, data)
        neue_id = neuer_df.iloc[-1]["ID"]
        if self.foto_pfad:
            mitglieder.save_photo(neue_id, LocalUploadedFile(self.foto_pfad))
        for upload in anhang_uploads:
            mitglieder.save_attachment(neue_id, upload)
        mitglieder.save_data(neuer_df)

        QMessageBox.information(self, "Erfolg", f"Mitglied {data['Vorname']} {data['Nachname']} wurde hinzugefügt.")
        self._formular_zuruecksetzen()
        self.main_window.zeige_uebersicht()

    def _formular_zuruecksetzen(self):
        neues_form = MemberFormWidget()
        layout = self.form.parentWidget().layout()
        layout.replaceWidget(self.form, neues_form)
        self.form.deleteLater()
        self.form = neues_form
        self.foto_pfad = None
        self.foto_pfad_label.setText("Kein Foto ausgewählt")
        self.anhang_liste = []
        self.anhang_label.setText("Keine Anhänge ausgewählt")


# ---------------------------------------------------------------------------
# Serienmail
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Gemeinsamer Versand-Loop (Serienmail + Beitragsmahnung nutzen denselben Ablauf)
# ---------------------------------------------------------------------------
def _versende_serienmails(smtp_config: dict, ids: list[str], df, betreff_vorlage: str, text_vorlage: str, pdf_anhaengen: bool) -> tuple[int, list[str]]:
    """Verschickt an jede der übergebenen Mitglieds-IDs eine personalisierte
    Mail, loggt jeden Versand (mitglieder.log_mail) und pausiert zwischen den
    Sends (mailer.SERIENMAIL_PAUSE_SEKUNDEN), damit Anbieter-Rate-Limits nicht
    greifen. Gibt (Anzahl erfolgreich, Liste Fehlermeldungen) zurück."""
    erfolgreich = 0
    fehlgeschlagen = []
    for mitglied_id in ids:
        treffer = df[df["ID"] == mitglied_id]
        if treffer.empty:
            continue
        member = treffer.iloc[0]
        empfaenger = member.get("E-Mail", "")
        betreff = mitglieder.fuelle_platzhalter(betreff_vorlage, member)
        text = mitglieder.fuelle_platzhalter(text_vorlage, member)
        try:
            if not empfaenger:
                raise ValueError("Keine E-Mail-Adresse hinterlegt.")
            anhang_bytes = None
            if pdf_anhaengen:
                anhang_bytes = mitglieder.build_serienbrief_pdf(member, betreff, text)
            mailer.send_mail(smtp_config, empfaenger, betreff, text, anhang_bytes=anhang_bytes, anhang_dateiname="anschreiben.pdf")
            mitglieder.log_mail(mitglied_id, betreff, empfaenger, erfolgreich=True)
            erfolgreich += 1
        except Exception as exc:
            mitglieder.log_mail(mitglied_id, betreff, empfaenger, erfolgreich=False, fehler=str(exc))
            fehlgeschlagen.append(f"{member['Vorname']} {member['Nachname']}: {exc}")
        time.sleep(mailer.SERIENMAIL_PAUSE_SEKUNDEN)
    return erfolgreich, fehlgeschlagen


class SerienmailPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)

        info = QLabel(
            "Versand über ein bestehendes E-Mail-Konto (SMTP). Platzhalter wie "
            "{Vorname}, {Nachname}, {Mitgliedsnummer} werden je Mitglied ersetzt."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        smtp_btn = QPushButton("SMTP-Einstellungen...")
        smtp_btn.clicked.connect(self._smtp_einstellungen)
        layout.addWidget(smtp_btn)

        anzeige_spalten = [c for c in COLUMNS if c != "ID"]
        self.anzeige_spalten = anzeige_spalten
        self.table = QTableWidget()
        self.table.setColumnCount(len(anzeige_spalten))
        self.table.setHorizontalHeaderLabels(anzeige_spalten)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        self.auswahl_label = QLabel("0 Mitglied(er) ausgewählt.")
        self.table.itemSelectionChanged.connect(self._auswahl_aktualisieren)
        layout.addWidget(self.auswahl_label)

        form_box = QGroupBox("Serienmail")
        form_layout = QFormLayout(form_box)
        self.betreff_edit = QLineEdit()
        form_layout.addRow("Betreff:", self.betreff_edit)
        self.text_edit = QTextEdit()
        self.text_edit.setMinimumHeight(150)
        form_layout.addRow("Text:", self.text_edit)
        self.pdf_anhaengen_check = QCheckBox("Text zusätzlich als PDF anhängen")
        form_layout.addRow(self.pdf_anhaengen_check)
        layout.addWidget(form_box)

        self.versenden_btn = QPushButton("Serienmail versenden")
        self.versenden_btn.clicked.connect(self._versenden)
        layout.addWidget(self.versenden_btn)

    def refresh_table(self):
        df = mitglieder.load_data()
        self.table.setRowCount(len(df))
        for row, (_, member) in enumerate(df.iterrows()):
            for col, spalte in enumerate(self.anzeige_spalten):
                self.table.setItem(row, col, QTableWidgetItem(str(member.get(spalte, ""))))
        self.table.resizeColumnsToContents()

    def _auswahl_aktualisieren(self):
        anzahl = len(self.table.selectionModel().selectedRows())
        self.auswahl_label.setText(f"{anzahl} Mitglied(er) ausgewählt.")

    def _selected_member_ids(self) -> list[str]:
        df = mitglieder.load_data()
        vorname_idx = self.anzeige_spalten.index("Vorname")
        nachname_idx = self.anzeige_spalten.index("Nachname")
        nummer_idx = self.anzeige_spalten.index("Mitgliedsnummer")
        ids = []
        for index in self.table.selectionModel().selectedRows():
            row = index.row()
            vorname = self.table.item(row, vorname_idx).text()
            nachname = self.table.item(row, nachname_idx).text()
            nummer = self.table.item(row, nummer_idx).text()
            treffer = df[(df["Vorname"] == vorname) & (df["Nachname"] == nachname) & (df["Mitgliedsnummer"] == nummer)]
            if not treffer.empty:
                ids.append(treffer.iloc[0]["ID"])
        return ids

    def _smtp_einstellungen(self):
        dlg = SmtpSettingsDialog(self)
        dlg.exec_()

    def _versenden(self):
        ausgewaehlte_ids = self._selected_member_ids()
        betreff_vorlage = self.betreff_edit.text()
        text_vorlage = self.text_edit.toPlainText()

        if not ausgewaehlte_ids:
            QMessageBox.warning(self, "Fehler", "Bitte mindestens ein Mitglied auswählen.")
            return
        if not betreff_vorlage.strip() or not text_vorlage.strip():
            QMessageBox.warning(self, "Fehler", "Betreff und Text dürfen nicht leer sein.")
            return

        try:
            smtp_config = mailer.smtp_konfiguration(adapter.smtp_secrets_wrapper())
        except mailer.SmtpNichtKonfiguriert as exc:
            QMessageBox.critical(self, "SMTP nicht konfiguriert", str(exc))
            return

        df = mitglieder.load_data()
        erfolgreich, fehlgeschlagen = _versende_serienmails(
            smtp_config, ausgewaehlte_ids, df, betreff_vorlage, text_vorlage, self.pdf_anhaengen_check.isChecked()
        )

        meldung = []
        if erfolgreich:
            meldung.append(f"{erfolgreich} Mail(s) erfolgreich versendet.")
        if fehlgeschlagen:
            meldung.append(f"{len(fehlgeschlagen)} Mail(s) fehlgeschlagen:\n" + "\n".join(f"- {f}" for f in fehlgeschlagen))
        QMessageBox.information(self, "Serienmail", "\n\n".join(meldung) if meldung else "Nichts versendet.")


class SmtpSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SMTP-Einstellungen")
        layout = QFormLayout(self)

        config = adapter.load_smtp_config()
        self.host_edit = QLineEdit(config.get("host", ""))
        self.port_edit = QLineEdit(str(config.get("port", "587")))
        self.user_edit = QLineEdit(config.get("user", ""))
        self.passwort_edit = QLineEdit(config.get("passwort", ""))
        self.passwort_edit.setEchoMode(QLineEdit.Password)
        self.absender_edit = QLineEdit(config.get("absender", ""))
        self.kassierer_edit = QLineEdit(config.get("kassierer_email", ""))

        layout.addRow("Host:", self.host_edit)
        layout.addRow("Port:", self.port_edit)
        layout.addRow("Benutzer:", self.user_edit)
        layout.addRow("Passwort:", self.passwort_edit)
        layout.addRow("Absender:", self.absender_edit)
        layout.addRow("Kassierer-E-Mail (für Beitragsmahnung):", self.kassierer_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._speichern)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def _speichern(self):
        adapter.save_smtp_config({
            "host": self.host_edit.text().strip(),
            "port": self.port_edit.text().strip(),
            "user": self.user_edit.text().strip(),
            "passwort": self.passwort_edit.text(),
            "absender": self.absender_edit.text().strip(),
            "kassierer_email": self.kassierer_edit.text().strip(),
        })
        self.accept()


# ---------------------------------------------------------------------------
# Beitragsmahnung
# ---------------------------------------------------------------------------
class BeitragsmahnungPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)

        info = QLabel(
            "Zeigt alle Mitglieder, deren nächste Beitragsfälligkeit (berechnet "
            "aus letzter Zahlung + Zahlungsrhythmus) erreicht oder überschritten "
            "ist. Platzhalter wie {Vorname}, {Beitragsbetrag}, "
            "{Faelligkeitsdatum} werden je Mitglied ersetzt."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        smtp_btn = QPushButton("SMTP-Einstellungen...")
        smtp_btn.clicked.connect(self._smtp_einstellungen)
        btn_row.addWidget(smtp_btn)
        self.kassierer_btn = QPushButton("Kassierer benachrichtigen")
        self.kassierer_btn.clicked.connect(self._kassierer_benachrichtigen)
        btn_row.addWidget(self.kassierer_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        anzeige_spalten = [c for c in COLUMNS if c != "ID"] + ["Faelligkeitsdatum"]
        self.anzeige_spalten = anzeige_spalten
        self.table = QTableWidget()
        self.table.setColumnCount(len(anzeige_spalten))
        self.table.setHorizontalHeaderLabels(anzeige_spalten)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        self.auswahl_label = QLabel("0 Mitglied(er) ausgewählt.")
        self.table.itemSelectionChanged.connect(self._auswahl_aktualisieren)
        layout.addWidget(self.auswahl_label)

        form_box = QGroupBox("Beitragsmahnung")
        form_layout = QFormLayout(form_box)
        self.betreff_edit = QLineEdit("Erinnerung: Mitgliedsbeitrag fällig")
        form_layout.addRow("Betreff:", self.betreff_edit)
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(
            "Hallo {Vorname},\n\n"
            "dein Mitgliedsbeitrag in Höhe von {Beitragsbetrag} € war am "
            "{Faelligkeitsdatum} fällig. Bitte überweise den Betrag zeitnah.\n\n"
            "Vielen Dank!"
        )
        self.text_edit.setMinimumHeight(150)
        form_layout.addRow("Text:", self.text_edit)
        self.pdf_anhaengen_check = QCheckBox("Text zusätzlich als PDF anhängen")
        form_layout.addRow(self.pdf_anhaengen_check)
        layout.addWidget(form_box)

        self.versenden_btn = QPushButton("Beitragsmahnung versenden")
        self.versenden_btn.clicked.connect(self._versenden)
        layout.addWidget(self.versenden_btn)

    def _faellig_df(self):
        return mitglieder.faellige_mitglieder(mitglieder.load_data())

    def refresh_table(self):
        faellig_df = self._faellig_df()
        self.table.setRowCount(len(faellig_df))
        for row, (_, member) in enumerate(faellig_df.iterrows()):
            for col, spalte in enumerate(self.anzeige_spalten):
                self.table.setItem(row, col, QTableWidgetItem(str(member.get(spalte, ""))))
        self.table.resizeColumnsToContents()

    def _auswahl_aktualisieren(self):
        anzahl = len(self.table.selectionModel().selectedRows())
        self.auswahl_label.setText(f"{anzahl} Mitglied(er) ausgewählt.")

    def _selected_member_ids(self) -> list[str]:
        faellig_df = self._faellig_df()
        vorname_idx = self.anzeige_spalten.index("Vorname")
        nachname_idx = self.anzeige_spalten.index("Nachname")
        nummer_idx = self.anzeige_spalten.index("Mitgliedsnummer")
        ids = []
        for index in self.table.selectionModel().selectedRows():
            row = index.row()
            vorname = self.table.item(row, vorname_idx).text()
            nachname = self.table.item(row, nachname_idx).text()
            nummer = self.table.item(row, nummer_idx).text()
            treffer = faellig_df[
                (faellig_df["Vorname"] == vorname)
                & (faellig_df["Nachname"] == nachname)
                & (faellig_df["Mitgliedsnummer"] == nummer)
            ]
            if not treffer.empty:
                ids.append(treffer.iloc[0]["ID"])
        return ids

    def _smtp_einstellungen(self):
        dlg = SmtpSettingsDialog(self)
        dlg.exec_()

    def _versenden(self):
        ausgewaehlte_ids = self._selected_member_ids()
        betreff_vorlage = self.betreff_edit.text()
        text_vorlage = self.text_edit.toPlainText()

        if not ausgewaehlte_ids:
            QMessageBox.warning(self, "Fehler", "Bitte mindestens ein Mitglied auswählen.")
            return
        if not betreff_vorlage.strip() or not text_vorlage.strip():
            QMessageBox.warning(self, "Fehler", "Betreff und Text dürfen nicht leer sein.")
            return

        try:
            smtp_config = mailer.smtp_konfiguration(adapter.smtp_secrets_wrapper())
        except mailer.SmtpNichtKonfiguriert as exc:
            QMessageBox.critical(self, "SMTP nicht konfiguriert", str(exc))
            return

        faellig_df = self._faellig_df()
        erfolgreich, fehlgeschlagen = _versende_serienmails(
            smtp_config, ausgewaehlte_ids, faellig_df, betreff_vorlage, text_vorlage,
            self.pdf_anhaengen_check.isChecked(),
        )

        meldung = []
        if erfolgreich:
            meldung.append(f"{erfolgreich} Mail(s) erfolgreich versendet.")
        if fehlgeschlagen:
            meldung.append(f"{len(fehlgeschlagen)} Mail(s) fehlgeschlagen:\n" + "\n".join(f"- {f}" for f in fehlgeschlagen))
        QMessageBox.information(self, "Beitragsmahnung", "\n\n".join(meldung) if meldung else "Nichts versendet.")
        self.refresh_table()

    def _kassierer_benachrichtigen(self):
        try:
            smtp_config = mailer.smtp_konfiguration(adapter.smtp_secrets_wrapper())
            empfaenger = mailer.kassierer_email(smtp_config)
        except mailer.SmtpNichtKonfiguriert as exc:
            QMessageBox.critical(self, "SMTP nicht konfiguriert", str(exc))
            return

        faellig_df = self._faellig_df()
        text = mitglieder.build_kassierer_beitragsuebersicht(faellig_df)
        try:
            mailer.send_mail(smtp_config, empfaenger, "Übersicht fälliger Mitgliedsbeiträge", text)
        except Exception as exc:
            QMessageBox.critical(self, "Versand fehlgeschlagen", str(exc))
            return
        QMessageBox.information(self, "Erfolg", f"Kassierer ({empfaenger}) wurde benachrichtigt.")


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
BACKUP_BESTAETIGUNGSTEXT = "WIEDERHERSTELLEN"


class BackupPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)

        erstellen_box = QGroupBox("Backup erstellen")
        erstellen_layout = QVBoxLayout(erstellen_box)
        erstellen_layout.addWidget(QLabel(
            "Erstellt ein ZIP-Archiv mit allen Mitgliederdaten (CSV, Fotos, "
            "Anhänge, Mail-Verlauf, Zahlungshistorie)."
        ))
        self.backup_erstellen_btn = QPushButton("Backup erstellen...")
        self.backup_erstellen_btn.clicked.connect(self._backup_erstellen)
        erstellen_layout.addWidget(self.backup_erstellen_btn)
        layout.addWidget(erstellen_box)

        restore_box = QGroupBox("Backup wiederherstellen")
        restore_layout = QVBoxLayout(restore_box)
        restore_layout.addWidget(QLabel(
            "⚠️ Ersetzt den kompletten aktuellen Datenbestand durch den Inhalt "
            "eines zuvor erstellten Backups. Vor dem Wiederherstellen wird "
            "automatisch ein Sicherheits-Backup des aktuellen Standes angelegt."
        ))
        self.backup_wiederherstellen_btn = QPushButton("Backup wiederherstellen...")
        self.backup_wiederherstellen_btn.clicked.connect(self._backup_wiederherstellen)
        restore_layout.addWidget(self.backup_wiederherstellen_btn)
        layout.addWidget(restore_box)

        sicherheitsbackups_box = QGroupBox("Automatische Sicherheits-Backups")
        sicherheitsbackups_layout = QVBoxLayout(sicherheitsbackups_box)
        self.sicherheitsbackups_list = QListWidget()
        sicherheitsbackups_layout.addWidget(self.sicherheitsbackups_list)
        sicherheitsbackups_btn_row = QHBoxLayout()
        self.sicherheitsbackup_herunterladen_btn = QPushButton("Ausgewähltes herunterladen...")
        self.sicherheitsbackup_herunterladen_btn.clicked.connect(self._sicherheitsbackup_herunterladen)
        sicherheitsbackups_btn_row.addWidget(self.sicherheitsbackup_herunterladen_btn)
        sicherheitsbackups_layout.addLayout(sicherheitsbackups_btn_row)
        layout.addWidget(sicherheitsbackups_box, stretch=1)

        self.refresh()

    def refresh(self):
        self.sicherheitsbackups_list.clear()
        backups = mitglieder.list_sicherheits_backups()
        if not backups:
            self.sicherheitsbackups_list.addItem("Noch keine Sicherheits-Backups vorhanden.")
            return
        for pfad in backups:
            item = QListWidgetItem(pfad.name)
            item.setData(Qt.UserRole, str(pfad))
            self.sicherheitsbackups_list.addItem(item)

    def _backup_erstellen(self):
        zeitstempel = date.today().isoformat()
        ziel, _ = QFileDialog.getSaveFileName(
            self, "Backup speichern", f"mitgliederverwaltung_backup_{zeitstempel}.zip", "ZIP-Archiv (*.zip)"
        )
        if not ziel:
            return
        Path(ziel).write_bytes(mitglieder.build_backup_zip())
        QMessageBox.information(self, "Erfolg", "Backup wurde gespeichert.")

    def _backup_wiederherstellen(self):
        quelle, _ = QFileDialog.getOpenFileName(self, "Backup auswählen", "", "ZIP-Archiv (*.zip)")
        if not quelle:
            return

        antwort = QMessageBox.warning(
            self, "Wiederherstellen bestätigen",
            "Wirklich den kompletten aktuellen Datenbestand durch dieses Backup "
            "ersetzen? Diese Aktion kann nur über ein Sicherheits-Backup "
            "rückgängig gemacht werden.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return

        bestaetigung, ok = QInputDialog.getText(
            self, "Endgültig bestätigen",
            f"Bitte tippe zur Bestätigung genau \"{BACKUP_BESTAETIGUNGSTEXT}\" ein:",
        )
        if not ok or bestaetigung.strip() != BACKUP_BESTAETIGUNGSTEXT:
            QMessageBox.information(self, "Abgebrochen", "Wiederherstellen wurde abgebrochen.")
            return

        try:
            zip_bytes = Path(quelle).read_bytes()
            mitglieder.restore_from_backup(zip_bytes)
        except mitglieder.UngueltigesBackup as exc:
            QMessageBox.critical(self, "Ungültiges Backup", str(exc))
            return

        QMessageBox.information(self, "Erfolg", "Backup wurde wiederhergestellt.")
        self.refresh()
        self.main_window.zeige_uebersicht()

    def _sicherheitsbackup_herunterladen(self):
        item = self.sicherheitsbackups_list.currentItem()
        if not item or not item.data(Qt.UserRole):
            return
        quelle = Path(item.data(Qt.UserRole))
        ziel, _ = QFileDialog.getSaveFileName(self, "Sicherheits-Backup speichern", quelle.name, "ZIP-Archiv (*.zip)")
        if ziel:
            Path(ziel).write_bytes(quelle.read_bytes())
            QMessageBox.information(self, "Erfolg", "Sicherheits-Backup wurde gespeichert.")


# ---------------------------------------------------------------------------
# Hauptfenster
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mitgliederverwaltung – Offline-Version")
        # Im PyInstaller-Build sind gebündelte Ressourcendateien nicht relativ
        # zu Path(__file__) zu finden (gui.py steckt im Programmarchiv, nicht
        # als lose Datei) - sys._MEIPASS ist der von PyInstaller vorgesehene
        # Weg, um zur Laufzeit an mitgelieferte Datendateien zu kommen.
        if getattr(sys, "frozen", False):
            ressourcen_root = Path(sys._MEIPASS)
        else:
            ressourcen_root = Path(__file__).parent.parent
        icon_path = ressourcen_root / "resources" / "icons" / "app.png"
        if icon_path.exists():
            from PyQt5.QtGui import QIcon

            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1100, 750)

        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        self.nav_list = QListWidget()
        self.nav_list.addItems(["Übersicht", "Neues Mitglied", "Serienmail", "Beitragsmahnung", "Backup"])
        self.nav_list.currentRowChanged.connect(self._navigiere)
        sidebar_layout.addWidget(self.nav_list)

        # Breite anhand der tatsächlichen Textbreite des längsten Eintrags
        # berechnen statt eines festen Pixelwerts - passt sich dadurch
        # automatisch an Systemschriftgröße/DPI-Skalierung an, statt bei
        # höherer Auflösung/Skalierung Einträge wie "Beitragsmahnung"
        # abzuschneiden.
        sidebar_breite = self._berechne_sidebar_breite(self.nav_list)
        sidebar.setMinimumWidth(sidebar_breite)
        sidebar.setMaximumWidth(sidebar_breite)

        sidebar_layout.addStretch(1)

        version_label = QLabel(f"v{VERSION}")
        version_label.setStyleSheet("color: gray; padding: 4px;")
        sidebar_layout.addWidget(version_label)

        main_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.uebersicht_page = UebersichtPage(self)
        self.neues_mitglied_page = NeuesMitgliedPage(self)
        self.serienmail_page = SerienmailPage(self)
        self.beitragsmahnung_page = BeitragsmahnungPage(self)
        self.backup_page = BackupPage(self)
        self.stack.addWidget(self.uebersicht_page)
        self.stack.addWidget(self.neues_mitglied_page)
        self.stack.addWidget(self.serienmail_page)
        self.stack.addWidget(self.beitragsmahnung_page)
        self.stack.addWidget(self.backup_page)
        main_layout.addWidget(self.stack, stretch=1)

        self.nav_list.setCurrentRow(0)
        self.uebersicht_page.refresh_table()

    @staticmethod
    def _berechne_sidebar_breite(nav_list: QListWidget) -> int:
        """Ermittelt die zur längsten Navigationsbeschriftung passende Breite
        über QFontMetrics, statt einen festen Pixelwert zu hardcoden."""
        from PyQt5.QtGui import QFontMetrics

        metriken = QFontMetrics(nav_list.font())
        breiteste_beschriftung = max(
            (metriken.horizontalAdvance(nav_list.item(i).text()) for i in range(nav_list.count())),
            default=0,
        )
        polsterung = 48  # Auswahl-Highlight, Innenabstände, ggf. Scrollbar
        return breiteste_beschriftung + polsterung

    def _navigiere(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.uebersicht_page.refresh_table()
        elif index == 2:
            self.serienmail_page.refresh_table()
        elif index == 3:
            self.beitragsmahnung_page.refresh_table()
        elif index == 4:
            self.backup_page.refresh()

    def zeige_uebersicht(self):
        self.nav_list.setCurrentRow(0)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
