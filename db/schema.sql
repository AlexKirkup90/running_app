create table if not exists athletes (
  id serial primary key,
  first_name varchar(80) not null,
  last_name varchar(80) not null,
  email varchar(200) unique not null,
  dob date,
  status varchar(16) not null default 'active',
  created_at timestamp not null default now()
);

create table if not exists users (
  id serial primary key,
  username varchar(120) unique not null,
  password_hash varchar(255) not null,
  role varchar(20) not null check (role in ('coach','client')),
  athlete_id integer references athletes(id),
  must_change_password boolean not null default true,
  failed_attempts integer not null default 0,
  locked_until timestamp,
  last_login_at timestamp
);

create table if not exists sessions_library (
  id serial primary key,
  name varchar(180) not null,
  category varchar(60) not null,
  tier varchar(20) not null default 'system',
  indoor_ok boolean not null default true,
  duration_min integer not null check (duration_min >= 0),
  blocks_json jsonb not null,
  prescription text not null
);

create table if not exists plans (
  id serial primary key,
  athlete_id integer not null references athletes(id),
  goal_race varchar(20) not null,
  weeks integer not null,
  sessions_per_week integer not null,
  max_session_duration integer not null,
  start_date date not null,
  created_at timestamp not null default now()
);

create table if not exists plan_weeks (
  id serial primary key,
  plan_id integer not null references plans(id),
  week_index integer not null,
  week_start date not null,
  phase varchar(30) not null,
  focus varchar(120) not null,
  target_load float not null check (target_load >= 0),
  sessions_order jsonb not null,
  is_locked boolean not null default false
);

create table if not exists plan_week_metrics (
  id serial primary key,
  plan_week_id integer not null references plan_weeks(id),
  planned_duration integer not null default 0 check (planned_duration >= 0),
  actual_duration integer not null default 0 check (actual_duration >= 0),
  planned_load float not null default 0 check (planned_load >= 0),
  actual_load float not null default 0 check (actual_load >= 0)
);

create table if not exists events (
  id serial primary key,
  athlete_id integer not null references athletes(id),
  event_date date not null,
  race_type varchar(20) not null,
  name varchar(120) not null
);

create table if not exists checkins (
  id serial primary key,
  athlete_id integer not null references athletes(id),
  checkin_date date not null,
  sleep_score integer not null check (sleep_score between 1 and 5),
  energy_score integer not null check (energy_score between 1 and 5),
  recovery_score integer not null check (recovery_score between 1 and 5),
  stress_score integer not null check (stress_score between 1 and 5),
  training_today boolean not null default true,
  unique(athlete_id, checkin_date)
);

create table if not exists training_logs (
  id serial primary key,
  athlete_id integer not null references athletes(id),
  log_date date not null,
  session_type varchar(60) not null,
  duration_min integer not null check (duration_min >= 0),
  distance_km float not null default 0 check (distance_km >= 0),
  load_score float not null default 0 check (load_score >= 0),
  rpe integer not null check (rpe between 1 and 10),
  pain_flag boolean not null default false,
  notes text
);

create table if not exists session_reflections (
  id serial primary key,
  training_log_id integer not null references training_logs(id),
  confidence_score integer not null check (confidence_score between 1 and 10),
  reflection_text text not null default ''
);

create table if not exists coach_action_logs (
  id serial primary key,
  coach_user_id integer not null references users(id),
  athlete_id integer references athletes(id),
  action varchar(120) not null,
  payload jsonb not null,
  created_at timestamp not null default now()
);

create table if not exists coach_notes_tasks (
  id serial primary key,
  athlete_id integer not null references athletes(id),
  note text not null,
  due_date date,
  status varchar(20) not null default 'open'
);

create table if not exists coach_interventions (
  id serial primary key,
  athlete_id integer not null references athletes(id),
  action varchar(40) not null,
  status varchar(20) not null default 'open',
  risk_score float not null,
  confidence_score float not null,
  expected_impact jsonb not null,
  factors jsonb not null,
  guardrail_pass boolean not null default true,
  guardrail_reason varchar(255) not null default '',
  created_at timestamp not null default now()
);
create unique index if not exists uq_intervention_open
on coach_interventions (athlete_id, action)
where status = 'open';

create table if not exists athlete_preferences (
  id serial primary key,
  athlete_id integer not null unique references athletes(id),
  reminder_enabled boolean not null default true,
  reminder_training_days jsonb not null default '["Mon","Tue","Thu","Sat"]',
  privacy_ack boolean not null default false,
  automation_mode varchar(20) not null check (automation_mode in ('manual','assisted','autopilot')),
  auto_apply_low_risk boolean not null default false,
  auto_apply_confidence_min float not null default 0.75,
  auto_apply_risk_max float not null default 0.25
);

create table if not exists app_write_logs (
  id serial primary key,
  log_type varchar(40) not null,
  payload jsonb not null,
  created_at timestamp not null default now()
);

create table if not exists app_runtime_errors (
  id serial primary key,
  page varchar(80) not null,
  message text not null,
  traceback text not null,
  created_at timestamp not null default now()
);

create table if not exists import_runs (
  id serial primary key,
  athlete_id integer references athletes(id),
  adapter_name varchar(80) not null,
  status varchar(20) not null default 'pending',
  created_at timestamp not null default now()
);

create table if not exists import_items (
  id serial primary key,
  import_run_id integer not null references import_runs(id),
  row_number integer not null,
  raw_payload jsonb not null,
  status varchar(20) not null default 'valid',
  message varchar(255) not null default ''
);

create index if not exists idx_athletes_status on athletes(status);
create index if not exists idx_plans_athlete on plans(athlete_id);
create index if not exists idx_plan_weeks_plan on plan_weeks(plan_id, week_index);
create index if not exists idx_checkins_athlete_date on checkins(athlete_id, checkin_date);
create index if not exists idx_training_logs_athlete_date on training_logs(athlete_id, log_date);
