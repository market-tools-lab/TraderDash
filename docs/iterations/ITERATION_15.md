# Iteration 15

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE** som driftsklarhed. Preview og Production er ikke skrevet til.

Driftskortet er `docs/production/STAGING.md`.

Piloten `https://traderdash-next.streamlit.app` bruger Production Auth. Preview `ajbsoudovxstlolojvte` er låst til nulstilling og må ikke være pilotens mål. Legacy-appen beholder sit eget secret-sæt.

Et push til `feature/supabase-auth` redeployer kun piloten. `master` redeployer ikke legacy-appen.
