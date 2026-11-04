# Iteration 14

Dato: 4. november 2026. Branch: `feature/supabase-auth`. Udgangspunkt: `c8cb417`.

Status: **DONE**. Integrations- og regressionsaudit. Ingen ny produktfunktion.

## Verificeret baseline

| Kontrol | Resultat |
| --- | --- |
| Branch | `feature/supabase-auth` |
| `master` og `origin/master` | `4d292da` |
| Production | `wxvobyifckbpnqfbnlxl`: 1 legacy, 1 Auth, 1 profil, 1 migreret link, 1 aktiv Free, plan `free`, scrypt, 0 stripe-events |
| Stripe-flag | false i `stripe_test.py` og i webhook-funktionen |
| Registrering | skjult i Auth-mode |
| Sletteknap | findes ikke i `app.py` |
| Papirer | 30, 79 og 159 |

## Rettelse

`.streamlit/config.toml` sætter `showErrorDetails` til `none`. Auth-fejl har allerede deres egen danske tekst. Ufangede undtagelser vises ikke som stack trace.

`tests/test_release_gates.py` låser default-login, det lukkede Stripe-flag, de beskyttede projekter, papirtallene og at de syv historiske auditfiler er ignoreret.

`python -m unittest discover -s tests`: 117 tests, 0 fejl, 9 sprunget over.

## Ikke gjort

- Ingen merge
- Ingen ændring af Production-data
- Ingen Stripe i drift
