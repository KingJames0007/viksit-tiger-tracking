CREATE TABLE public.tigers (
  id text NOT NULL,
  name text,
  enrolled_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT tigers_pkey PRIMARY KEY (id)
);
CREATE TABLE public.captures (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  tiger_id text,
  image_path text NOT NULL UNIQUE,
  station text NOT NULL,
  timestamp timestamp with time zone NOT NULL,
  latitude double precision NOT NULL,
  longitude double precision NOT NULL,
  status text NOT NULL CHECK (status = ANY (ARRAY['processed'::text, 'quarantined'::text, 'pending_review'::text])),
  confidence double precision NOT NULL,
  CONSTRAINT captures_pkey PRIMARY KEY (id),
  CONSTRAINT captures_tiger_id_fkey FOREIGN KEY (tiger_id) REFERENCES public.tigers(id)
);
CREATE TABLE public.alerts (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  tiger_id text,
  alert_type text NOT NULL,
  severity text NOT NULL CHECK (severity = ANY (ARRAY['CRITICAL'::text, 'WARNING'::text, 'INFO'::text])),
  message text NOT NULL,
  timestamp timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  resolved boolean NOT NULL DEFAULT false,
  evidence jsonb,
  CONSTRAINT alerts_pkey PRIMARY KEY (id),
  CONSTRAINT alerts_tiger_id_fkey FOREIGN KEY (tiger_id) REFERENCES public.tigers(id)
);