# Iteration 3

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **BLOCKED**.

Auth-koden ligger bag `TRADERDASH_AUTH_MODE`. Default er `legacy`. Preview-login med den eksisterende syntetiske bruger blev afvist, så iterationen er ikke DONE.

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

Modulet kan logge ind med e-mail og password, læse session, user id, egen profil og egen entitlement, oversætte planen og logge ud. Det skriver ikke entitlements.

Sessionen gemmer access token, user id og e-mail. Password nøglerne `login_password`, `register_password` og `register_confirmation` fjernes efter et vellykket login. De fjernes ikke, før formularen er læst.

Aktiv TraderDash-entitlement med plan `free`, `nordic` eller `international` bliver den plan. Manglende, ukendt, `revoked`, `suspended`, udløbet eller forkert produkt giver ingen plan. Appen stopper før analyse og skriver "Ingen adgang".

## Preview

Brugeren `markettools-auth-test@example.invalid` findes stadig. Id `32772e00-62a3-4d85-8da6-eeb806cb56c5`. E-mail er bekræftet. Der er ét password, én profil og én aktiv entitlement. `public.users` er ikke ændret.

Passwordet blev spurgt lokalt tre gange og lå kun i processens miljø. Det er ikke skrevet her. Auth svarede hver gang `invalid_credentials` (HTTP 400). Derfor blev disse ikke kørt færdigt:

1. login
2. user id
3. profile
4. entitlement
5. plan = free
6. 30 papirer via den eksisterende universlogik
7. logout og session cleanup

Testen ligger i `tests/test_supabase_auth_preview.py`. Den springes over, medmindre preview-URL, anon key og password ligger i miljøet. Ingen af delene er committet.

## Enhedstest

`python -m unittest tests.test_supabase_auth tests.test_account_store tests.test_identity_schema tests.test_entitlement_access`

49 tests. 42 bestod, 0 fejlede, 7 sprunget over. De 18 legacy-kontotests bestod. De 7 sprunget over er de gamle database-pladsholdere.

Dækket uden netværk: default `legacy`, ukendt mode tilbage til `legacy`, eksplicit `supabase_auth`, legacy-kaldet er uændret i `app.py`, password væk efter login, manglende entitlement lukket, `free`/`nordic`/`international`, og `revoked`, `suspended`, udløbet og forkert produkt uden adgang.

`universes.stocks_for("free")` er stadig 30. `universes.py` er ikke ændret.

## Rollback

Sæt `TRADERDASH_AUTH_MODE=legacy`, eller fjern variablen. Appen bruger da `accounts.authenticate`, `accounts.create_user` og `accounts.get_user` som før. Preview-brugeren og Free-entitlementen bliver stående.

## Næste skridt

Iteration 4 startes ikke. Preview-testen skal bestå med det password, Auth accepterer, før iteration 3 kan blive DONE.
