# Merge-readiness

Historisk note for pull request #1 den 4. november 2026. Pull request #8 er merget senere. Den gældende tilstand står i `CURRENT_BASELINE.md`.

Dato: 4. november 2026.

Kontrolleret merge er udført. Pull request #1 merget `feature/supabase-auth` `8f304de5eb3baebef5f5048570c27d65b7995a4d` til `master` som `0e1f7b4a43125af36431bab82f95d848bfc882e6` den 4. november 2026 kl. 18:28 UTC. Strategien er en almindelig merge-commit. Den tidligere `master` var `4d292dae4a43c114df8818d4d7991d9b37149736`. `feature/supabase-auth` er beholdt.

Release-gate på pull requesten var grøn: 117 tests, 0 fejl, 9 sprunget over, Python 3.12, ingen Production-secrets. Workflowet lytter på pull requests mod `master` og push til `feature/**`. Selve merge-committen starter derfor ikke et nyt Actions-kørsel. Træet er identisk med den godkendte kandidat.

## Produktion efter mergen

Manglende eller ukendt `TRADERDASH_AUTH_MODE` bliver `legacy`. Legacy-appens secrets er ikke ændret. Mergen tænder ikke Supabase Auth på `https://traderdash-market.streamlit.app`.

Piloten peger stadig på `feature/supabase-auth`. Den følger ikke `master`, før dens branch ændres.

Registrering er lukket i Auth-mode. Stripe-flaget er false. Der er ingen sletteknap.

Mergen kopierede kode. Den kørte ikke SQL, skiftede ikke Cloud-secrets og flyttede ikke DNS. Migrationerne `accounts`, `identity_catalog` og `legacy_auth_links` var allerede anvendt og må ikke køres igen. Filkommentaren `NOT APPLIED` i identitetskataloget er låst af testen. Driftshistorikken er kilden.

## Stadig uden for mergen

| Punkt | Klasse |
| --- | --- |
| Mailleverandør og levering af nulstilling | Offentlig lancering |
| Restore-øvelse | Offentlig lancering |
| Produktionsklar kontosletning | Offentlig lancering |
| Beslutning om åben registrering | Offentlig lancering |
| Stripe Live, produkter, checkout og webhook | Betalt lancering |
| Container-vært, overvågning og backup-procedure | Drift |
| Historiske auditfiler | Ignoreret. Ikke en del af mergen |

Rollback af Git-mergen er at flytte `master` tilbage til `4d292da` og lade legacy-appens secrets være. Production-schema og pilotbrugeren rulles ikke tilbage af Git. Der køres ikke omvendt SQL af den grund.
