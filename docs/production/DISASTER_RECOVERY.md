# Gendannelse

Dato: 9. november 2026. Branch: `feature/disaster-recovery`. Udgangspunkt: `master` `ad4d6cfe7b791f26fae96565ee626c67d57e33f0`.

Dette er runbogen for en hændelse. Den gendanner ikke Production af sig selv. Ingen adgangskode, nøgle eller token står her.

Production er Traderdash, `wxvobyifckbpnqfbnlxl`, region `eu-west-1`. Organisationen er Pro. Der er én default-branch, `main`. Preview-branchen `supabase-auth-test` / `ajbsoudovxstlolojvte` er slettet og må ikke oprettes igen.

## Hvad der kan gendannes

En databasebackup er ikke en hel tjeneste.

| Lag | Kilde | Backup | Gendannelse | Hemmelighed | Theis skal handle | Tab hvis kilden mangler |
| --- | --- | --- | --- | --- | --- | --- |
| Kode | GitHub `market-tools-lab/TraderDash` | Git-historik | Checkout eller revert af en kendt commit. CI er `release-gate` | Nej | Ja, ved deploy | App og migrationer |
| Database | Supabase Pro, daglig fysisk backup | Dashboard, Database, Backups | Restore i samme projekt. Projektet er nede imens | Nej i denne fil | Ja | Rækker siden sidste backup |
| Auth-rækker | Samme database, skema `auth` | Med i databasebackuppen | Med i database-restore | Adgangskoder er hash, ikke klartekst | Ja | Login for den ene pilot |
| Katalog, profil, link, entitlement | `public` | Med i databasebackuppen | Med i database-restore | Nej | Ja | Plan og pilot-i9 |
| Migrationhistorik | `supabase_migrations` i databasen og filerne i Git | Begge | Filerne genopbygger skemaet. Versionsnumrene i Production er ikke filnavnene | Nej | Nej for filerne | Skemaet kan bygges fra Git |
| Storage-filer | Supabase Storage | Ikke med i databasebackuppen | Ingen filer at hente i dag | Nej | Nej | Intet kendt filtab. Metadata alene er ikke filerne |
| Edge Function | Git `supabase/functions/stripe-webhook` | Git | Deploy fra Git. Flaget er false | Nej | Ja, hvis funktionen mangler | Webhooken, som ikke opdaterer planer |
| Auth-indstillinger | Supabase-dashboard | Ikke bevist som en del af backuppen | Sættes igen fra denne note og den sikre opbevaring | Værdierne ja | Ja | SMTP, redirects, skabelon |
| Streamlit | Community Cloud | Appens repo, branch og Python | Appen peger stadig på samme repo. Secrets sættes igen | Secrets ja | Ja | Login på den app, hvis secrets mangler |
| Resend | Resend-kontoen | Udbyderens egen konto | Domænet `auth.markettools.app` verificeres igen. SMTP-nøglen sættes i Supabase | Nøglen ja | Ja | Nulstillingsmail |
| DNS | Cloudflare for `markettools.app` og `auth.markettools.app` | Udbyderens zone | Posterne sættes igen. Værdierne står ikke her | Nej i Git | Ja | Afsenderdomænet |
| Legitimation | Den sikre opbevaring Theis allerede bruger | Ikke Git | Hent eller roter. Kopier ikke værdien hertil | Ja | Ja | Den tjeneste, nøglen låser |

Daglige backups på Pro gemmes i 7 dage. De er fysiske. Et slettet Supabase-projekt sletter også sine backups. PITR er et tilkøb og er ikke bekræftet slået til på dette projekt. Seneste nedskrevne fysiske restore-punkt før denne note er 4. november 2026 02:58:26 UTC. Listen er ikke genlæst i dashboardet i denne omgang. Download af den fysiske backup er ikke den vej, dokumentationen anbefaler. En logisk kopi laves med Supabase CLI `db dump` og blev ikke taget her, fordi den ville indeholde produktionsrækker.

Databasebackuppen indeholder databaseskemaerne, herunder `auth` og `public`. Den indeholder ikke Streamlit-secrets, Resend-nøglen, DNS-poster, dashboardets SMTP-felter, Edge Functions eller GitHub.

## Mål

RPO er hvor meget data der højst må mangle. RTO er hvor længe gendannelsen højst bør tage for denne ene operatør. Tallene er driftsmål, ikke en målt øvelse mod Production.

| Trin | RPO | RTO | Hvorfor | Krav | Pris |
| --- | --- | --- | --- | --- | --- |
| Pilot nu | 24 timer | Kode 30 minutter. Database 2 timer. Hel tjeneste 8 timer | Én bruger og sjældne skrivninger. Pro har daglig backup | Git plus den daglige backup. Secrets ligger uden for Git | Ingen ny fast pris |
| Offentlig lancering | 24 timer, indtil PITR vælges | 4 timer | Rigtige konti tåler ikke en hel dags tab, hvis der skrives hver dag | Offsite logisk dump eller PITR. Lille compute kræves til PITR | PITR 7 dage er offentliggjort omkring 100 USD pr. måned og er ikke dækket af spend cap |
| Betalt lancering | 2 minutter i worst case med PITR | 1 time for databasen, 4 timer for hel tjeneste | Betaling og konti skal kunne rulles til lige før hændelsen | PITR 7 dage, mindst Small compute, og secrets uden for Git | Omkring 100 USD pr. måned for PITR plus compute. Læs prisen igen før køb |

