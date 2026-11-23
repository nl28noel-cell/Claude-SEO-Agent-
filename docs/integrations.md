# Integrationen – SEO Autopilot

Stand: 23.11.2026 · Quellen: developer.semrush.com (v3/v4-Doku, Stand 13.–20.11.2026), developers.google.com/webmaster-tools, support.google.com/webmasters/answer/7687615, developers.google.com/identity/protocols/oauth2/service-account

---

## 1. Semrush

### 1.1 Abrechnungsmodell (laut offizieller Doku)

| Frage | Antwort | Quelle |
|---|---|---|
| Woher kommen die Units? | Ein **Account-weites API-Unit-Guthaben**. Semrush MCP (der Claude-Connector) „uses the same unit-based system as the Semrush API“ und „consumes API units from your Semrush API subscription“. | api/v3/introduction/semrush-mcp |
| Welche Pläne? | **Semrush One Starter, One Pro+, SEO Classic Pro, SEO Classic Guru:** enthalten **50.000 API Units**, die **zum Verlängerungsdatum des Abos erneuert werden**. **SEO Classic Business / Semrush One Advanced:** Units als separat gekaufte Pakete (2 / 5 / 10 / 20 Mio.). | ebd. |
| Separat kaufbar? | Nur mit Business- bzw. One-Advanced-Plan (Subscription info → API Units → Paket kaufen). Bei Pro/Guru gibt es **keinen Zukauf** – das erklärt, warum im Konto keine Kaufoption sichtbar ist. | api/v3/get-started/api-access |
| Pro Key oder pro Account? | **Pro Account.** „Your API key gives access to your API units balance.“ Ein neuer Key erzeugt **kein** zusätzliches Kontingent. | api/v3/introduction/api-versions |
| Leere Antworten | Kosten **0 Units**. | api/v3/get-started/api-units-balance |
| Zu wenig Units | SEO API liefert ggf. nur so viele Zeilen, wie bezahlt werden können, oder ERROR 132. | ebd. |
| Wo sehe ich Verbrauch? | Semrush UI → My Profile → **Subscription info → API units** (Restguthaben) und → **Query log → API Queries** (jede Abfrage mit Kosten und Restguthaben, exportierbar). | ebd. |

**Interpretation für SEMSHARKS (zu bestätigen):** Die beobachteten 1.250 Units vor unserem ersten Lauf passen zu einem Pro/Guru-Plan mit 50.000 Units pro Abrechnungsperiode, von denen bereits ca. 48.750 verbraucht waren – vermutlich durch andere Semrush-MCP-Nutzung im selben Account (z. B. andere Claude-Chats/Projekte). Das Query Log zeigt genau, wodurch. Nach der Abo-Verlängerung stehen wieder 50.000 Units zur Verfügung.

### 1.2 API-Keys

- **v3-Key:** einer pro Account, automatisch, nicht widerrufbar, Übergabe als Query-Parameter `?key=`. Kostenloser Kontostand: `http://www.semrush.com/users/countapiunits.html?key=…`.
- **v4-Key:** bis zu 100, mit Rechten (read-only / read-write) und Ablaufdatum (TTL), widerrufbar. Übergabe im Header `Authorization: Apikey <KEY>`. Abdeckung v4: Keyword reports, Domain Analytics, Backlinks, Projects, Traffic & Market, Local.
- Ein selbst erstellter Key (`semrtkn-pat-…`) ist nach Doku ein **v4-Key** (nur v4-Keys sind erstellbar). **Nicht verifiziert**, bis ein Test-Call läuft.

### 1.3 Unit-Kosten (aus der Semrush-MCP-Preisangabe, live/Historie)

| Report | Zweck | Units |
|---|---|---|
| domain_rank | Domain-Überblick | 10 / Zeile (Historie 50) |
| resource_organic (domain_organic) | Rankings je Domain/URL | 10 / Zeile (Historie 50) |
| phrase_this / phrase_these | Volumen, CPC, Competition, KD, Intent | 10 / Zeile (Historie 50) |
| phrase_all | Keyword in allen Datenbanken | 10 / Zeile |
| phrase_organic | SERP Top-Ergebnisse je Keyword | 10 / Zeile (Historie 50) |
| phrase_fullsearch | Broad Match | 20 / Zeile |
| phrase_questions | Fragen | 40 / Zeile |
| phrase_related | Related Keywords | 40 / Zeile |
| phrase_kdi | Keyword Difficulty | 50 / Zeile (in phrase_these als Spalte enthalten) |
| projects: get/list | Projektverwaltung | 100 / Request |

