-- Prepared 2026-11-04. NOT APPLIED.
-- Identity catalog for the first Supabase Auth iteration.
-- Does not alter public.users, public.stripe_events, roles, or Auth settings.
-- Does not create payment tables, legacy links, or audit tables.
-- Does not copy credentials or any Auth field except the user id.
-- Universe size stays in universes.py: free 30, nordic 79, international 159.
-- Those counts are not columns here.
--
-- Service access, documented and not implemented:
-- A later webhook may use the Supabase service role. That role bypasses RLS.
-- This migration does not grant that role and does not place it in Streamlit.
-- The postgres role is not altered. It already bypasses RLS, so RLS is not
-- the security boundary for the current database URI.
-- Authenticated clients read through auth.uid(). They cannot write entitlements.
--
-- Apply later only on a non-production database. Do not run against Cloud.

create table public.products (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  constraint products_code_format check (code ~ '^[a-z0-9]+(-[a-z0-9]+)*$')
);

create table public.plans (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products (id) on delete restrict,
  code text not null,
  name text not null,
  rank integer not null,
  billing_type text not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  constraint plans_product_code unique (product_id, code),
  constraint plans_code_format check (code ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  constraint plans_rank_nonnegative check (rank >= 0),
  constraint plans_billing_type check (billing_type in ('free', 'recurring', 'one_time'))
);

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_display_name_length check (
    display_name is null or char_length(display_name) between 1 and 80
  )
);

create table public.entitlements (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  product_id uuid not null references public.products (id) on delete restrict,
  plan_id uuid not null references public.plans (id) on delete restrict,
  status text not null,
  source text not null,
  starts_at timestamptz not null default now(),
  ends_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint entitlements_status check (
    status in ('active', 'expired', 'revoked', 'suspended')
  ),
  constraint entitlements_source check (
    source in ('signup', 'migration', 'manual', 'subscription', 'purchase')
  ),
  constraint entitlements_window check (ends_at is null or ends_at > starts_at)
);

create unique index entitlements_one_active_per_product
  on public.entitlements (user_id, product_id)
  where status = 'active';

create index entitlements_user_product_idx
  on public.entitlements (user_id, product_id);

create or replace function public.entitlements_reject_plan_product_mismatch()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (
    select 1
    from public.plans
    where id = new.plan_id
      and product_id = new.product_id
  ) then
    raise exception 'entitlement plan does not belong to product'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger entitlements_plan_matches_product
  before insert or update of plan_id, product_id
  on public.entitlements
  for each row
  execute function public.entitlements_reject_plan_product_mismatch();

create or replace function public.profiles_before_update()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  if new.id is distinct from old.id then
    raise exception 'profile id is immutable'
      using errcode = '42501';
  end if;
  if new.created_at is distinct from old.created_at then
    raise exception 'profile created_at is immutable'
      using errcode = '42501';
  end if;
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_before_update
  before update on public.profiles
  for each row
  execute function public.profiles_before_update();

create or replace function public.entitlements_before_update()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger entitlements_before_update
  before update on public.entitlements
  for each row
  execute function public.entitlements_before_update();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

revoke all on function public.entitlements_reject_plan_product_mismatch() from public, anon, authenticated;
revoke all on function public.profiles_before_update() from public, anon, authenticated;
revoke all on function public.entitlements_before_update() from public, anon, authenticated;
revoke all on function public.handle_new_user() from public, anon, authenticated;

alter table public.products enable row level security;
alter table public.plans enable row level security;
alter table public.profiles enable row level security;
alter table public.entitlements enable row level security;

alter table public.products force row level security;
alter table public.plans force row level security;
alter table public.profiles force row level security;
alter table public.entitlements force row level security;

revoke all on table public.products from public, anon, authenticated;
revoke all on table public.plans from public, anon, authenticated;
revoke all on table public.profiles from public, anon, authenticated;
revoke all on table public.entitlements from public, anon, authenticated;

grant select on table public.products to authenticated;
grant select on table public.plans to authenticated;
grant select on table public.profiles to authenticated;
grant update (display_name) on table public.profiles to authenticated;
grant select on table public.entitlements to authenticated;

create policy products_select_active on public.products
  for select to authenticated
  using (active);

create policy plans_select_active on public.plans
  for select to authenticated
  using (active);

create policy profiles_select_own on public.profiles
  for select to authenticated
  using (id = auth.uid());

create policy profiles_update_own on public.profiles
  for update to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

create policy entitlements_select_own on public.entitlements
  for select to authenticated
  using (user_id = auth.uid());

insert into public.products (code, name) values
  ('traderdash', 'TraderDash');

insert into public.plans (product_id, code, name, rank, billing_type)
select id, 'free', 'Free', 0, 'free' from public.products where code = 'traderdash'
union all
select id, 'nordic', 'Nordic', 1, 'recurring' from public.products where code = 'traderdash'
union all
select id, 'international', 'International', 2, 'recurring' from public.products where code = 'traderdash';