## Tre hændelser

### A. Koden er gået i stykker, databasen er rask

Opdagelse: appen viser en ny fejl efter et deploy, og rækketallene er uændrede.

Inddæmning: lad databasen være. Peg ikke `traderdash-market` om, og sæt ikke `TRADERDASH_AUTH_MODE` på den.

Kilde: Git. Sidste kendte gode `master` før en dårlig commit.

Mål: den Streamlit-app, der kører den dårlige kode. Legacy bliver på `master`. Piloten bliver på sin nuværende branch, indtil den bevidst flyttes.

Validering: legacy viser Log ind og Opret konto. Piloten viser lukket registrering. Ingen ny nulstillingsmail.

Overgang: Community Cloud bygger den valgte commit. Secrets ændres ikke.

Tilbage: den forrige gode commit.

RTO: omkring 30 minutter. RPO for data: ingen, fordi databasen ikke røres.

### B. Rækker er ændret eller slettet, projektet findes

Opdagelse: den ene Auth-bruger, profilen, `pilot-i9` eller Free-entitlement mangler, og koden er ikke ændret.

Inddæmning: stop med at skrive. Send ikke en ny nulstillingsmail. Kør ikke migrationer.

Kilde: seneste daglige backup før fejlen.

Mål: først en vurdering af hvad backuppen indeholder. Selve restore i Supabase erstatter projektdatabasen og må ikke bruges som prøve. Den køres kun, når tabet er bekræftet, og Theis bekræfter i dashboardet.

Validering: ét Auth-id, én profil, ét link `pilot-i9`, én aktiv Free-entitlement, én legacy-række, nul `stripe_events`.

Overgang: projektet er utilgængeligt under restore. Bagefter logges der ind på piloten uden at sende mail.

Tilbage: en tidligere backup, hvis den valgte er for ny og allerede indeholder fejlen.

RTO: omkring 2 timer for denne lille database. RPO: op til 24 timer.

### C. Supabase-projektet er væk eller ubrugeligt

Opdagelse: projektet svarer ikke, eller det er slettet. Backups på et slettet projekt er væk.

Inddæmning: opret ikke et nyt projekt uden et bevidst GO. Rør ikke DNS, Resend eller Streamlit-secrets i panik.

Kilde: Git til skema og app. En tidligere logisk dump, hvis en sådan findes uden for Git. Den findes ikke i denne note.

Mål: et nyt projekt, først isoleret. Production-ref `wxvobyifckbpnqfbnlxl` kan ikke genoplives fra Git alene.

Validering: skemaet matcher filerne. Syntetiske rækker bruges, indtil en dump er lagt på. Auth-mail, SMTP og redirects sættes fra den sikre opbevaring.

Overgang: først når login mod det nye projekt er prøvet, og legacy stadig er legacy.

Tilbage: behold det gamle projekt, hvis det kun var midlertidigt nede.

RTO: omkring 8 timer. RPO: alt der ikke ligger i Git eller i en offsite dump. Auth-hashen kan ikke genfindes fra Git.

Kode-rollback, database-restore og fuld genopbygning er tre forskellige handlinger. Brug kun én af dem.

## 1. Stop og klassificer hændelsen

Skriv tidspunkt, hvad der er galt, og hvilken app der viser det. Vælg A, B eller C ovenfor. Gæt ikke.

## 2. Bevar spor

Notér commit, projekt-ref og om appen svarer. Kopier ikke secrets, adgangskoder eller recovery-links ind i chatten eller Git.

## 3. Stop skrivninger hvis det er nødvendigt

Ved B og C: lad være med at migrere, importere eller sende nulstillingsmail. Ved A: lad databasen være.

## 4. Find sidste kendte gode tilstand

Kode: `git log` på `master` og på pilotens branch. Data: seneste backup før fejlen. Den 4. november 2026 var et fysisk punkt synligt. Dagens liste skal læses i dashboardet, før der vælges et punkt.

## 5. Skeln kode, database og konfiguration

Kode fejler, mens rækketallene er de samme: A. Rækker mangler, mens appen er den kendte commit: B. Projektet eller dashboardet er væk: C. Manglende SMTP eller DNS er konfiguration, ikke en database-restore.

## 6. Vælg gendannelseskilde

Git for kode og skemafiler. Dashboardets backup for rækker. Den sikre opbevaring for nøgler. Cloudflare for DNS. Resend for afsenderen. Streamlit for appens branch og secrets.

