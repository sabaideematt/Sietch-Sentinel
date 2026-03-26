# reports/

**Layer 5: Report Generation & SOC Integration**

Generates multi-format investigation reports and exports them to SOC platforms.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package exports: `ReportGenerator`, `STIXBundleBuilder`, `SOCExporter` |
| `generator.py` | `ReportGenerator` — produces three output formats from an `InvestigationResult`: **JSON** (full structured data with delta-V uncertainty ranges, TTP matches with confidence tiers and indicator scores, investigation budget used), **Markdown** (natural-language analyst brief with executive summary, evidence chain, TTP table, resource usage), and **STIX 2.1** (via `STIXBundleBuilder`). Can save all formats to disk. |
| `stix_builder.py` | `STIXBundleBuilder` — constructs STIX 2.1 bundles from investigation results. Creates `Identity`, `ObservedData`, `Indicator`, `Sighting`, `Relationship`, and `Note` objects. Each TTP match becomes an Indicator with its SPARTA/ATT&CK technique ID as a STIX pattern. |
| `soc_export.py` | `SOCExporter` — exports investigation results to SOC platforms: **Splunk HEC** (HTTP Event Collector via `httpx`), **Elasticsearch ECS** (Elastic Common Schema mapping), and **TAXII 2.1** (placeholder for STIX bundle publishing). Includes retry logic and error handling. |

## Output Formats

| Format | Consumer | Content |
|---|---|---|
| JSON | Programmatic consumers, dashboards | Full structured investigation data |
| Markdown | Human analysts | Natural-language brief with tables |
| STIX 2.1 | Threat intelligence platforms | Interoperable threat objects |
| Splunk HEC | Splunk SIEM | Events via HTTP Event Collector |
| Elastic ECS | Elasticsearch SIEM | Documents in Elastic Common Schema |
