# SafeClaw

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Lizenz MIT](https://img.shields.io/badge/Lizenz-MIT-green)
![CI](https://img.shields.io/github/actions/workflow/status/constripacity/safeclaw/ci.yml?label=CI)

Ein **sandboxed, richtliniengesteuerter lokaler Entwicklungsassistent**, der Ihre Codebasis nach TODOs, Secrets, Abhangigkeitsproblemen und mehr durchsucht — ohne jemals beliebige Shell-Befehle auszufuhren oder auf das Netzwerk zuzugreifen.

> Dieses Projekt wurde als Portfolio-Projekt entwickelt.

## Schnellstart

```bash
# Installation
pip install -e ".[dev]"

# Nach TODO/FIXME/HACK suchen
safeclaw todo ./mein-projekt/

# Hardcodierte Secrets erkennen
safeclaw secrets ./mein-projekt/

# Build-Log zusammenfassen
safeclaw summarize ./build.log

# Abhangigkeiten prufen
safeclaw deps ./mein-projekt/

# Repository-Statistiken
safeclaw stats ./mein-projekt/

# Audit-Log anzeigen
safeclaw audit

# Aktuelle Richtlinie anzeigen
safeclaw policy
```

## Sicherheitsmodell

SafeClaw basiert auf dem Prinzip, dass **KI-Agenten niemals mehr Zugriff haben sollten als explizit gewahrt**:

- **Standardmassig verweigert** — kein Shell-Zugang, kein Netzwerkzugang, es sei denn, die policy.yaml erlaubt es ausdruecklich
- **Pfadbeschrankung** — alle Operationen sind auf das deklarierte `project_root` beschrankt
- **Plugin-Allowlist** — nur explizit erlaubte Plugins konnen ausgefuhrt werden
- **Automatische Secret-Redaktion** — API-Schlussel, Tokens und private Schlussel werden aus allen Audit-Logs entfernt
- **Vollstandiger Audit-Trail** — jeder Plugin-Lauf wird in `.safeclaw/audit.jsonl` protokolliert

Siehe [SECURITY.md](SECURITY.md) fur das vollstandige Bedrohungsmodell.

## Konfiguration

SafeClaw wird uber `policy.yaml` konfiguriert:

```yaml
project_root: "."
allow_network: false
allow_shell: false
allowed_plugins:
  - todo_scan
  - log_summarize
  - secrets_scan
  - deps_audit
  - repo_stats
limits:
  max_file_mb: 5
  max_files: 2000
  timeout_seconds: 30
```

## Verfugbare Plugins

| Plugin | Beschreibung |
|--------|-------------|
| `todo_scan` | TODO / FIXME / HACK Marker finden |
| `log_summarize` | Fehler und Exceptions aus Log-Dateien extrahieren |
| `secrets_scan` | Hardcodierte API-Schlussel und Zugangsdaten erkennen |
| `deps_audit` | Deklarierte Abhangigkeiten auf Probleme prufen |
| `repo_stats` | Dateien, Codezeilen und Dateityp-Verteilung zahlen |

## Warum dieses Projekt existiert

Autonome KI-Agenten (wie OpenClaw, PicoClaw usw.) sind leistungsstark, laufen aber oft mit ubermassigen Berechtigungen — uneingeschrankter Shell-Zugang, voller Festplattenzugriff und offene Netzwerkverbindungen. SafeClaw zeigt, dass ein Entwicklungsassistent **nutzlich sein kann, ohne gefahrlich zu sein**, indem Least-Privilege-Sicherheit auf jeder Ebene durchgesetzt wird.

### Demonstrierte Konzepte

Dieses Projekt demonstriert Verstandnis von:
- **Least-Privilege-Prinzip** — der Agent kann nur das tun, was die Richtlinie explizit erlaubt
- **Defense in Depth** — Pfadbeschrankung + Plugin-Allowlist + Audit-Logging + Redaktion
- **Prompt-Injection-Bewusstsein** — der LLM-Planner kann nur vorschlagen, nie direkt ausfuhren
- **Supply-Chain-Sicherheit** — keine beliebige Plugin-Ausfuhrung von Drittanbietern
- **DevOps-Grundlagen** — CI/CD, Docker, Linting, Testing
- **Saubere Architektur** — Separation of Concerns, Plugin-System, Config-Validierung

## Entwicklung

```bash
# Mit Entwicklungsabhangigkeiten installieren
pip install -e ".[dev]"

# Tests ausfuhren
pytest

# Linting
ruff check .

# Format prufen
ruff format --check .
```

## Mitwirken

Beitrage sind willkommen! Bitte stellen Sie sicher, dass alle Anderungen `ruff check` und `pytest` bestehen, bevor Sie einen PR einreichen.

## Lizenz

MIT