## 7. Gendan først til et isoleret mål

Kør aldrig restore oven på Production som en prøve. En lokal Postgres må kun høre på `127.0.0.1`. Den må ikke pege på `wxvobyifckbpnqfbnlxl` eller på den slettede preview. Brug syntetiske rækker. `scripts/local_restore_rehearsal.py` gør det og sletter bagefter den lokale database.

## 8. Validér

Skemaet har `users`, `stripe_events`, `products`, `plans`, `profiles`, `entitlements` og `legacy_auth_links`. Kataloget er `traderdash` med `free`, `nordic` og `international`. Profil, link og entitlement peger på samme syntetiske id. Et andet aktivt entitlement på samme produkt afvises. Linkets identitet kan ikke ændres. RLS er tvunget på kataloget, profilen, entitlement og linket. En authenticated-rolle ser kun sin egen profil og entitlement og har ingen rettighed til linket.

Auth-login, JWT, SMTP og adgangskode kontrolleres ikke af den lokale prøve.

## 9. Skift først over hvis det er nødvendigt

Legacy forbliver legacy. Piloten flyttes ikke i en kodefejl, medmindre det er pilotens egen commit, der er gal. Database-restore i Supabase er selve overgangen og kræver Theis' bekræftelse i dashboardet.

## 10. Validér efter gendannelse

Én Auth-bruger med det kendte id, bekræftet mail, én profil, `pilot-i9` med status `migrated`, én aktiv Free-entitlement med kilde `migration`, én legacy-række med plan `free`, nul betalte entitlements og nul `stripe_events`. Migrationerne er stadig de tre, der allerede er kørt. De køres ikke igen. Stripe forbliver slået fra. Registrering forbliver lukket.

## 11. Skriv hændelsen ned

Dato, type A, B eller C, kilde, hvad der blev gendannet, og hvad der mangler. Skriv ikke secrets.

## 12. Fjern midlertidige ressourcer

Stop den lokale Postgres og slet dens datamappe. Slet en midlertidig cloud-database, hvis en senere øvelse har fået lov at oprette en. Efterlad ikke en preview-branch. Production ændres ikke af oprydningen.

## Lokal prøve

9. november 2026 blev skemaet bygget fra `supabase/migrations/20261030160000_accounts.sql`, `supabase/migrations/20261104110000_identity_catalog.sql` og `supabase/migrations/20261104140000_legacy_auth_links.sql` på en lokal Postgres 17, kun på `127.0.0.1`. Der blev brugt syntetiske rækker. Ingen produktionsrække blev kopieret. Prøven blev slettet bagefter, inklusive database og binære filer.

Resultat: relationerne holdt, begrænsningerne afviste et ekstra aktivt entitlement og en ændret link-identitet, og RLS viste én profil og én entitlement. Linktabellen afviste authenticated. Auth-semantik blev ikke prøvet.

## Hemmeligheder, kun som kort

Værdierne ligger ikke her og blev ikke læst fra en adgangskodehuske.

| Kategori | System | Formål | Opbevaring | Kan roteres | Hvis den mangler | Ejer |
| --- | --- | --- | --- | --- | --- | --- |
| Databaseforbindelse | Supabase | Legacy-appens database | Streamlit-secrets og den sikre opbevaring | Ja | Legacy kan ikke læse konti | Theis |
| Auth-URL og anon-nøgle | Supabase | Pilotens login | Kun pilotens Streamlit-secrets | Ja | Piloten kan ikke logge ind | Theis |
| Supabase secret key | Supabase | Privilegeret API. Ikke i appen | Den sikre opbevaring | Ja | Admin-kald kan ikke køres | Theis |
| Resend SMTP | Resend via Supabase | Nulstillingsmail | Kun Supabase SMTP | Ja | Mail sendes ikke | Theis |
| Streamlit-adgang | GitHub-login til Community Cloud | Deploy og secrets | GitHub-kontoen | Ja | Apps kan ikke ændres | Theis |
| Cloudflare | DNS for de to domæner | Afsenderdomænet | Cloudflare-kontoen | Ja | Mail fra underdomænet fejler | Theis |
| GitHub | `market-tools-lab/TraderDash` | Kode og CI | GitHub-kontoen | Ja | Kode kan ikke gendannes | Theis |

## Kendt sag ved siden af

Logget-ind skift af adgangskode afviser stadig enhver anden vært end den slettede preview. Det er ikke nulstillingsmailen. Nulstillingen er prøvet og virker på piloten. Sagen hører til kontolivscyklus før en offentlig lancering og blokerer ikke denne gendannelse.

## Kontakter

GitHub: `market-tools-lab/TraderDash`. Supabase: projektet Traderdash. Streamlit Community Cloud: `traderdash-market` på `master` og `traderdash-next` på `feature/auth-email-recovery`, begge `app.py` og Python 3.14. Resend: afsender `noreply@auth.markettools.app`. Cloudflare: `markettools.app` og `auth.markettools.app`.
