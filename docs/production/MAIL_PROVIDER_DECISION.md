# Valg af mailudbyder

Dato: 4. november 2026. Ingen konto er oprettet. Ingen betaling er foretaget. Ingen DNS er ændret. Ingen SMTP-værdi ligger i repositoriet.

Tallene nedenfor er læst den dag på udbydernes egne sider. De kan ændre sig og skal læses igen, før der betales. Dette er ikke en juridisk vurdering.

## Hvad TraderDash skal bruge

Supabase Auth skal sende nulstillingsmailen. Appen skal ikke have sin egen mailklient. Udbyderen skal derfor have SMTP, som Supabase kan udfylde med host, port, bruger, adgangskode, afsenderadresse og afsendernavn.

Mailen er transaktionel login-mail. Den må ikke bruges til nyhedsbrev, og modtageren må ikke tilmeldes en marketingsliste. Åbnings- og kliksporing skal være slået fra.

Repositoriet dokumenterer ikke et afsenderdomæne. Valg af domæne er en særskilt beslutning. Indtil da kan der ikke verificeres DNS.

## Sammenligning

### Supabase indbyggede afsender

Kompatibel uden opsætning. Dokumenteret 4. november 2026: højst 2 mails i timen, og kun til organisationens team-medlemmer. Ingen SLA. Ikke egnet til pilot med rigtige brugere og ikke til offentlig lancering.

### Postmark

Kilde: `https://postmarkapp.com/pricing`, `https://postmarkapp.com/developer/user-guide/send-email-with-smtp` og `https://postmarkapp.com/eu-privacy`, læst 4. november 2026.

- SMTP: `smtp.postmarkapp.com` til transaktionel mail, porte 25, 2525 og 587 med STARTTLS. Broadcast har en anden vært og må ikke bruges til login.
- Pris på siden: Developer 100 mails pr. måned uden overtræk. Basic 15 USD pr. måned fra 10.000 mails, derefter 1,80 USD pr. 1.000. Pro 16,50 USD pr. måned fra 10.000, med længere mulig opbevaring.
- DNS: udbyderen viser SPF, DKIM og Return-Path, når domænet oprettes. Værdierne findes ikke endnu.
- Levering: produktet er bygget til transaktionel mail, med bounce, complaint, suppression og webhooks.
- Drift: en server, en transaktionel stream, SMTP-token. Mindre arbejde end AWS. Sandbox findes.
- GDPR: siden beskriver en DPA og SCC for overførsel ud af EU. Postmark skriver, at data ikke behøver at ligge i EU, når overførslen er dækket. Firmaadressen på siden er i USA. Om en EU-region kan vælges, er ikke bekræftet her og skal læses i DPA'en før accept.
- Basic opbevarer aktivitetsdata i 45 dage ifølge prissiden.

### Resend

Kilde: `https://resend.com/pricing`, `https://resend.com/docs/send-with-smtp` og `https://resend.com/security/gdpr`, læst 4. november 2026.

- SMTP: `smtp.resend.com`. Brugernavn `resend`. Adgangskoden er en API-nøgle. Porte 465 eller 587 er blandt de dokumenterede.
- Pris på siden: Free 0 USD for 3.000 mails pr. måned og højst 100 pr. dag. Pro 20 USD pr. måned for 50.000, overtræk 0,90 USD pr. 1.000.
- DNS: udbyderen udsteder posterne ved domæneverifikation. Værdierne findes ikke endnu.
- Levering: tilstrækkelig til lav volumen. Åbnings- og kliksporing indgår i produktet og skal slås fra for login-mail.
- Drift: enkel SMTP. Log for SMTP-serveren udleveres ikke ifølge SMTP-siden. Sendte mails kan ses i deres tabel.
- GDPR: siden siger, at en DPA træder i kraft ved oprettelse af konto, og at mail og logs beholdes i 30 dage på Free, Pro og Scale. Hvor data fysisk ligger, og om en EU-region kan låses, stod ikke klart på de sider og skal bekræftes før accept.

### Amazon SES

Kilde: `https://aws.amazon.com/ses/pricing/`, læst 4. november 2026.

- SMTP findes. Prisen på siden: nye konti fra 21. juli 2026 starter på Essentials, 0,16 USD pr. 1.000 for de første 10 millioner. À la carte er 0,10 USD pr. 1.000 uden månedligt minimum. Vedhæftninger kan koste ekstra.
- Drift er den tunge del: AWS-konto, sandbox, ansøgning om produktion, IAM, bounce- og complaint-håndtering og et sæt DNS-poster. Det er et ekstra driftssystem for én operatør.
- GDPR-aftalen ligger i AWS' egen aftalepakke og skal hentes der. Den er ikke citeret her.
- Billigst ved høj volumen. Ikke det enkleste første valg.

## Anbefaling

Foretrukken udbyder: Postmark.

Grund: Supabase skal bruge SMTP, og Postmark skiller transaktionel mail fra broadcast. Bounce, complaint og suppression er en del af produktet. Prisen er et lille fast beløb, ikke et AWS-projekt. DPA'en er offentlig. 100 gratis mails rækker kun til en kort prøve. En rigtig pilot kræver Basic eller tilsvarende.

Reserve: Resend.

Grund: lavere startpris, inklusive et brugbart gratis loft, og en kort SMTP-opskrift. Den er reserven, hvis den månedlige Postmark-pris ikke skal betales endnu. Sporing skal slås fra, og dataregionen skal bekræftes.

Udskudt: Supabase' indbyggede afsender, fordi loftet og modtagerbegrænsningen ikke bærer en lancering. Amazon SES, indtil volumen eller en eksisterende AWS-drift gør det ekstra arbejde rimeligt.

Beslutningen er ikke truffet. Theis godkender udbyderen, før der oprettes en konto.

## DNS, når en udbyder og et domæne er valgt

Ingen poster er kendt endnu. Udbyderen skal udstede værdierne. Principper:

- Brug et underdomæne kun til transaktionel mail, for eksempel `auth` under det domæne Theis vælger. Roddomænet bruges ikke som afsender, hvis det allerede sender almindelig post.
- Præcis én SPF-TXT pr. værtsnavn. En ny udbyder må ikke tilføjes ved at oprette en ekstra SPF-post.
- DKIM slås til.
- DMARC starter bevidst, typisk med overvågning, og strammes først når afvisninger er forstået. Den konkrete politik vælges ved opsætningen.
- Verifikation og eventuel return-path eller bounce-vært kommer fra udbyderen.
- Sporingsdomæne bruges ikke til login-mail.
- Rollback er at fjerne de poster, udbyderen bad om, og slå custom SMTP fra. Eksisterende post på andre værtsnavne røres ikke.

## Data

Udbyderen får modtageradressen, afsenderadressen, emnet og selve nulstillingsmailen, herunder et engangstoken i linket. Formålet er at levere login-mailen. Der sendes ikke navn, plan, adgangskode eller portefølje.

Krav før ibrugtagning, uden at dette er en færdig juridisk konklusion: databehandleraftale, liste over underdatabehandlere, hvor data ligger, hvor længe logs beholdes, hvem der ejer udbyderkontoen, og hvordan et læk hos udbyderen opdages. Sletning af en TraderDash-konto sletter ikke automatisk udbyderens logs. Det skal stå i driftsnoten, når udbyderen er valgt.

Login-mail og markedsføring holdes adskilt. Der oprettes ikke et nyhedsbrev i denne omgang.
