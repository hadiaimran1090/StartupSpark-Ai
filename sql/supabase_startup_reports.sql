create extension if not exists pgcrypto;

create table if not exists startup_reports (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    title text not null,
    report jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists startup_reports_user_created_idx
on startup_reports(user_id, created_at desc);

alter table startup_reports enable row level security;

drop policy if exists "Users can read their own reports" on startup_reports;
create policy "Users can read their own reports"
on startup_reports for select
using (auth.uid() = user_id);

drop policy if exists "Users can insert their own reports" on startup_reports;
create policy "Users can insert their own reports"
on startup_reports for insert
with check (auth.uid() = user_id);

drop policy if exists "Users can update their own reports" on startup_reports;
create policy "Users can update their own reports"
on startup_reports for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "Users can delete their own reports" on startup_reports;
create policy "Users can delete their own reports"
on startup_reports for delete
using (auth.uid() = user_id);
