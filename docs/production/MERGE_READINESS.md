# Merge-readiness

Dato: 4. november 2026.

Beslutning i denne blok: **ingen merge**. `master` bliver på `4d292dae4a43c114df8818d4d7991d9b37149736`.

## Hvorfor koden kan merges senere uden at skifte legacy-appen

Manglende eller ukendt `TRADERDASH_AUTH_MODE` bliver `legacy`. Legacy-appens secrets bruger ikke det navn. En merge alene tænder ikke Supabase Auth på `https://traderdash-market.streamlit.app`.

Piloten peger på `feature/supabase-auth`. Den følger ikke `master`, før dens branch ændres.

## Åbne punkter før mergen besluttes

| Punkt | Status |
| --- | --- |
| Fuld testsuite | Skal være grøn på merge-committen |
| Registrering | Lukket i Auth-mode. Skal forblive lukket |
| Stripe | Flag false. Ingen live-nøgle |
| Mailleverandør | Ikke valgt. Nulstilling er låst til preview |
| Sletning | Kun lokal. Ingen knap |
| Restore | Ikke udført |
| Vært | Community Cloud. Image er ikke deployet |
| Historiske auditfiler | Ignoreret. Ikke en del af mergen |
| CI | Findes ikke |

Rollback efter en senere merge er at flytte `master` tilbage til `4d292da` og lade legacy-appens secrets være. Production-schema og pilotbrugeren rulles ikke tilbage af en Git-merge.
