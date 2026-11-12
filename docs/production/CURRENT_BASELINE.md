# Nuværende production-baseline

Dato: 12. november 2026. Dette er den gældende ikke-hemmelige tilstand. Ældre noter i `docs/production` og `docs/iterations` er historiske, når de siger noget andet.

## GitHub

Kanonisk repo: `market-tools-lab/TraderDash`. `master` er `aefb8fc676f8596d10ca800203fe00a6eb0e0213`, merge-commit for pull request #8. Forældrene er `25088d12c4e72ae5670a1bf5b417be82708270fc` og `118caae7036a0d365783e3587e61ee25316fa026`. `feature/public-pilot-finalization` er beholdt. Workflowet `.github/workflows/release-gate.yml` kører på pull requests mod `master`, push til `feature/**` og push til `master`. Det bruger Python 3.12 og kontakter ikke Production.

## Applikationer

| App | Rolle | Kilde |
| --- | --- | --- |
| `traderdash-market` | Legacy på `https://traderdash-market.streamlit.app` | `master`, `app.py`, Auth-mode legacy |
| `traderdash-next` | Auth-pilot på `https://traderdash-next.streamlit.app` | Stadig `feature/public-pilot-finalization`, `app.py`, Python 3.14 |

`traderdash-next` er ikke flyttet til `master` i merge-blokken. Community Cloud skifter ikke branch af sig selv.

## Domæner

`markettools.app` er platformen. `auth.markettools.app` sender Auth-mail. `support@markettools.app` modtager support via Cloudflare Email Routing.

## Supabase

Projektet Traderdash, ref `wxvobyifckbpnqfbnlxl`, region `eu-west-1`, er `ACTIVE_HEALTHY`. Den eneste branch er default `main`. Der er ingen preview.

Anvendte migrationer: `accounts`, `identity_catalog`, `legacy_auth_links`, `provision_traderdash_free`, `provision_traderdash_free_self`. Filnavn og historikversion er ikke altid ens. `docs/production/MIGRATION_MANIFEST.md` er listen. Anvendt SQL ændres ikke.

`provision_traderdash_free(uuid)` kan kaldes af `postgres` og `service_role`. `provision_traderdash_free_self()` tager intet id, læser `auth.uid()` og kan kaldes af `authenticated`.

## Mail, DNS og Turnstile

Resend sender transaktionsmail som `noreply@auth.markettools.app`. Åbnings- og kliksporing er slået fra. Cloudflare ejer DNS for domænerne, Email Routing for support og Turnstile-widgettet Market Tools Registration Pilot for `traderdash-next.streamlit.app`.

## Konti

Der er to Auth-brugere og to profiler. Den migrerede pilot har én aktiv TraderDash Free-entitlement med kilden `migration` og linket `pilot-i9`. Fixturen `markettools.pilot@proton.me` har én aktiv TraderDash Free-entitlement med kilden `signup`. Legacy har én række med planen `free`. Nordic, International og Stripe-hændelser er nul.

## Sikkerhed

Registrering er lukket. Stripe er slået fra. Sletning er slået fra. Ingen hemmelige værdier står i denne fil. Repositoriet er den tekniske kilde. D-drevet indgår ikke i driften. Bekræftelsens glade vej og reserven ved login står i `SIGNUP_CONFIRMATION.md`. En merge af den tekst kræver ikke en ny tilmelding.
