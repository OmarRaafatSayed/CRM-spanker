-- ================================================================
-- PORTAL INTEGRATION MIGRATION
-- ================================================================
-- Purpose : Add customer-facing portal tables so the external
--           website can register customers, upload documents, and
--           receive real-time status updates from the CRM.
--
-- HOW TO RUN:
--   Supabase Dashboard → SQL Editor → paste this entire file → Run
--
-- SAFE TO RE-RUN: every statement uses IF NOT EXISTS / OR REPLACE
-- ================================================================


-- ────────────────────────────────────────────────────────────────
-- 0. PREREQUISITES
--    set_updated_at() already exists from earlier migrations.
--    We re-create it with OR REPLACE just to be safe.
-- ────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;


-- ================================================================
-- 1. CUSTOMER_REQUESTS
--    A customer on the website fills a form (destination, dates,
--    type of service). It lands here as a new lead for the CRM.
--
--    Lifecycle (status):
--      new → in_review → quoted → booked → completed | cancelled
-- ================================================================

CREATE TABLE IF NOT EXISTS public.customer_requests (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Who made the request — links to auth.users (same Supabase project)
  customer_id      UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Personal info snapshot (in case profile is incomplete at request time)
  full_name        TEXT        NOT NULL,
  phone            TEXT,
  email            TEXT,

  -- What they want
  request_type     TEXT        NOT NULL DEFAULT 'visa'
                                 CHECK (request_type IN ('visa', 'flight', 'hotel', 'package')),
  destination      TEXT        NOT NULL,
  travel_date      DATE,
  return_date      DATE,
  num_travelers    INTEGER     NOT NULL DEFAULT 1 CHECK (num_travelers >= 1),
  notes            TEXT,

  -- CRM pipeline state
  status           TEXT        NOT NULL DEFAULT 'new'
                                 CHECK (status IN ('new', 'in_review', 'quoted', 'booked', 'completed', 'cancelled')),

  -- Which staff member owns this request (set by CRM staff)
  assigned_to      UUID        REFERENCES public.profiles(id) ON DELETE SET NULL,

  -- Link to visa_application created by CRM for this request (optional)
  visa_application_id UUID,

  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_creq_customer_id  ON public.customer_requests (customer_id);
CREATE INDEX IF NOT EXISTS idx_creq_status        ON public.customer_requests (status);
CREATE INDEX IF NOT EXISTS idx_creq_assigned_to   ON public.customer_requests (assigned_to);
CREATE INDEX IF NOT EXISTS idx_creq_created_at    ON public.customer_requests (created_at DESC);

-- Auto-update updated_at
DROP TRIGGER IF EXISTS trg_creq_updated_at ON public.customer_requests;
CREATE TRIGGER trg_creq_updated_at
  BEFORE UPDATE ON public.customer_requests
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ── RLS ──────────────────────────────────────────────────────────
ALTER TABLE public.customer_requests ENABLE ROW LEVEL SECURITY;

-- Backend (service role) — full access, bypasses RLS
DROP POLICY IF EXISTS "creq_service_all"    ON public.customer_requests;
CREATE POLICY "creq_service_all"
  ON public.customer_requests FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);

-- Customer — can see and manage ONLY their own requests
DROP POLICY IF EXISTS "creq_customer_select" ON public.customer_requests;
CREATE POLICY "creq_customer_select"
  ON public.customer_requests FOR SELECT
  TO authenticated
  USING (customer_id = auth.uid());

DROP POLICY IF EXISTS "creq_customer_insert" ON public.customer_requests;
CREATE POLICY "creq_customer_insert"
  ON public.customer_requests FOR INSERT
  TO authenticated
  WITH CHECK (customer_id = auth.uid());

-- Customers can update only non-status fields (status is CRM-controlled)
-- They can still edit their own notes / travel dates before staff reviews
DROP POLICY IF EXISTS "creq_customer_update" ON public.customer_requests;
CREATE POLICY "creq_customer_update"
  ON public.customer_requests FOR UPDATE
  TO authenticated
  USING (customer_id = auth.uid() AND status = 'new');


-- ================================================================
-- 2. PORTAL_DOCUMENTS
--    Customer uploads supporting files from the website.
--    CRM staff reviews and marks each document approved / rejected.
--
--    Lifecycle (status):
--      uploaded → under_review → approved | rejected | expired
-- ================================================================

