# Iteration 13

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE** som lokal eksport og sletning. Production og preview afvises.

## Resultat

`account_privacy.py` eksporterer e-mail, plan, status og tid. Hash og token kommer ikke med. Sletning kræver en lokal target og bekræftelsen `DELETE-LOCAL-ACCOUNT`.

Production `wxvobyifckbpnqfbnlxl`, preview `ajbsoudovxstlolojvte` og de kendte pilot-id'er afvises. En lokal bruger, entitlement og link fjernes sammen.

Modulet åbner ikke en database.

## Ikke gjort

- Ingen sletning i Production
- Ingen sletning af pilotbrugeren
- Ingen knap i appen
- Ingen Stripe
