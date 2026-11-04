# Merge-readiness

Dato: 4. november 2026.

Beslutning i denne blok: **ingen merge**. `master` bliver på `4d292dae4a43c114df8818d4d7991d9b37149736`.

## Hvorfor koden kan merges senere uden at skifte legacy-appen

Manglende eller ukendt `TRADERDASH_AUTH_MODE` bliver `legacy`. Legacy-appens secrets bruger ikke det navn. En merge alene tænder ikke Supabase Auth på `https://traderdash-market.streamlit.app`.

Piloten peger på `feature/supabase-auth`. Den følger ikke `master`, før dens branch ændres.

## Åbne punkter før mergen besluttes

| Punkt | Status |
| --- | --- |
| Fuld testsuite | CI kører `python -m unittest discover -s tests` på Python 3.12 uden secrets |
| Registrering | Lukket i Auth-mode. Skal forblive lukket |
| Stripe | Flag false. Ingen live-nøgle |
| Mailleverandør | Ikke valgt. Det blokerer ikke en kodemerge |
| Sletning | Kun lokal. Ingen knap. Det blokerer ikke en kodemerge |
| Restore | Ikke udført. Det blokerer ikke en kodemerge |
| Vært | Community Cloud. Image er ikke deployet |
| Historiske auditfiler | Ignoreret. Ikke en del af mergen |
| CI | `.github/workflows/release-gate.yml` |

En merge kopierer kode. Den kører ikke SQL, skifter ikke Cloud-secrets og flytter ikke DNS. Migrationerne er allerede anvendt på Production og må ikke køres igen. Filkommentaren `NOT APPLIED` i identitetskataloget er låst af testen. Driftshistorikken er kilden.

Rollback efter en senere merge er at flytte `master` tilbage til `4d292da` og lade legacy-appens secrets være. Production-schema og pilotbrugeren rulles ikke tilbage af en Git-merge.
