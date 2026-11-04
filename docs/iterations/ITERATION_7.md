# Iteration 7

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE**.

Cutover for den kendte testkonto er bevist på preview med en syntetisk kopi. Production er ikke læst og ikke skrevet. Iteration 8 er ikke startet.

## Target

| Kontrol | Resultat |
| --- | --- |
| Project ref | `ajbsoudovxstlolojvte` |
| Branch | `supabase-auth-test` |
| URL | `https://ajbsoudovxstlolojvte.supabase.co` |
| Production | Ikke kontaktet |
| Streamlit Cloud | Ikke ændret |
| `master` | Står på `4d292dae4a43c114df8818d4d7991d9b37149736` |

Den stående preview-bruger `markettools-auth-test@example.invalid`, id `63ffe985-0e7e-48bd-b41b-d1741330257a`, er ikke ændret og er ikke slettet.

## Hvad der ikke blev læst

Der findes ingen credential-fri læsning af Production. `account_store` kræver `DATABASE_URL`. Den del blev stoppet.

Kendte fakta fra opgaven er brugt i stedet: legacy-plan `free` og TraderDash Free er 30 papirer. `subscription_status` er sat til `free`, fordi det er det par, kataloget oversætter til en aktiv Free-entitlement. Produktions-id er ikke kopieret. Legacy-password og `password_hash` er ikke kopieret.

## Mapping

Referenceadressen `traderdashtesttest@example.dk` er kun en etiket. Den er ikke gemt på preview og er ikke brugt til at sende mail.

| Felt | Preview-kopi |
| --- | --- |
| Legacy-id | `legacy-mig-i7pilot` |
| E-mail | `markettools-mig-i7pilot@example.invalid` |
| Plan | `free` |
| `subscription_status` | `free` |
| Migrationsreference | `pilot-i7` |

Auth-brugeren blev oprettet med et nyt preview-password. Hashen er en ny bcrypt og er ikke den gamle scrypt-streng. Legacy-rækken fik en anden ny bcrypt, fordi `password_hash` ikke må være tom. De to hash-værdier var ikke ens. Ingen af dem er produktionshashen.

Migrationsinput er kun `user_id`, `email`, `plan` og `subscription_status`. SQL til link og entitlement indeholder ikke password, token eller referenceadressen.

## Forløb

Dry-run skrev intet. Efter oprettelsen fandtes profilen, og der var 0 links og 0 entitlements.

Den faktiske migration skrev ét link med status `migrated` og én aktiv entitlement på produktet `traderdash` og planen `free`. Kilden er `migration`.

Lokal AppTest i `supabase_auth` mod preview:

| Kontrol | Resultat |
| --- | --- |
| Plan | `free` |
| Papirer | 30 |
| Auth-id | samme som den oprettede preview-bruger |
| Password i sessionen | nej |
| Referenceadresse i visningen | nej |
| Undtagelser | 0 |
| Logout | token og user id væk |
| Nyt login | plan `free` igen |

Markedskaldene var stubbet. Processen bandt ikke en Cloud-instans. `DATABASE_URL` var ikke sat. Recover og signup blev ikke kaldt, så der blev ikke sendt mail.

## Tilbage på preview

Pilotkopien er slettet. Cascade fjernede profil, identity, link og entitlement. Legacy-rækken blev slettet for sig.

| Kontrol | Resultat |
| --- | --- |
| Auth-brugere | 1 |
| Stående bruger | 1 |
| Andre Auth-brugere | 0 |
| Profiler | 1 |
| Entitlements | 0 |
| Links | 0 |
| `public.users` | 0 |
| Rest af piloten | 0 |

## Tests

`python -m unittest discover -s tests`

90 tests. 81 bestod, 0 fejlede, 9 sprunget over. Varighed 16,0 sekunder. De tre nye cutover-tests er med. De ni overspringelser er de eksisterende placeholders og preview-tests uden miljø.

Streamlit skrev `missing ScriptRunContext` under AppTest. Biblioteket siger, at advarslen kan ignoreres i bare mode.

## Rollback

Sæt `TRADERDASH_AUTH_MODE=legacy`, eller fjern variablen. Et slettet link sletter ikke `public.users`. Cloud er stadig `legacy`.

## Ikke gjort

- Ingen produktionsbruger er læst eller migreret
- Ingen åben registrering
- Ingen mailleverandør
- Cloud-flaget er ikke sat
- Ingen betaling eller planændring
- Iteration 8 er ikke startet