### 1.4 API-effiziente Discovery-Strategie

Grundregel: **teure Expansion nur auf wenige, geprüfte Seeds; Bewertung immer gebündelt; alles cachen.**

1. **Cache zuerst** (`tools/keyword_cache.py`): Jedes Keyword wird mit Datenbank, Quelle, Datum und Ergebnis gespeichert – auch „keine Daten“. Vor jedem Call nur `missing` abfragen; Gültigkeit Volumen/KD 90 Tage, Rankings 30 Tage.
2. **Kostenlose Quellen vor Semrush:** GSC-Queries (sobald angebunden), bestehende Keywordrecherche (Drive), eigenes Seiten-Vokabular, Wettbewerberseiten (Crawl, 0 Units).
3. **Expansion sparsam:** `phrase_fullsearch` (20/Zeile) vor `phrase_related` (40/Zeile); `display_limit` 20–30; nur für ca. 10–15 Seeds mit Prio ≥ 8; Filter auf Mindestvolumen bzw. Wortbestandteile.
4. **Bewertung gebündelt:** `phrase_these` mit bis zu 100 Keywords pro Call und KD als Spalte (spart `phrase_kdi` = 50/Zeile). Lokale Kombinationen kosten meist 0, weil ohne Daten.
5. **SERP-Analyse nur für Kandidaten:** `phrase_organic` mit `display_limit=10` (100 Units/Keyword) ausschließlich für Opportunities, die in das Approval-Gate-Paket sollen.
6. **Wettbewerber über SERPs statt Domain-Exports:** Top-10-Domains aus `phrase_organic` → nur für 3–5 Hauptwettbewerber `resource_organic` mit Filter auf relevante Wörter und `display_limit` ≤ 50.
7. **Budget pro Lauf** vorab schätzen und im Report ausweisen.

Richtwert für einen vollständigen Discovery-Lauf dieses Piloten: ca. **8.000–15.000 Units** (15 Seeds × 30 Zeilen Broad Match ≈ 9.000; 3 Batches phrase_these ≈ 2.000–3.000; 15 SERPs ≈ 1.500; 3 Wettbewerber × 50 ≈ 1.500). Das passt in ein 50.000er-Kontingent, wenn keine anderen Nutzer im Account parallel verbrauchen.

### 1.5 Hinterlegen eines Semrush-Keys (sicher)

- Key **nie** in den Chat, ins Repo oder in eine Datei. Hinterlegung über das **sichere Formular dieser Umgebung (Network Secret)**: Host `api.semrush.com`, Header `Authorization`, Präfix `Apikey`. Der Proxy fügt den Key nur in Requests an diesen Host ein; Claude sieht den Wert nie.
- Empfohlene Key-Einstellungen in Semrush: eigener Key „Claude SEO Autopilot“, **Read-only**, TTL z. B. 90 Tage.
- Der v3-Key (Query-Parameter) lässt sich so **nicht** hinterlegen – nicht nötig, solange MCP bzw. v4 genutzt werden.

---

## 2. Google Search Console

### 2.1 Geprüfte Optionen

| Option | Bewertung |
|---|---|
| Bestehender Google-Drive-Connector | ❌ Liefert nur Drive-Daten; kein Search-Console-Scope. |
| Offizieller Search-Console-Connector | ❌ Kein Google-eigener Connector im Verzeichnis gefunden. Drittanbieter (Windsor.ai, Supermetrics, Adspirer) existieren – Daten laufen dann über Dritte und es fallen Kosten an. |
| OAuth-Benutzerzugang (Refresh Token) | ⚠️ Möglich, aber Token muss für die Erneuerung im Container vorliegen; bei OAuth-Apps im Status „Testing“ laufen Refresh Tokens nach 7 Tagen ab (Google-OAuth-Richtlinie; in dieser Recherche nicht erneut belegt). |
| **Service Account + Search Console API** | ✅ **Empfohlen.** Dauerhaft, ohne Browser-Login, Rechte auf genau eine Property begrenzbar. |
| GSC Bulk Export → BigQuery | Für später (Skalierung), aktuell bewusst ausgeschlossen. |

