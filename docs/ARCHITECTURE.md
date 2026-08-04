# Arkitektur

GitHub Pages publicerar `index.html`, `assets/`, `data/` och dokumentationen som en statisk webbplats. `update-data.yml` kör Python-insamlaren enligt schema, validerar resultatet och committar ändrade JSON-filer. En push till `main` startar `pages.yml`.

```text
SEC EDGAR Form 4 ─┐
                  ├→ update_all.py → topp 100/marknad/kategori → data/*.json
FI Insynsregister ┘                                             ↓
                                                        GitHub Pages
```

GitHub Actions kör insamlingen var 15:e minut. Dashboarden kontrollerar publicerade JSON-filer var femte minut utan webbläsarcache. Schemalagda Actions-körningar kan fördröjas av GitHub, så detta är nära realtid efter publicering – inte ett börsflöde i realtid.

Kursreaktioner uppdateras i ett separat dagligt arbetsflöde. Det håller myndighetsflödet snabbt och undviker att förbruka marknadsdatakvoter vid varje 15-minuterskontroll.

Ingen hemlig API-nyckel skickas till webbläsaren. Repository-variablerna `SEC_USER_AGENT` och `FI_USER_AGENT` bör identifiera appen och en kontaktadress.

## Begränsning i startversionen

SEC:s aktuella Atom-flöde upptäcker nya Form 4-rapporter men innehåller inte fullständiga transaktionsfält. Startinsamlaren markerar därför dessa poster med låg score och länkar till originalrapporten. En produktionsversion bör följa länken och tolka Form 4 XML innan köp/sälj, antal, pris, roll och score sätts.
