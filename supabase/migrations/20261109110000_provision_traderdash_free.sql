-- Prepared 2026-11-09. NOT APPLIED to Production.
-- Additive. The function provisions one TraderDash Free entitlement.
-- It does not run for every Market Tools account by itself.
-- anon and authenticated cannot execute it. The service role is not granted here.
-- An existing active entitlement is left unchanged.

create or replace function public.provision_traderdash_free(target uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  product uuid;
  free_plan uuid;
  active_count integer;
  other_count integer;
begin
  if target is null then
    raise exception 'missing user' using errcode = '22023';
  end if;
  select id into product from public.products where code = 'traderdash';
  select id into free_plan from public.plans where product_id = product and code = 'free';
  if product is null or free_plan is null then
    raise exception 'free plan missing' using errcode = '23514';
  end if;

  insert into public.profiles (id) values (target)
  on conflict (id) do nothing;

  select count(*) into other_count
  from public.entitlements as entitlement
  join public.plans as plan on plan.id = entitlement.plan_id
  where entitlement.user_id = target
    and entitlement.product_id = product
    and entitlement.status = 'active'
    and plan.code <> 'free';
  if other_count > 0 then
    raise exception 'unexpected plan' using errcode = '23514';
  end if;

  select count(*) into active_count
  from public.entitlements
  where user_id = target
    and product_id = product
    and status = 'active';
  if active_count > 1 then
    raise exception 'duplicate free' using errcode = '23514';
  end if;
  if active_count = 1 then
    return;
  end if;

  insert into public.entitlements (user_id, product_id, plan_id, status, source)
  values (target, product, free_plan, 'active', 'signup');
end;
$$;

revoke all on function public.provision_traderdash_free(uuid) from public, anon, authenticated;