### 2.2 Fakten (offizielle Doku)

- Scope (read-only): `https://www.googleapis.com/auth/webmasters.readonly`
- Service-Account-Flow: signiertes JWT → `https://oauth2.googleapis.com/token` → kurzlebiges Access Token (Erneuerung automatisch durch die Anwendung). Google speichert den privaten Schlüssel nicht.
- Search Analytics: Dimensionen `query`, `page`, `country`, `device`, `searchAppearance`, `date`, `hour`; Filter und Paginierung (`rowLimit`, `startRow`); API liefert „top rows“, nicht garantiert alle Zeilen.
- Quoten: Search Analytics 1.200 QPM pro Site/User; URL Inspection 2.000 QPD und 600 QPM pro Site.
- Rollen in Search Console: Owner / Full user / Restricted user. Nutzer hinzufügen kann nur ein Owner. Max. 100 Nicht-Owner pro Property.

### 2.3 Einrichtung (Schritt für Schritt)

1. **Google Cloud Console** → neues Projekt „semsharks-seo-autopilot“.
2. **APIs & Dienste → Bibliothek → „Google Search Console API“ aktivieren.**
3. **IAM → Dienstkonten → Dienstkonto erstellen**, z. B. `seo-autopilot@<projekt>.iam.gserviceaccount.com`. **Keine IAM-Rollen vergeben** (nicht nötig).
4. Dienstkonto → **Schlüssel → Neuer Schlüssel → JSON** herunterladen. Datei sicher aufbewahren, nicht per Mail/Chat weitergeben.
5. **Search Console** → Property `spreewald-luftaufnahmen.de` (Domain-Property bevorzugt) → Einstellungen → **Nutzer und Berechtigungen → Nutzer hinzufügen** → E-Mail des Dienstkontos.
   - **Minimal:** „Eingeschränkt“ (Restricted) – reicht für Leistungsdaten.
   - **Empfohlen:** „Vollständig“ (Full user), damit auch URL Inspection (Indexierungsstatus) sicher funktioniert. Kein Owner nötig.
6. Credential in dieser Umgebung hinterlegen (siehe 2.4).

### 2.4 Credential sicher hinterlegen – Einschränkung dieser Umgebung

Network Secrets dieser Cloud-Umgebung injizieren einen **festen Header** pro Host. Google erwartet aber stündlich wechselnde Access Tokens, die aus dem privaten Schlüssel **im Container** erzeugt werden. Der Schlüssel muss daher im Container lesbar sein.

Empfohlene Pilot-Lösung:
- Umgebung „Claude-SEO-Agent“ → Bearbeiten → **Umgebungsvariable `GSC_SERVICE_ACCOUNT_JSON_B64`** = Base64 der JSON-Schlüsseldatei. Eintragen ausschließlich durch Noel in den Umgebungseinstellungen; nie im Chat.
- Risiko-Begrenzung: persönliche Umgebung (nur Noel), Dienstkonto ohne IAM-Rollen, nur Lesezugriff auf die freigegebenen Properties, Schlüssel alle 90 Tage rotieren, jederzeit in Cloud Console widerrufbar.
- Skalierungs-Lösung später: kleiner Token-Broker (z. B. Cloud Run), der den Schlüssel hält und dem Autopiloten nur über einen festen API-Key (Network Secret) Daten liefert – dann liegt kein Google-Schlüssel mehr im Container.

### 2.5 Ergebnis

Nach Einrichtung ruft der Autopilot **selbstständig und ohne manuelle Exporte** Query-, Page-, Country-, Device- und Tages-Zeitreihen (16 Monate) sowie den Indexierungsstatus einzelner URLs ab. Neue Kunden: nur Dienstkonto in deren Property als Nutzer hinzufügen.

Benötigte Hosts (bereits freigegeben): `oauth2.googleapis.com`, `searchconsole.googleapis.com`, `www.googleapis.com`.
