# Supportmail, endnu ikke i drift

Dato: 9. november 2026. Ingen DNS-ændring og ingen postkasse er oprettet her.

`support@markettools.app` er ikke en fungerende indbakke. Den må ikke stå som kontakt, før en mail udefra er modtaget og læst.

`noreply@auth.markettools.app` er kun afsender for Auth-mail gennem Resend. Den må ikke bruges som supportadresse, og support må ikke lægges på `auth.markettools.app`.

## Krav

Adressen skal kunne modtage almindelig mail om piloten, indsigt og sletning. Den skal læses af en person. Afsendelse af Auth-mail forbliver på det eksisterende underdomæne.

Mindste opsætning er Cloudflare Email Routing på zonen `markettools.app`, som allerede bruger Cloudflare-navneservere. Ruten videresender til en postkasse, der allerede læses. Der oprettes ikke en ny mailserver.

Opslag 9. november 2026 mod `1.1.1.1` viste ingen MX for `markettools.app` og ingen MX for `auth.markettools.app`. Opslaget skal gentages, umiddelbart før en post oprettes, så en senere MX ikke bliver overskrevet.

## Virkning

Forventet pris er 0, så længe Email Routing ligger på Cloudflares gratis tilbud. DNS-ændringen er MX på apex `markettools.app` og den TXT-post, Cloudflare viser til routing. `auth.markettools.app` og Resend må ikke ændres.

Det kan rulles tilbage ved at slå ruten fra og fjerne de nye poster. Auth-afsenderen bliver stående.
