# Datakällor och utbyggnad

## Implementerat

- **USA – SEC Form 4:** bolagsinsiders, roller, öppna marknadsköp/försäljningar, antal, pris och belopp. Originalrapporten länkas alltid.
- **Sverige – Finansinspektionens insynsregister:** personer i ledande ställning och närstående, förvärv/avyttringar, instrument, ISIN, antal, pris och valuta. Originalanmälan länkas när registret tillhandahåller länken.
- **Valfri kursdata:** `MARKET_DATA_API_KEY` kan innehålla en Alpha Vantage-nyckel. Då beräknas närmaste handelsdag före köpet samt 7, 30 och 90 dagar efter.
- **Automatisk kategori:** enkel, transparent namnklassning till bland annat Teknik, Energi, Försvar och Hälsa. Den markeras som automatisk och ska verifieras.

## Nästa separata insamlare

- **Representanthuset och senaten:** rapporterade politiska transaktioner. De publiceras ofta med fördröjning och värdeintervall.
- **SEC Form 13F:** kvartalsvisa innehav från större institutionella investerare. Ett ökat innehav är inte alltid ett exakt, enskilt köp och rapporteringen är fördröjd.
- **Finansinspektionens insynsregister:** svenska personer i ledande ställning.
- **Bolagshändelser:** SEC 8-K för kontrakt, uppköp och andra väsentliga händelser.

Varje insamlare måste bevara käll-URL, handelsdatum, rapportdatum, datakvalitet och om värdet är exakt eller ett intervall. Verkliga personer får aldrig visas utan verifierbar offentlig källa.

## Vad “realtid” betyder

Dashboarden kan hämta en rapport kort efter att den publicerats, men den känner inte till affären innan rapportören eller myndigheten offentliggjort den. USA:s Form 4 kan normalt lämnas inom två affärsdagar. Svenska insynstransaktioner ska normalt anmälas inom tre affärsdagar. Tabellen visar därför handelsdatum, publiceringsdatum och beräknad fördröjning sida vid sida.

## Topp 100

Varje körning läser de senaste posterna från båda marknaderna och slår ihop dem med tidigare verifierade poster i repositoryt. Dubbletter tas bort. För varje kombination av marknad och kategori behålls de 100 största affärerna efter rapporterat belopp i lokal valuta. USD och SEK jämförs inte direkt med varandra.

## Bevakningslista för kända ledare

`config/leader-watchlist.json` är avsiktligt tom vid leverans. Där kan verifierade teknik- och affärsledare läggas till med namn, alias och relevanta tickers. En matchande SEC-rapport får då persontypen `business_leader` och kan filtreras separat. Listan skapar inga transaktioner; den märker bara redan verifierade rapporter.
# Amerikanska politiker, beslut och trenddata

- Representanthusets och senatens PTR-uppgifter hämtas via öppna JSON-speglar av de offentliga rapporterna. Varje post behåller länk till PTR/originalsökningen. Speglarna kan vara fördröjda eller ofullständiga; originalrapporten är alltid källan som gäller.
- Tull-, handels-, exportkontroll- och försvarsbeslut hämtas från den officiella Federal Register-API:n.
- Historiska slutkurser och volym hämtas från Stooq med Yahoo Finance chart-data som reservkälla. Detta är dagsdata, inte realtidskurser eller orderbok.
- Politikernas belopp publiceras ofta som intervall. Dashboarden visar intervallet och använder dess mittpunkt endast för en tydligt märkt uppskattning av historisk P/L.
- Stora investerares positionsökningar jämförs från officiella SEC Form 13F-HR för Berkshire Hathaway, Bridgewater Associates, Pershing Square och Soros Fund Management. Rapporterna är kvartalsvisa och kan vara 45 dagar fördröjda.
