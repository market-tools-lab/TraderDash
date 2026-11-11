# Drift, overvågning og alarmer

Dato: 9. november 2026. Branch: `feature/monitoring-operations`. Udgangspunkt: `master` `99d28e15e97886b2f5412d872c15e41d6da96768`.

Ingen ny betalingstjeneste er oprettet. Ingen hemmelighed står her. Kontrollen kontakter ikke Production, sender ikke mail og opretter ikke brugere.

## Hvad der kan ses

| Lag | Bevis | Hvor |
| --- | --- | --- |
| Liveness | Processen kan indlæse modulet og svare | `operations.liveness` |
| Readiness | Legacy er klar uden Auth-nøgler. Auth-mode kræver både URL og anon-nøgle, og den slettede preview afvises | `operations.assess` |
| Afhængigheder | Klassificeret nedenfor. De fleste køres af et menneske | `operations.DEPENDENCIES` |

Streamlit Community Cloud har ingen særskilt `/health`. Brugeren ser den almindelige side. En senere container bruger `python -m operations` som Docker `HEALTHCHECK`. Kommandoen skriver tilstande og booleans. Den skriver ikke nøgler, adgangskoder eller forbindelsesstrenge. Image er ikke deployet.

`TRADERDASH_REGISTRATION` og `TRADERDASH_STRIPE` er ikke funktioner. Hvis de sættes til en aktiv værdi, er processen `not_ready`. Det er driftssignaler, ikke kontakter der åbner registrering eller Stripe.

## Kontroller

| Navn | Klasse | Handling |
| --- | --- | --- |
| `github_ci` | AUTOMATIC | `release-gate` på pull requests mod master, push til `feature/**` og push til master |
| `release_flags` | AUTOMATIC | `operations.release_validation` læser koden lokalt |
| `supabase_database` | MANUAL | Se projektstatus i dashboardet. Ingen forespørgsel fra health-kommandoen |
| `supabase_auth` | MANUAL | Åbn login. Opret ikke en bruger |
| `resend` | MANUAL | Læs leveringsloggen. Send ikke en nulstillingsmail |
| `streamlit_legacy` | MANUAL | Åbn `https://traderdash-market.streamlit.app` |
| `streamlit_pilot` | MANUAL | Åbn `https://traderdash-next.streamlit.app` |
| `backups` | MANUAL | Sammenlign backuplisten med `docs/production/DISASTER_RECOVERY.md` |
| `migration_versions` | MANUAL | Sammenlign en udleveret versionsliste med `EXPECTED_MIGRATIONS`. Kør ikke migrationer |
| `recovery_mail` | INCIDENT-ONLY | Kun når en hændelse kræver en ny prøve |
| `preview_branch` | INCIDENT-ONLY | Listen må ikke få en ny branch. `ajbsoudovxstlolojvte` må ikke oprettes igen |
| `restore` | INCIDENT-ONLY | Følg katastrofegendannelsen. Health-kommandoen gendanner ikke |

## Log

Hver linje er ét JSON-objekt på stderr med `category` og `correlation_id`. Id'et er lokalt for processen og kommer ikke fra en person.

Kategorier: `APP_START`, `CONFIG_ERROR`, `AUTH_FAILURE`, `AUTH_RECOVERY_REQUEST`, `DATABASE_FAILURE`, `ENTITLEMENT_FAILURE`, `STRIPE_DISABLED_ATTEMPT`, `ACCOUNT_LIFECYCLE_BLOCKED`, `UNHANDLED_APPLICATION_ERROR`.

Loggen må ikke indeholde adgangskode, recovery-token, access-token, refresh-token, API-nøgle, fuld authorization-header, SMTP-hemmelighed eller en rå e-mail. En nulstillingsanmodning logges uden adressen. Brugeren ser stadig den korte danske tekst. `showErrorDetails` er `none`.

## Efter en merge til master

1. Se at `release-gate` er grøn på master-pushen. Workflowet kørte ikke på master før denne branch.
2. Kør `python -m operations` lokalt. Forvent `ready`, `registration_open` false, Stripe false og sletning false.
3. Åbn legacy-appen og piloten. Legacy skal blive legacy, medmindre dens secret bevidst ændres.
4. Bekræft at registrering, Stripe og sletning har den forventede lukkede tilstand.
5. Bekræft at migrationslisten er uændret, og at der ikke er oprettet en preview-branch.

Automatikken dækker kodeflag, workflow og hemmelighedsfilter. Den åbner ikke Production.

## Alarmer

GitHubs egen besked ved en rød `release-gate` er alarmen. Der er ikke tilmeldt Sentry, Datadog, New Relic, Better Stack, UptimeRobot, Grafana Cloud eller en anden betalt overvågning. De eksisterende værktøjer dækker denne størrelse: testene fanger kodeflag, og dashboardene dækker Supabase, Resend og Streamlit, når et menneske ser efter.

En ny ekstern tjeneste kræver en særskilt beslutning, før den oprettes.

## Drift uden for denne branch

Den kørende pilot følger `feature/public-pilot-finalization`. Denne note ændrer ikke Streamlit-secrets, DNS, Resend eller SMTP. Legacy-appen på master får først koden, når branchen er merget.

`TRADERDASH_AUTH_REGISTRATION` skal mangle eller være `disabled`. Værdien `enabled` gør sundhedstjekket `not_ready`.
