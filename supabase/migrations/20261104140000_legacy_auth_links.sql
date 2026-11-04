-- Preview pilot link between one legacy public.users row and one Auth user.
-- Apply only to project ref ajbsoudovxstlolojvte. Do not run against Production.
-- Does not alter public.users, Auth users, or the postgres role.
-- Does not copy credentials or tokens.
--
-- Rollback on the same preview database:
--   drop table public.legacy_auth_links;

create table public.legacy_auth_links (
  id uuid primary key default gen_random_uuid(),
  legacy_user_id text not null,
  auth_user_id uuid not null references auth.users (id) on delete cascade,
  migration_status text not null,
  migration_reference text,
  migrated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint legacy_auth_links_status check (migration_status in ('migrated')),
  constraint legacy_auth_links_legacy_id check (char_length(legacy_user_id) between 1 and 80),
  constraint legacy_auth_links_reference_length check (
    migration_reference is null or char_length(migration_reference) between 1 and 120
  )
);

create unique index legacy_auth_links_legacy_user_id_key
  on public.legacy_auth_links (legacy_user_id);

create unique index legacy_auth_links_auth_user_id_key
  on public.legacy_auth_links (auth_user_id);

create or replace function public.legacy_auth_links_before_update()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  if new.legacy_user_id is distinct from old.legacy_user_id
     or new.auth_user_id is distinct from old.auth_user_id then
    raise exception 'migration link identity is immutable'
      using errcode = '42501';
  end if;
  new.updated_at = now();
  return new;
end;
$$;

create trigger legacy_auth_links_before_update
  before update on public.legacy_auth_links
  for each row
  execute function public.legacy_auth_links_before_update();

revoke all on function public.legacy_auth_links_before_update() from public, anon, authenticated;

alter table public.legacy_auth_links enable row level security;
alter table public.legacy_auth_links force row level security;

revoke all on table public.legacy_auth_links from public, anon, authenticated;
