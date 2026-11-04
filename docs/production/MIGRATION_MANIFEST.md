# Production migration manifest

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Denne fil er en kørselsliste. Ingen sætning her er kørt mod Production. Preview er `ajbsoudovxstlolojvte` / `https://ajbsoudovxstlolojvte.supabase.co`.

SHA-256 er taget af filernes bytes. Filnavnets tidsstempel og preview-historikkens version er ikke det samme, fordi preview fik migrationen et senere tidspunkt.

## Må ikke køres igen

| Rækkefølge | Fil | SHA-256 | Afhængighed | Preview | Production |
| --- | --- | --- | --- | --- | --- |
| 0 | `supabase/migrations/20261030160000_accounts.sql` | `5f3118ea88414be5ee600ed6d966d05a5800bb40410a3a8752294c4a4ae87235` | Ingen. Opretter `public.users` | Allerede kørt som `20261030160000` | Forventes allerede. Må ikke køres igen |

Backup-gaten er grøn. Verified 2026-11-04 på Traderdash / `main` / PRODUCTION. Seneste synlige restore-punkt er 2026-11-04 02:58:26 UTC, typen er PHYSICAL, og restore er tilgængelig. Restore er ikke testet og ikke udført. Theis gav 2026-11-04 eksplicit GO til de to filer nedenfor. De er kørt på `wxvobyifckbpnqfbnlxl` og ikke på preview.

## Fremad, først efter eksplicit GO

| Rækkefølge | Fil | SHA-256 | Afhængighed | Preview | Production |
| --- | --- | --- | --- | --- | --- |
| 1 | `supabase/migrations/20261104110000_identity_catalog.sql` | `fdf53d809b5811baf43afe577be9c86e5fe475c5e1fab20b3bacfb6421573951` | `public.users` findes og er urørt. `auth.users` findes | Kørt som `20261104112720` | Kørt som `20261104143544` |
| 2 | `supabase/migrations/20261104140000_legacy_auth_links.sql` | `671d8e9e7cd6d6e87b3e668b3b3bf5048a817093f55e07dd75c922f018c3a0c9` | Rækkefølge 1. Ingen ændring af `public.users` | Kørt som `20261104130624` | Kørt som `20261104143902` |

Iteration 7 ændrede ikke skemaet. Der er ingen tredje migrationsfil.

Filhovedet i identity catalog siger stadig `NOT APPLIED`. Det er det oprindelige forberedelsesstempel, og den statiske test låser formuleringen. Preview-historikken og Production-historikken er sandheden for de to databaser. Production er kørt som `20261104143544` og `20261104143902`.

## Forventede objekter

Efter rækkefølge 1:

- `public.products` med `traderdash`
- `public.plans` med `free` rank 0, `nordic` rank 1, `international` rank 2
- `public.profiles`
- `public.entitlements`
- RLS og FORCE RLS på de fire tabeller
- Authenticated kan læse egen profil og egen entitlement og kan ikke skrive entitlement
- Triggeren på `auth.users` opretter kun en profil

Efter rækkefølge 2:

- `public.legacy_auth_links`
- RLS og FORCE RLS
- Ingen policy og ingen grant til `anon` eller `authenticated`
- Ingen e-mail, password eller token i tabellen

## Verifikation, læs kun

Kør først når Production-projektets ref er bekræftet forskellig fra `ajbsoudovxstlolojvte`.

```sql
select version, name from supabase_migrations.schema_migrations
where version in ('20261104110000', '20261104112720', '20261104140000', '20261104130624')
order by version;

select code from public.products order by code;
select code, rank from public.plans order by rank;

select c.relname, c.relrowsecurity, c.relforcerowsecurity
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public'
  and c.relname in ('products', 'plans', 'profiles', 'entitlements', 'legacy_auth_links');

select count(*) as entitlement_write_policies
from pg_policy
where polrelid = 'public.entitlements'::regclass
  and polcmd in ('a', 'w', 'd', '*');
```

Forventet skrivetal for entitlements er 0. `public.users` må have samme rækketal som før migrationen.

## Rollback

`docs/production/ROLLBACK.sql` er ikke kørt. Den sletter ikke `public.users` og ikke `auth.users`. En restore fra backup er den foretrukne vej, hvis rækker allerede er migreret. Drop-scriptet er kun til et katalog, der endnu ikke har piloter.

Appens rollback er `TRADERDASH_AUTH_MODE=legacy` eller en fjernet variabel. Cloud sættes ikke i denne iteration.
