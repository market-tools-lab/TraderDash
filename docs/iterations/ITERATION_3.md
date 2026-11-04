# Iteration 3

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE**.

Auth ligger bag `TRADERDASH_AUTH_MODE`. Default er `legacy`. Preview-kæden er kørt med en midlertidig bruger, som bagefter er slettet.

## Target

| Kontrol | Resultat |
| --- | --- |
| Project ref | `ajbsoudovxstlolojvte` |
| Branch | `supabase-auth-test` |
| URL | `https://ajbsoudovxstlolojvte.supabase.co` |
| Production | Ikke kontaktet |
| Streamlit Cloud | Ikke ændret |
| `master` | Står på `4d292dae4a43c114df8818d4d7991d9b37149736` |

## Auth-mode

| Værdi | Resultat |
| --- | --- |
| Mangler, tom eller `legacy` | `legacy` |
| `supabase_auth` | Ny loginvej |
| Enhver anden værdi, herunder `dual` og `supabase` | `legacy` |

Rollback er `TRADERDASH_AUTH_MODE=legacy`, eller at variablen fjernes. Begge dele bruger den nuværende loginvej. Cloud har ikke fået variablen.

## Kode

Nyt modul: `supabase_auth.py`. `app.py` vælger kun vej. Analyse, universer og den gamle kontofunktion er ikke skrevet om.

Modulet kan logge ind med e-mail og password, læse session, user id, egen profil og egen entitlement, oversætte planen og logge ud. Det skriver ikke entitlements. Det bruger anon- eller publishable-nøglen fra miljøet, ikke service role.

Sessionen gemmer access token, user id og e-mail. Password-nøglerne `login_password`, `register_password` og `register_confirmation` fjernes efter et vellykket login. De fjernes ikke, før formularen er læst.

Aktiv TraderDash-entitlement med plan `free`, `nordic` eller `international` bliver den plan. Manglende, ukendt, `revoked`, `suspended`, udløbet eller forkert produkt giver ingen plan. Appen stopper før analyse og skriver "Ingen adgang".

## Preview

Kæden er kørt mod preview med en midlertidig syntetisk bruger. Brugeren og entitlementen er slettet bagefter.

| Trin | Resultat |
| --- | --- |
| Auth-login | Session oprettet |
| Profil | Samme user id som sessionen |
| Entitlement | Aktiv `traderdash` / `free` |
| Plan | `free` |
| Univers | 30 papirer |
| Session | Password-nøgler fjernet efter login |
| Logout | Token og user id fjernet |

Preview indeholder derefter én Auth-bruger, `markettools-auth-test@example.invalid`, id `63ffe985-0e7e-48bd-b41b-d1741330257a`, én profil og ingen entitlement. `public.users` er 0.

Preview-testen har ingen default-bruger. URL, anon- eller publishable-nøgle, e-mail, user id og password skal alle sættes i miljøet. Mangler en af dem, springes testen over med navnene på de manglende variable. En anden URL, en service-role-nøgle eller en nøgle fra et andet projekt afvises før der sendes et kald. Nøgle, password og token skrives ikke i testoutput eller i denne fil.

## Enhedstest

`python -m unittest tests.test_supabase_auth tests.test_supabase_auth_preview tests.test_account_store tests.test_identity_schema tests.test_entitlement_access`

53 tests. 45 bestod, 0 fejlede, 8 sprunget over. De 18 legacy-kontotests bestod. Syv sprunget over er de gamle database-pladsholdere. Den ottende er preview-testen, fordi miljøet ikke var sat.

Dækket uden netværk: default `legacy`, ukendt mode tilbage til `legacy`, eksplicit `supabase_auth`, legacy-kaldet er uændret i `app.py`, password væk efter login, manglende entitlement lukket, `free`/`nordic`/`international`, `revoked`, `suspended`, udløbet og forkert produkt uden adgang, og at preview-konfigurationen ikke falder tilbage til et historisk user id.

`universes.stocks_for("free")` er stadig 30. `universes.py` er ikke ændret.

## Rollback

Sæt `TRADERDASH_AUTH_MODE=legacy`, eller fjern variablen. Appen bruger da `accounts.authenticate`, `accounts.create_user` og `accounts.get_user` som før.

## Næste skridt

Iteration 4 er ikke startet.
