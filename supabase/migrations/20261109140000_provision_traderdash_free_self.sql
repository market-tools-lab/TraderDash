-- Prepared 2026-11-09. NOT APPLIED to Production.
-- TraderDash product enrollment for the signed-in user only.
-- A Market Tools account does not call this by itself.
-- There is no user-id argument. auth.uid() is the only identity.
-- An unconfirmed address is refused. anon cannot execute this function.
-- public.provision_traderdash_free(uuid) is unchanged and stays closed
-- to anon and authenticated.

create or replace function public.provision_traderdash_free_self()
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  actor uuid := auth.uid();
  confirmed_at timestamptz;
  product uuid;
  blocked integer;
begin
  if actor is null then
    raise exception 'authenticated identity required' using errcode = '42501';
  end if;
  select email_confirmed_at into confirmed_at
  from auth.users
  where id = actor;
  if confirmed_at is null then
    raise exception 'email not confirmed' using errcode = '42501';
  end if;

  select id into product from public.products where code = 'traderdash';
  if product is null then
    raise exception 'free plan missing' using errcode = '23514';
  end if;

  select count(*) into blocked
  from public.entitlements as entitlement
  join public.plans as plan on plan.id = entitlement.plan_id
  where entitlement.user_id = actor
    and entitlement.product_id = product
    and entitlement.status = 'active'
    and (
      plan.code <> 'free'
      or entitlement.source in ('subscription', 'purchase')
    );
  if blocked > 0 then
    raise exception 'unexpected plan' using errcode = '23514';
  end if;

  begin
    perform public.provision_traderdash_free(actor);
  exception
    when unique_violation then
      return;
  end;
end;
$$;

revoke all on function public.provision_traderdash_free_self() from public, anon;
grant execute on function public.provision_traderdash_free_self() to authenticated;
