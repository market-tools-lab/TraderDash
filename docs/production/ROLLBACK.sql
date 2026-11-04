-- NOT FOR EXECUTION.
-- Iteration 8 does not run this file on Production or preview.
-- It does not delete public.users, auth.users, or passwords.
-- Prefer a completed Production backup restore if any pilot row exists.
-- Confirm the project ref is the intended target and is not a preview branch
-- before anyone later runs these statements.
-- Drop the Auth trigger first, then the new tables, then the functions.

drop trigger if exists on_auth_user_created on auth.users;
drop table if exists public.legacy_auth_links;
drop table if exists public.entitlements;
drop table if exists public.profiles;
drop table if exists public.plans;
drop table if exists public.products;
drop function if exists public.handle_new_user();
drop function if exists public.entitlements_reject_plan_product_mismatch();
drop function if exists public.profiles_before_update();
drop function if exists public.entitlements_before_update();
drop function if exists public.legacy_auth_links_before_update();
