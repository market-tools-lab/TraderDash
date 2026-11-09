# Repository-inventar

Dato: 4. november 2026.

Repositoriet er den versionerede tekniske dokumentation. Hemmelige værdier ligger ikke her. `.streamlit/secrets.toml`, `.env` og `data/` er ignoreret. Resend er valgt og prøvet. Ingen SMTP-hemmelighed ligger her.

## Kørsel

| Fil | Rolle |
| --- | --- |
| `app.py` | Entrypoint. Legacy er default. Auth kun ved `supabase_auth` |
| `supabase_auth.py` | Login, profil og entitlement-læsning |
| `accounts.py`, `account_store.py` | Legacy-konti. Production uden URL opretter ikke SQLite |
| `access.py`, `universes.py`, `plans.py` | 30, 79 og 159 papirer. Checkout er en tekst |
| `account_privacy.py` | Lokal eksport og sletning. Production og preview afvises |
| `stripe_test.py` | Lokal Stripe-test. Flaget er false |
| `Dockerfile` | Python 3.12, `0.0.0.0`, `PORT`. Ikke deployet |

## Data og drift

| Fil | Rolle |
| --- | --- |
| `supabase/migrations/20261030160000_accounts.sql` | Legacy-konti. Ikke kørt igen |
| `supabase/migrations/20261104110000_identity_catalog.sql` | Katalog. Kørt på preview og Production |
| `supabase/migrations/20261104140000_legacy_auth_links.sql` | Link. Kørt på preview og Production |
| `supabase/functions/stripe-webhook/index.ts` | Flag false |
| `docs/production/AUTH_PRODUCTION_GATE.md` | Ikke-hemmelige id'er og gaten |
| `docs/production/STAGING.md` | Miljøer |
| `docs/production/HOSTING.md` | Senere vært, uden DNS-skift |
| `docs/production/ROLLBACK.sql` | Ikke til kørsel |
| `docs/production/AUTH_EMAIL_RECOVERY.md` | Nulstilling med `token_hash`. Én prøve er gennemført |
| `docs/production/MAIL_PROVIDER_DECISION.md` | Resend er valgt og prøvet |
| `docs/production/email/` | Kladder. Nulstillingssedlen er den, prøven brugte |
| `docs/production/DISASTER_RECOVERY.md` | Gendannelse. Ingen hemmeligheder og ingen kørsel mod Production |
| `docs/production/ACCOUNT_LIFECYCLE.md` | Kontolivscyklus. Sletning er ikke slået til |
| `docs/production/OPERATIONS.md` | Drift og lokale sundhedstjek. Ingen ekstern betalingstjeneste |
| `docs/production/PUBLIC_REGISTRATION.md` | Registrering er forberedt og lukket |
| `docs/production/MARKET_TOOLS_PLATFORM.md` | Platform og TraderDash-produkt |
| `docs/production/PRIVACY_NOTICE.md` | Udkast til privatlivsnotits |
| `docs/production/TERMS_OF_USE.md` | Udkast til pilotvilkår |
| `docs/production/PUBLIC_PILOT.md` | Pilotdrift. Registrering er lukket |
| `docs/production/SUPPORT_MAIL.md` | `support@markettools.app` er i drift. Den private modtager står ikke her |
| `captcha_component/index.html` | Isoleret Turnstile-komponent. Hemmeligheden ligger ikke her |

## Uden for mergen

Syv filer under `docs/TRADERDASH_*` er en audit fra 2. november 2026 mod en ældre `master`. De står i `.gitignore`. De er ikke den nuværende kilde.

## Drift uden for git

Ingen hemmelighed står her. Ingen adgangskode, intet token og ingen SMTP-nøgle.

| Felt | Værdi |
| --- | --- |
| Domæne | `markettools.app` |
| Auth-vært | `auth.markettools.app` |
| Udbyder | Resend |
| Afsender | `noreply@auth.markettools.app`, vist som TraderDash |
| Pilot | `https://traderdash-next.streamlit.app` |
| Pilotens kilde | `market-tools-lab/TraderDash`, branch `feature/auth-email-recovery`, `app.py`, Python 3.14 |
| Legacy | `https://traderdash-market.streamlit.app` forbliver på `master` |
| Prøvedato | 4. november 2026 |

Supabase Auth ejer linket og sender mailen over SMTP. Appen kalder `POST /auth/v1/recover` med en allowlistet `redirect_to`. `token_hash` lander på piloten. Appen verificerer, sætter adgangskoden og dropper sessionen. Den fulde URL gemmes ikke.

Kontaktnavne, uden værdier: `TRADERDASH_AUTH_MODE`, `TRADERDASH_SUPABASE_URL`, `TRADERDASH_SUPABASE_ANON_KEY`, `TRADERDASH_PASSWORD_RECOVERY`, `TRADERDASH_AUTH_EMAIL_DELIVERY`, `TRADERDASH_AUTH_REDIRECT_URL`, `TRADERDASH_AUTH_REDIRECT_ALLOWLIST`, `TRADERDASH_TURNSTILE_SITE_KEY`, `TRADERDASH_TURNSTILE_SECRET_KEY`.