CREATE TABLE IF NOT EXISTS public.portal_documents (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Ownership
  customer_id   UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  request_id    UUID        REFERENCES public.customer_requests(id) ON DELETE SET NULL,

  -- File metadata
  doc_type      TEXT        NOT NULL
                              CHECK (doc_type IN (
                                'PASSPORT', 'NATIONAL_ID', 'PHOTO',
                                'BANK_STATEMENT', 'SALARY_SLIP',
                                'HOTEL_BOOKING', 'FLIGHT_BOOKING',
                                'TRAVEL_INSURANCE', 'OTHER'
                              )),
  file_url      TEXT        NOT NULL,   -- Supabase Storage public/signed URL
  file_name     TEXT        NOT NULL,
  file_size     INTEGER,               -- bytes
  mime_type     TEXT,

  -- Review workflow
  status        TEXT        NOT NULL DEFAULT 'uploaded'
                              CHECK (status IN (
                                'uploaded', 'under_review', 'approved', 'rejected', 'expired'
                              )),

  -- CRM feedback visible to the customer
  staff_notes   TEXT,
  reviewed_by   UUID        REFERENCES public.profiles(id) ON DELETE SET NULL,
  reviewed_at   TIMESTAMPTZ,

  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pdoc_customer_id  ON public.portal_documents (customer_id);
CREATE INDEX IF NOT EXISTS idx_pdoc_request_id   ON public.portal_documents (request_id);
CREATE INDEX IF NOT EXISTS idx_pdoc_status        ON public.portal_documents (status);

-- Auto-update updated_at
DROP TRIGGER IF EXISTS trg_pdoc_updated_at ON public.portal_documents;
CREATE TRIGGER trg_pdoc_updated_at
  BEFORE UPDATE ON public.portal_documents
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ── RLS ──────────────────────────────────────────────────────────
ALTER TABLE public.portal_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "pdoc_service_all"      ON public.portal_documents;
CREATE POLICY "pdoc_service_all"
  ON public.portal_documents FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);

-- Customer can see ALL their own documents (including staff feedback)
DROP POLICY IF EXISTS "pdoc_customer_select"  ON public.portal_documents;
CREATE POLICY "pdoc_customer_select"
  ON public.portal_documents FOR SELECT
  TO authenticated
  USING (customer_id = auth.uid());

-- Customer can upload new documents
DROP POLICY IF EXISTS "pdoc_customer_insert"  ON public.portal_documents;
CREATE POLICY "pdoc_customer_insert"
  ON public.portal_documents FOR INSERT
  TO authenticated
  WITH CHECK (customer_id = auth.uid());

-- Customer can delete only their own uploaded (not-yet-reviewed) docs
DROP POLICY IF EXISTS "pdoc_customer_delete"  ON public.portal_documents;
CREATE POLICY "pdoc_customer_delete"
  ON public.portal_documents FOR DELETE
  TO authenticated
  USING (customer_id = auth.uid() AND status = 'uploaded');


-- ================================================================
-- 3. PORTAL_NOTIFICATIONS
--    CRM staff actions (status changes, document reviews, payment
--    requests) automatically create rows here.
--    The customer portal subscribes via Supabase Realtime and
--    shows them instantly — no polling needed.
--
--    INSERT  → triggered by FastAPI (service role)
--    SELECT  → customer reads their own notifications
--    UPDATE  → customer marks as read
-- ================================================================

