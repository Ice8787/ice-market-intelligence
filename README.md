# Ice Market Intelligence v2

GitHub Pages-klar dashboard för offentligt rapporterade insidersignaler från USA och Sverige, större köp, personhistorik, sektorkategorier och kursreaktioner före/efter affären. Uppdatering sker var 15:e minut och sidan läser om data var femte minut. Startdatan är tydligt markerad som fiktiv demo. Projektet ger investeringsanalys, inte personlig investeringsrådgivning.

## Lokal kontroll

På Windows kan du dubbelklicka på `start-windows.bat`. Webbläsaren öppnas automatiskt på `http://localhost:8080`.

Om `index.html` öppnas direkt visar sidan två tydligt markerade lokala demorader som reserv. Myndighetsdata och automatiska uppdateringar kräver en webbserver eller GitHub Pages.

```bash
python -m compileall -q scripts
python scripts/validate.py
python -m http.server 8080
```

Öppna `http://localhost:8080`.

## Publicera

1. Lägg innehållet i denna mapp direkt i repositoryts rot och pusha till `main`.
2. Välj **Settings → Pages → Source: GitHub Actions**.
3. Skapa repository-variabeln `SEC_USER_AGENT`, exempelvis `IceMarketIntelligence/1.0 namn@example.com`.
4. Skapa repository-variabeln `FI_USER_AGENT` med samma typ av app-/kontaktidentifikation.
5. Lägg valfritt till Actions-hemligheten `MARKET_DATA_API_KEY` för kursreaktioner via Alpha Vantage.
6. Kör **Actions → Update market intelligence → Run workflow**.

“Live” betyder så snart uppgiften har publicerats av SEC eller Finansinspektionen. Det är inte tillgång till pågående order eller ännu orapporterade affärer.

Se `docs/ARCHITECTURE.md`, `docs/METHODOLOGY.md` och `docs/DATA_SOURCES.md` för begränsningar och metod.
