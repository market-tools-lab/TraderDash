# Kontolivscyklus

Dato: 9. november 2026. Branch: `feature/account-lifecycle`. Udgangspunkt: `master` `f6daf64a510e08e490f2c28d8c44882c51630884`.

Ingen konto slettes her. Ingen hemmelighed står her. Registrering er lukket. Stripe er slået fra. Knappen til sletning vises ikke.

## Tilstande

En konto er `active`, indtil en senere fase må sætte `deletion_pending`. Den fase er ikke bygget. `account_lifecycle.DELETION_EXECUTION_ENABLED` er false, og `DELETION_UI_ENABLED` er false.

## Adgangskode

Nulstilling via mail er en anden vej end skift mens man er logget ind. Nulstillingen kræver begge leveringskontakter og en allowlistet redirect. Den er prøvet på piloten.

Logget-ind skift kræver den aktuelle session, den samme adgangskodepolitik på 12 til 128 tegn, og det Supabase-projekt, som `TRADERDASH_SUPABASE_URL` peger på. Den slettede preview er ikke et gyldigt mål. Legacy-login har ikke formularen. Efter et gyldigt skift ryddes den lokale session, og appen beder Auth logge alle sessioner ud. Brugeren skal logge ind igen. Denne omgang har ikke skiftet pilotens rigtige adgangskode.

## Sletning, to faser

Fase 1 er et ønske. Kontoen bliver `deletion_pending` og kan ikke bruges. Fase 2 er den endelige sletning efter 14 dage. I vinduet kan Theis eller brugeren annullere ønsket, og kontoen er `active` igen. Efter fase 2 kan appen ikke genskabe kontoen. En databasebackup er en særskilt katastrofegendannelse, ikke en fortryd-knap.

Fase 1 og fase 2 skriver ikke endnu. `plan_deletion` er en tør gennemgang. `apply_deletion` afviser altid.

## Data

| Kategori | Handling | Hvorfor |
| --- | --- | --- |
| `auth.users` | DELETE | Auth-identiteten fjernes til sidst |
| `auth.identities` | DELETE | Følger Auth-brugeren |
| `profiles` | DELETE | Følger Auth-brugeren |
| `legacy_auth_links` | DELETE | Linket har ingen mening uden begge sider |
| `entitlements` | DELETE for fri konto, RETAIN hvis betalt | En aktiv betaling må ikke forsvinde stille |
| `public.users` | ANONYMIZE hvis legacy-rækken findes, ellers N/A | Rækken er ikke en fremmednøgle til Auth |
| `stripe_events` | RETAIN | Hændelserne er ikke personens kontorække |
| Sessioner | DELETE | Et slettet login må ikke blive hængende |
| Abonnementsreference | DETACH hvis betalt, ellers N/A | Referencen kan skulle bruges til afstemning |

Der er ingen anden app-specifik personrække. Kurser og papirer er ikke knyttet til en bruger.

## Fire slags konti

Auth-only: profil og entitlement slettes med Auth-brugeren. Ingen legacy-række.

Migreret: Auth-brugeren, profilen, linket og entitlement slettes. Legacy-rækken anonymiseres, så mail og adgangskodehash ikke bliver stående.

Legacy-only: ingen Auth-række. Legacy-rækken anonymiseres. Registrering er stadig lukket, så samme mail kan ikke oprette en ny konto i dag.

Fremtidig betalt konto: sletning blokeres, mens abonnementet er `active`, `trialing` eller `past_due`, eller en entitlement har kilde `subscription` eller `purchase` og status `active`. Afregning, indsigelse og lovpligtig opbevaring kræver en særskilt beslutning før en betalt lancering. Den beslutning er ikke truffet her.

## Beskyttelse

Kendte id'er i `account_privacy.PROTECTED_IDS` kan ikke slettes. Beskyttelsen følger id, ikke mail. Production-ref og den slettede preview er ikke gyldige mål. Manglende mål afvises. En tør gennemgang ændrer ingen felter.

## Tilbage

Så længe execution er slået fra, er der ingen sletning at rulle tilbage. Et senere `deletion_pending` rulles tilbage ved at fjerne markeringen inden for 14 dage. Efter endelig sletning er der ingen kontogendannelse i appen.
