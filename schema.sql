-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.tigers (
  id text NOT NULL,
  name text,
  enrolled_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT tigers_pkey PRIMARY KEY (id)
);
CREATE TABLE public.captures (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  tiger_id text NOT NULL,
  image_path text,
  station text,
  timestamp timestamp with time zone DEFAULT timezone('utc'::text, now()),
  latitude double precision,
  longitude double precision,
  status text,
  confidence double precision,
  embedding USER-DEFINED,
  CONSTRAINT captures_pkey PRIMARY KEY (id),
  CONSTRAINT captures_tiger_id_fkey FOREIGN KEY (tiger_id) REFERENCES public.tigers(id)
);
CREATE TABLE public.alerts (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  tiger_id text NOT NULL,
  alert_type text,
  severity text,
  message text,
  timestamp timestamp with time zone DEFAULT timezone('utc'::text, now()),
  resolved boolean DEFAULT false,
  evidence jsonb,
  CONSTRAINT alerts_pkey PRIMARY KEY (id),
  CONSTRAINT alerts_tiger_id_fkey FOREIGN KEY (tiger_id) REFERENCES public.tigers(id)
);