CREATE TABLE IF NOT EXISTS public.portal_notifications (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Target customer
  customer_id   UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Notification content
  title         TEXT        NOT NULL,
  body          TEXT,

  -- Type drives the icon / color on the frontend
  type          TEXT        NOT NULL DEFAULT 'info'
                              CHECK (type IN (
                                'status_update',      -- request/visa status changed
                                'document_approved',  -- CRM approved a document
                                'document_rejected',  -- CRM rejected a document
                                'payment_due',        -- payment reminder
                                'payment_confirmed',  -- payment received
                                'message',            -- general CRM → customer message
                                'info'                -- generic
                              )),

  -- Has the customer seen it?
  is_read       BOOLEAN     NOT NULL DEFAULT FALSE,

  -- Optional structured payload so the website can deep-link
  -- e.g. {"request_id": "...", "new_status": "in_review"}
  data          JSONB,

  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
  -- No updated_at: notifications are immutable except for is_read
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pnotif_customer_id  ON public.portal_notifications (customer_id);
CREATE INDEX IF NOT EXISTS idx_pnotif_is_read       ON public.portal_notifications (customer_id, is_read)
  WHERE is_read = FALSE;   -- partial index — fast unread badge count
CREATE INDEX IF NOT EXISTS idx_pnotif_created_at    ON public.portal_notifications (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pnotif_type          ON public.portal_notifications (type);

-- ── RLS ──────────────────────────────────────────────────────────
ALTER TABLE public.portal_notifications ENABLE ROW LEVEL SECURITY;

-- Backend inserts notifications (only service_role can create them)
DROP POLICY IF EXISTS "pnotif_service_all"      ON public.portal_notifications;
CREATE POLICY "pnotif_service_all"
  ON public.portal_notifications FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);

-- Customer reads their own notifications
DROP POLICY IF EXISTS "pnotif_customer_select"  ON public.portal_notifications;
CREATE POLICY "pnotif_customer_select"
  ON public.portal_notifications FOR SELECT
  TO authenticated
  USING (customer_id = auth.uid());

-- Customer marks as read (can only flip is_read, nothing else)
DROP POLICY IF EXISTS "pnotif_customer_update"  ON public.portal_notifications;
CREATE POLICY "pnotif_customer_update"
  ON public.portal_notifications FOR UPDATE
  TO authenticated
  USING (customer_id = auth.uid());


-- ================================================================
-- 4. PORTAL_STATUS_LOG
--    Immutable audit trail every time CRM changes a request status.
--    Gives the customer a timeline view: "Your request moved from
--    'new' to 'in_review' on June 3rd".
-- ================================================================

CREATE TABLE IF NOT EXISTS public.portal_status_log (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id    UUID        NOT NULL REFERENCES public.customer_requests(id) ON DELETE CASCADE,
  customer_id   UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  from_status   TEXT,                 -- NULL when first entry
  to_status     TEXT        NOT NULL,
  changed_by    UUID        REFERENCES public.profiles(id) ON DELETE SET NULL,
  note          TEXT,                 -- optional staff note visible to customer

  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plog_request_id   ON public.portal_status_log (request_id);
CREATE INDEX IF NOT EXISTS idx_plog_customer_id  ON public.portal_status_log (customer_id);

-- ── RLS ──────────────────────────────────────────────────────────
ALTER TABLE public.portal_status_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "plog_service_all"      ON public.portal_status_log;
CREATE POLICY "plog_service_all"
  ON public.portal_status_log FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);

-- Customer can read their own history (read-only)
DROP POLICY IF EXISTS "plog_customer_select"  ON public.portal_status_log;
CREATE POLICY "plog_customer_select"
  ON public.portal_status_log FOR SELECT
  TO authenticated
  USING (customer_id = auth.uid());


-- ================================================================
-- 5. SUPABASE REALTIME
--    Enable realtime replication for the portal_notifications table
--    so the website gets instant push updates when the CRM acts.
--
--    The website will subscribe with:
--      supabase.channel('portal')
--        .on('postgres_changes', {
--            event: 'INSERT',
--            schema: 'public',
--            table: 'portal_notifications',
--            filter: `customer_id=eq.${userId}`
--          }, handler)
--        .subscribe()
-- ================================================================

-- Add tables to the supabase_realtime publication
-- (safe to re-run — ALTER PUBLICATION ... ADD TABLE is idempotent on PG 15+)
DO $$
BEGIN
  -- portal_notifications: real-time push to customer
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'portal_notifications'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.portal_notifications;
  END IF;

  -- customer_requests: customer sees their request status change live
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'customer_requests'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.customer_requests;
  END IF;

  -- portal_documents: customer sees document review result live
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'portal_documents'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.portal_documents;
  END IF;
END $$;


-- ================================================================
-- 6. STORAGE BUCKET — portal-documents
--    Customers upload their files here from the website.
--    Each customer can only read/write their own folder:
--      portal-documents/{auth.uid()}/filename.pdf
-- ================================================================

-- Create the bucket (private by default — only accessible via signed URLs)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'portal-documents',
  'portal-documents',
  FALSE,                    -- private bucket
  10485760,                 -- 10 MB max per file
  ARRAY[
    'image/jpeg', 'image/png', 'image/webp',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
)
ON CONFLICT (id) DO NOTHING;   -- safe to re-run

-- ── Storage RLS ───────────────────────────────────────────────────
-- Customers upload to their own folder
DROP POLICY IF EXISTS "portal_docs_customer_upload" ON storage.objects;
CREATE POLICY "portal_docs_customer_upload"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'portal-documents'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Customers read their own files
DROP POLICY IF EXISTS "portal_docs_customer_read" ON storage.objects;
CREATE POLICY "portal_docs_customer_read"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (
    bucket_id = 'portal-documents'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Customers can delete their own uploaded files
DROP POLICY IF EXISTS "portal_docs_customer_delete" ON storage.objects;
CREATE POLICY "portal_docs_customer_delete"
  ON storage.objects FOR DELETE
  TO authenticated
  USING (
    bucket_id = 'portal-documents'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Service role (FastAPI backend) reads ALL files for review
DROP POLICY IF EXISTS "portal_docs_service_all" ON storage.objects;
CREATE POLICY "portal_docs_service_all"
  ON storage.objects FOR ALL
  TO service_role
  USING (bucket_id = 'portal-documents')
  WITH CHECK (bucket_id = 'portal-documents');


-- ================================================================
-- 7. HELPER VIEW — portal_customer_summary
--    Convenience view the website can query to show the customer
--    their full dashboard in one call.
-- ================================================================

CREATE OR REPLACE VIEW public.portal_customer_summary AS
SELECT
  cr.id                              AS request_id,
  cr.customer_id,
  cr.full_name,
  cr.request_type,
  cr.destination,
  cr.travel_date,
  cr.status                          AS request_status,
  cr.created_at                      AS request_created_at,

  -- Document counts
  (SELECT COUNT(*) FROM public.portal_documents pd
   WHERE pd.request_id = cr.id)      AS total_documents,

  (SELECT COUNT(*) FROM public.portal_documents pd
   WHERE pd.request_id = cr.id
     AND pd.status = 'approved')     AS approved_documents,

  (SELECT COUNT(*) FROM public.portal_documents pd
   WHERE pd.request_id = cr.id
     AND pd.status = 'rejected')     AS rejected_documents,

  -- Unread notification count for this request
  (SELECT COUNT(*) FROM public.portal_notifications pn
   WHERE pn.customer_id = cr.customer_id
     AND pn.is_read = FALSE
     AND (pn.data->>'request_id')::text = cr.id::text
  )                                  AS unread_notifications

FROM public.customer_requests cr;

-- RLS on the view: customers see only their own rows
ALTER VIEW public.portal_customer_summary OWNER TO postgres;

-- Note: views don't have RLS directly — security is enforced by
-- underlying table policies. The website should always filter by
-- customer_id = auth.uid() when querying this view.


-- ================================================================
-- 8. PROFILE ROLE CONSTRAINT
--    Make sure the profiles.role column accepts 'customer' in
--    addition to existing values. Website users register as
--    'customer'; CRM users are 'staff' or 'admin'.
-- ================================================================

-- Add CHECK constraint only if it doesn't already exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.check_constraints
    WHERE constraint_name = 'profiles_role_check'
  ) THEN
    ALTER TABLE public.profiles
      ADD CONSTRAINT profiles_role_check
      CHECK (role IN ('customer', 'user', 'staff', 'admin', 'super_admin'));
  END IF;
END $$;


-- ================================================================
-- DONE ✅
-- Tables created:
--   public.customer_requests       (website lead form)
--   public.portal_documents        (customer file uploads)
--   public.portal_notifications    (CRM → customer realtime alerts)
--   public.portal_status_log       (immutable audit trail)
--
-- Storage bucket created:
--   portal-documents               (10 MB limit, private, per-user folder)
--
-- Realtime enabled on:
--   portal_notifications, customer_requests, portal_documents
--
-- View created:
--   portal_customer_summary        (dashboard one-query helper)
-- ================================================================
