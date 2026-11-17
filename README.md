# Creality Falcon für Home Assistant

Lokale Custom Integration (kein Cloud-Zugang) für den **Creality Falcon T1**. Sie sollte auch mit dem Falcon A1 Pro funktionieren, weil beide dieselbe HTTP-API nutzen.

> ⚠️ Creality dokumentiert diese API nicht. Die Endpunkte stammen aus der LightBurn-Treiberentwicklung („Creality Falcon HTTP“) und aus dem Open-Source-Projekt KerfDesk. Je nach Firmware kann sich etwas ändern.

## Installation

**HACS (benutzerdefiniertes Repository):** `https://github.com/jschallmayer78/ha-creality-falcon` als Typ *Integration* hinzufügen, installieren und HA neu starten.

**Manuell:** `custom_components/creality_falcon` nach `/config/custom_components/` kopieren und HA neu starten.

Danach: *Einstellungen → Geräte & Dienste → Integration hinzufügen → „Creality Falcon“*. Die IP-Adresse eintragen, der API-Port (8080 oder 80) wird automatisch erkannt. Tipp: dem Laser im UniFi-Controller eine feste IP geben.

## Entitäten

| Entität | Typ | Hinweis |
|---|---|---|
| Status | Sensor (Enum) | `bereit` / `laeuft` / `alarm` |
| Fortschritt | Sensor % | aus `GET /work/progress` |
| Job gestartet, Voraussichtliches Ende | Timestamp | Ende wird aus der Fortschrittsrate hochgerechnet |
| Letzter Job beendet, Dauer letzter Job | Timestamp / Dauer | |
| Zustandscode | Diagnose | roher `state`-Wert, Attribut `endpoint` zeigt den gefundenen Pfad |
| Job läuft, Alarm | Binärsensor | |
| Job stoppen, Rahmen fahren, Referenzfahrt, Autofokus | Taste | |
| Job starten | Taste | **standardmäßig deaktiviert**, siehe Sicherheit |
| Innenbeleuchtung | Licht (dimmbar) | `POST /device/setLight {"dutyCycle":0..100}`, Zustand wird angenommen |
| Positionslaser | Schalter | `POST /device/assistLight {"switch":0/1}`, Zustand wird angenommen |
| Innenraumkamera | Kamera | T1: `POST /media/getCapturePhoto?from=falcon` mit Bildgröße, 2560×1920 JPEG; A1 Pro: `GET` als Fallback |

### Events für Automationen

- `creality_falcon_job_started`
- `creality_falcon_job_finished` mit `completed`, `alarm` und `duration_s`

Beispiel: Signal-Nachricht, wenn ein Job fertig ist:

```yaml
alias: "Laser: Job fertig"
triggers:
  - trigger: event
    event_type: creality_falcon_job_finished
actions:
  - action: notify.signal
    data:
      message: >-
        {% if trigger.event.data.alarm %}⚠️ Laser-Alarm!
        {% elif trigger.event.data.completed %}✅ Laserjob fertig
        {% else %}⏹️ Laserjob abgebrochen{% endif %}
        ({{ (trigger.event.data.duration_s / 60) | round(1) }} min)
```

## Sicherheit

Ein Laserjob sollte nur laufen, wenn jemand in der Nähe ist. Deshalb ist **„Job starten“ standardmäßig deaktiviert**. Wer die Taste trotzdem braucht, aktiviert sie bewusst unter Entität → Einstellungen. „Job stoppen“ ist immer aktiv, damit ein Job notfalls aus der Ferne abgebrochen werden kann.

## Am Falcon T1 verifiziert (Firmware Stand 11/2026)

- `GET /work/progress` → `{"errorcode":0,"payload":{"progress":"0.00"}}` (Text, 0..1)
- `GET /work/state` → `{"errorcode":0,"payload":{"state":2}}` (2 = Leerlauf)
- `GET /device/status` → Liste der Komponenten (Beeper, Light, LightBar, Fan, FieldlensNfc …)
- `GET /media/getCapturePhoto` → `{"errorcode":-1,"payload":{}}` (A1-Pro-Variante funktioniert am T1 nicht)
- `POST /media/getCapturePhoto?from=falcon` mit `{"exposureValue":-1,"height":1920,"width":2560}` → JPEG, 2560×1920, ca. 350 KB (so ruft Falcon Design Space das Bild ab, per Mitschnitt verifiziert)
- `GET /work/probe?from=falcon` (Autofokus) → `{"errorcode":0,"payload":{"materialHight":6.31,"result":0}}`
- `GET /work/mpos?from=falcon` → `{"errorcode":0,"payload":{"mpos":"<87.5,87.5,-140.19,0.0>"}}`
- UDP-Broadcast auf Port 12345: `{"devName":"cv_laser_60","ip":"…","port":"8080"}` (für eine spätere automatische Erkennung)
- TCP 11111: Push-Kanal mit Statusmeldungen (`{"module":"printer","curState":512}`, `{"module":"alarm",…}`); der Verbindungsaufbau ist verschlüsselt und noch nicht nachgebaut

## Offene Punkte / Verifikation

- **Zustandsendpunkt:** Der Pfad, der `{"errorcode":0,"payload":{"state":N}}` liefert, ist nicht öffentlich bekannt. Die Integration probiert mehrere Kandidaten nacheinander. Findet sie keinen, wird der Status nur aus dem Fortschritt abgeleitet. Bisher bekannt ist nur `state 4` = Alarm.
- **Referenzfahrt:** `POST /work/home` erwartet laut LightBurn einen JSON-Body. Gesendet wird `{}`. Falls der T1 etwas anderes erwartet, muss das angepasst werden.
- **Rahmen fahren** läuft laut Firmware in einer Schleife, bis „Job stoppen“ gedrückt wird.

Zum Prüfen des eigenen Geräts (sendet nur lesende GET-Anfragen):

```bash
python3 tools/falcon_probe.py 192.168.x.y
```

Die Ausgabe zeigt, welche Endpunkte antworten. Damit lassen sich die Kandidaten in `const.py` anpassen.
