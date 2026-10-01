-- Resume Finder schema. Idempotent: safe to run more than once.
create extension if not exists pgcrypto;

create table if not exists candidates (
  id uuid primary key default gen_random_uuid(),
  role text not null check (role in ('PM','SPM')),
  full_name text, email text, phone text, address text,
  current_company text, current_title text,
  pm_years numeric, total_experience_years numeric,
  location text, relocation text check (relocation in ('willing','unwilling','unknown')),
  summary text, applied_role_hint text, extraction_notes text,
  extraction_method text,            -- 'text' or 'gemini_vision'
  file_name text, file_path text, file_hash text, file_size integer,
  gemini_model text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (role, file_hash)
);
create unique index if not exists candidates_role_email_uniq on candidates (role, lower(email)) where email is not null;
create index if not exists candidates_role_idx on candidates (role);

create table if not exists scores (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid not null references candidates(id) on delete cascade,
  requirement_id text not null,
  score integer not null check (score between 0 and 5),
  evidence text, reason text,
  unique (candidate_id, requirement_id)
);

create table if not exists results (
  candidate_id uuid primary key references candidates(id) on delete cascade,
  weighted_score numeric(5,1) not null,
  recommendation text not null,
  location_gate text,
  probe_questions jsonb default '[]'::jsonb,
  rubric_version text not null,
  updated_at timestamptz not null default now()
);

-- keep updated_at fresh (so a manual edit in Supabase shows up as a change after Refresh)
create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists candidates_set_updated_at on candidates;
create trigger candidates_set_updated_at before update on candidates
  for each row execute function set_updated_at();

drop trigger if exists results_set_updated_at on results;
create trigger results_set_updated_at before update on results
  for each row execute function set_updated_at();

-- RLS on, and NO policies: only the backend's secret key can read or write
alter table candidates enable row level security;
alter table scores enable row level security;
alter table results enable row level security;

-- Private storage bucket for the original resume files
insert into storage.buckets (id, name, public) values ('resumes', 'resumes', false)
on conflict (id) do nothing;
