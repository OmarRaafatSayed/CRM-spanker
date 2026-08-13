# Customer Portal — مواصفات كاملة
> نظام بوابة العميل (Customer Self-Service Portal) للربط مع الـ CRM

---

## 1. الفكرة العامة

**الهدف:**
- العميل يسجّل حساب في موقع الشركة (Public Website)
- يقدر يتابع حالة طلبات الفيزا بتاعته
- يشوف الحجوزات والفنادق والرحلات اللي حجزها
- يشوف سجل المدفوعات
- **كل البيانات دي مربوطة بالـ CRM** — يعني الموظف في الـ CRM يشوف نفس البيانات

---

## 2. البنية الحالية (CRM)

### قاعدة البيانات — Supabase
```
auth.users (Supabase managed)
    └── profiles (user_id → auth.users.id)
         profiles.id ──┬── visa_applications.created_by
                       ├── hotel_offers.created_by
                       ├── payment_records.created_by
                       └── flight_search_cache.created_by
```

**الجداول:**
- `profiles` — بيانات المستخدمين (موظفين حالياً)
- `visa_applications` — طلبات الفيزا
- `hotel_offers` — عروض الفنادق
- `payment_records` — سجل المدفوعات
- `flight_search_cache` — cache للرحلات

**الـ Backend API:** FastAPI على port 8000
- كل الـ endpoints محمية بـ JWT (Bearer token)
- الـ token بييجي من Supabase Auth

---

## 3. المطلوب في الـ Customer Portal

### الصفحات المطلوبة:


#### أ) صفحة التسجيل / الدخول
- `POST /api/v1/auth/signup` — إنشاء حساب جديد
- `POST /api/v1/auth/login` — تسجيل الدخول
- بعد النجاح → الـ frontend يحفظ الـ `access_token` في localStorage

#### ب) صفحة Dashboard العميل
- ترحيب بالعميل
- نظرة سريعة:
  - عدد طلبات الفيزا
  - آخر حالة للطلب الفعّال
  - إجمالي المدفوعات
  - الحجوزات القادمة

#### ج) صفحة متابعة الفيزا
- عرض **كل طلبات الفيزا الخاصة بالعميل**
- فلترة حسب الحالة (Documents Collected, In Review, Embassy Appointment, etc.)
- عرض Timeline للحالة (stepper)
- تفاصيل كل طلب:
  - رقم جواز السفر
  - الدولة المقصودة
  - الحالة الحالية
  - موعد السفارة (إن وُجد)
  - ملاحظات

#### د) صفحة الحجوزات (اختياري — المرحلة الثانية)
- عرض حجوزات الفنادق
- عرض حجوزات الطيران

#### هـ) صفحة المدفوعات (Read-Only)
- **العميل يشوف فقط** — لا يستطيع إضافة أو تعديل
- **الموظف** هو اللي بيدخل المدفوعات من الـ CRM (يدوياً)
- سجل كل المدفوعات الخاصة بالعميل
- الحالة: pending, partial, full, refunded
- إمكانية طباعة الفاتورة
- **ملاحظة:** المعاملات في هذه المرحلة cash/offline — مش دفع إلكتروني

---

## 4. التعديلات المطلوبة على الـ Backend (CRM)

### أ) إضافة حقل `client_user_id` في الجداول

**المشكلة الحالية:**
- الـ `visa_applications.created_by` بيشير للـ **موظف** اللي أدخل الطلب، مش العميل
- محتاجين نفرّق بين:
  - `created_by` → الموظف اللي أدخل البيانات في الـ CRM
  - `client_user_id` → العميل اللي الطلب خاص بيه

**التعديل:**
```sql
-- Add client_user_id to visa_applications
ALTER TABLE public.visa_applications 
ADD COLUMN IF NOT EXISTS client_user_id UUID REFERENCES public.profiles(user_id);

CREATE INDEX IF NOT EXISTS idx_visa_client_user ON public.visa_applications(client_user_id);

-- Add client_user_id to payment_records
ALTER TABLE public.payment_records
ADD COLUMN IF NOT EXISTS client_user_id UUID REFERENCES public.profiles(user_id);

CREATE INDEX IF NOT EXISTS idx_payment_client_user ON public.payment_records(client_user_id);
```

### ب) إضافة endpoint للعميل يشوف طلبات الفيزا بتاعته

في `app/routers/visa.py` نضيف:

```python
@router.get("/my-applications")
async def get_my_visa_applications(
    token: AuthToken = Depends(require_auth),
    supabase: Client = Depends(get_supabase),
) -> Dict[str, Any]:
    """
    Get all visa applications for the authenticated customer.
    """
    result = supabase.table("visa_applications") \
        .select("*") \
        .eq("client_user_id", token.user_id) \
        .order("created_at", desc=True) \
        .execute()
    
    return {
        "results": result.data,
        "count": len(result.data),
    }
```

### ج) إضافة endpoint للعميل يشوف المدفوعات بتاعته

في `app/routers/payments.py` نضيف:

```python
@router.get("/my-payments")
async def get_my_payments(
    token: AuthToken = Depends(require_auth),
    supabase: Client = Depends(get_supabase),
) -> Dict[str, Any]:
    """
    Get all payment records for the authenticated customer.
    """
    result = supabase.table("payment_records") \
        .select("*") \
        .eq("client_user_id", token.user_id) \
        .order("created_at", desc=True) \
        .execute()
    
    return {
        "results": result.data,
        "count": len(result.data),
        "total_amount": sum(p["amount"] for p in result.data),
    }
```

### د) تعديل الـ signup endpoint عشان يفرّق بين موظف و عميل

في `app/routers/auth.py`:

```python
class SignUpRequest(BaseModel):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""
    role: str = "customer"  # ← جديد: customer أو staff
```

وفي الـ signup handler:
```python
profile_data = {
    "user_id":    user_id,
    "email":      request.email,
    "first_name": request.first_name,
    "last_name":  request.last_name,
    "role":       request.role,  # ← customer vs staff
    ...
}
```

---

## 5. تعديلات الـ CRM (الموظفين)

### أ) في صفحة إضافة طلب فيزا جديد

الموظف لازم يختار:
- **العميل** — dropdown من كل الـ customers المسجلين
- أو **يدوي** — يدخل البيانات بدون ربط بـ user

### ب) في صفحة تسجيل المدفوعات

الموظف لازم يختار:
- **العميل** — dropdown لربط الدفعة بعميل مسجل
- أو **يدوي** — يدخل الاسم بدون ربط بـ user

**ملاحظة:** كل المدفوعات يدوية (cash/bank/POS/cheque) — مفيش دفع إلكتروني من الموقع



**مثال:**
```typescript
// في VisaManagement-simple.tsx
<Select>
  <option value="">-- Manual Entry --</option>
  {customers.map(c => (
    <option key={c.user_id} value={c.user_id}>
      {c.first_name} {c.last_name} ({c.email})
    </option>
  ))}
</Select>
```

عند الحفظ:
```typescript
const payload = {
  client_name: formData.client_name,
  passport_number: formData.passport_number,
  destination_country: formData.destination_country,
  client_user_id: selectedCustomerUserId || null,  // ← nullable
  ...
}
```

---

## 6. الـ Customer Portal — Frontend Stack

### التكنولوجيا الموصى بها:

**Option A — Next.js 14 (App Router) + TypeScript**
- SSR/SSG للصفحات العامة (الصفحة الرئيسية، عن الشركة)
- Client-side rendering للصفحات المحمية (Dashboard، متابعة الفيزا)
- Tailwind CSS للتصميم
- shadcn/ui للـ components
- React Query للـ data fetching
- Zustand أو Jotai للـ state management

**Option B — React + Vite (زي الـ CRM الحالي)**
- أسرع في التطوير
- نفس الـ stack الموجود
- لكن بدون SSR

### الـ Authentication Flow:

```
1. العميل يفتح الموقع → صفحة Login/Signup
2. POST /api/v1/auth/signup { email, password, first_name, last_name, role: "customer" }
3. Backend يعمل:
   - supabase.auth.sign_up()
   - INSERT INTO profiles { ..., role: "customer" }
   - يرجع { session: { access_token, refresh_token }, user: { id, email } }
4. Frontend يحفظ في localStorage:
   key: 'customer_portal_session'
   value: { session, user }
5. كل request للـ API يرسل: Authorization: Bearer <access_token>
```

### الصفحات المطلوبة:

```
/                    → الصفحة الرئيسية (Landing Page)
/about               → عن الشركة
/services            → خدماتنا
/contact             → تواصل معنا

/login               → تسجيل الدخول
/signup              → إنشاء حساب

/dashboard           → لوحة التحكم (محمية)
/dashboard/visa      → متابعة الفيزا (محمية)
/dashboard/payments  → المدفوعات (محمية)
/dashboard/bookings  → الحجوزات (اختياري)
/dashboard/profile   → الملف الشخصي
```

---

## 7. الـ API Endpoints المطلوبة

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/signup` | ❌ | إنشاء حساب (customer) |
| POST | `/api/v1/auth/login` | ❌ | تسجيل الدخول |
| GET | `/api/v1/visa/my-applications` | 🔒 | جلب طلبات الفيزا للعميل |
| GET | `/api/v1/visa/my-applications/{id}` | 🔒 | تفاصيل طلب واحد |
| GET | `/api/v1/payments/my-payments` | 🔒 | جلب المدفوعات للعميل |
| GET | `/api/v1/payments/my-payments/{id}` | 🔒 | تفاصيل دفعة واحدة |
| GET | `/api/v1/customers` | 🔒 | قائمة العملاء (للموظفين فقط) |
| GET | `/api/v1/profile` | 🔒 | بيانات الملف الشخصي |
| PATCH | `/api/v1/profile` | 🔒 | تحديث البيانات الشخصية |

---

## 8. الـ Migration SQL المطلوبة

```sql
-- ===================================================================
-- Customer Portal Schema Updates
-- ===================================================================

-- 1. Add client_user_id to visa_applications
ALTER TABLE public.visa_applications 
ADD COLUMN IF NOT EXISTS client_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_visa_client_user ON public.visa_applications(client_user_id);

COMMENT ON COLUMN public.visa_applications.client_user_id IS 
'The customer who owns this visa application (null = manual entry by staff)';

-- 2. Add client_user_id to payment_records
ALTER TABLE public.payment_records
ADD COLUMN IF NOT EXISTS client_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_payment_client_user ON public.payment_records(client_user_id);

COMMENT ON COLUMN public.payment_records.client_user_id IS 
'The customer who owns this payment record';

-- 3. Add is_customer flag to profiles (optional — can use role field)
-- The 'role' field already exists. We can use:
--   role = 'customer' → public portal users
--   role = 'staff' or 'admin' → CRM users

-- 4. RLS policy for customers to read their own visa applications
DROP POLICY IF EXISTS "customers_read_own_visa" ON public.visa_applications;
CREATE POLICY "customers_read_own_visa" 
ON public.visa_applications 
FOR SELECT 
TO authenticated 
USING (client_user_id = auth.uid());

-- 5. RLS policy for customers to read their own payments
DROP POLICY IF EXISTS "customers_read_own_payments" ON public.payment_records;
CREATE POLICY "customers_read_own_payments" 
ON public.payment_records 
FOR SELECT 
TO authenticated 
USING (client_user_id = auth.uid());

-- ===================================================================
-- DONE ✅
-- ===================================================================
```

---

## 9. الأدوات والتقنيات الحديثة

### Frontend:
- **Next.js 14** (App Router) — SSR/SSG + React Server Components
- **TypeScript** — type safety
- **Tailwind CSS** — utility-first CSS
- **shadcn/ui** — accessible components (Radix UI)
- **Framer Motion** — animations
- **React Query (TanStack Query)** — data fetching + caching
- **Zustand** — state management (أخف من Redux)
- **Zod** — schema validation
- **React Hook Form** — form management
- **Recharts** — charts للـ dashboard

### Backend (موجود بالفعل):
- **FastAPI** — Python async framework
- **Supabase** — PostgreSQL + Auth + Storage
- **JWT** — authentication
- **Pydantic** — data validation

### DevOps:
- **Vercel** — deploy للـ Next.js (free tier ممتاز)
- **Railway / Render** — deploy للـ FastAPI backend
- **Supabase Cloud** — PostgreSQL hosted
- **GitHub Actions** — CI/CD

---

## 10. المطلوب منك (كمطوّر الـ CRM)

### ✅ المطلوب:

1. **تشغيل الـ SQL Migration** — أضف الـ `client_user_id` columns في Supabase
2. **تحديث الـ `/api/v1/auth/signup`** — يقبل `role: "customer"` أو `"staff"`
3. **إضافة الـ endpoints الجديدة:**
   - `GET /api/v1/visa/my-applications`
   - `GET /api/v1/payments/my-payments`
   - `GET /api/v1/customers` (للموظفين — يجيب قائمة العملاء)
4. **تحديث الـ CRM UI** — في صفحة إضافة طلب فيزا:
   - أضف dropdown لاختيار العميل
   - أرسل `client_user_id` مع الطلب

### ❌ مش مطلوب منك:
- **بناء الموقع** — ده هيعمله agent تاني

---

## 11. الـ Prompt للـ Agent (الموقع)

إليك الـ prompt الكامل اللي تبعته للـ agent اللي هيبني الموقع.

يتبع في الصفحة التالية...


---

# الـ Prompt الكامل للـ Agent (نسخ ولصق)

```
Build a modern, production-ready Customer Self-Service Portal for a travel agency using Next.js 14 (App Router), TypeScript, Tailwind CSS, and shadcn/ui.

## Project Overview
Create a public-facing website where customers can:
1. Sign up for an account
2. Track their visa application status in real-time
3. View payment history
4. See booking details (future feature)
5. Update their profile

This portal connects to an existing FastAPI backend and Supabase database shared with the company's internal CRM system.

## Tech Stack (Required)
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript (strict mode)
- **Styling:** Tailwind CSS
- **UI Components:** shadcn/ui (Radix UI primitives)
- **Data Fetching:** TanStack Query (React Query)
- **State Management:** Zustand
- **Forms:** React Hook Form + Zod
- **Animations:** Framer Motion
- **Icons:** Lucide React
- **i18n:** next-intl (Arabic + English, RTL support)

## Backend API Details
- **Base URL:** `http://localhost:8000/api/v1` (configurable via env var)
- **Authentication:** JWT Bearer token (Supabase Auth)
- **Available Endpoints:**
  - `POST /auth/signup` → { email, password, first_name, last_name, role: "customer" }
  - `POST /auth/login` → { email, password }
  - `GET /visa/my-applications` → returns customer's visa applications
  - `GET /visa/my-applications/{id}` → single visa application details
  - `GET /payments/my-payments` → returns customer's payment records
  - `GET /profile` → returns authenticated user profile
  - `PATCH /profile` → update user profile

## Required Pages

### Public Pages (No Auth Required)
1. **`/` (Home)** — Landing page with hero section, services overview, CTA buttons
2. **`/about`** — About the company
3. **`/services`** — Services offered (visa, flights, hotels)
4. **`/contact`** — Contact form + map
5. **`/login`** — Login form
6. **`/signup`** — Registration form

### Protected Pages (Require Auth)
7. **`/dashboard`** — Customer dashboard with:
   - Welcome message
   - Quick stats (total visa applications, pending payments, etc.)
   - Recent activity
8. **`/dashboard/visa`** — Visa application tracking:
   - List of all customer's visa applications
   - Filter by status
   - Visual timeline/stepper showing current stage:
     - 1 = Documents Collected
     - 2 = In Review
     - 3 = Embassy Appointment
     - 4 = Submitted to Consulate
     - 5 = Approved
     - 6 = Rejected
     - 7 = Cancelled
   - Show appointment date if scheduled
9. **`/dashboard/payments`** — Payment history:
   - Table of all payments
   - Status badges (pending, partial, full, refunded, cancelled)
   - Download invoice button (future)
10. **`/dashboard/profile`** — User profile management:
    - Edit first name, last name, email
    - Change password (via Supabase)

## Authentication Flow
1. User signs up → `POST /auth/signup` with `role: "customer"`
2. Backend creates Supabase auth user + profile row
3. Backend returns `{ success, user: { id, email }, session: { access_token, refresh_token } }`
4. Frontend stores session in localStorage key: `customer_portal_session`
5. All protected API calls include: `Authorization: Bearer <access_token>`
6. Token expires after 1 hour → user must re-login

## Design Requirements
- **Modern, clean, professional** design
- **Fully responsive** (mobile-first)
- **RTL support** for Arabic
- **Dark mode** toggle (optional but nice to have)
- **Smooth animations** (page transitions, loading states)
- **Accessible** (WCAG AA compliant)
- **Loading skeletons** for data fetching
- **Empty states** with helpful messages
- **Error boundaries** for graceful error handling

## Key Features
### Visa Tracking Page
- Show visual progress stepper (1-7 steps)
- Highlight current step
- Show "Appointment Date" prominently if scheduled
- Filter by status dropdown
- Search by passport number or destination country

### Payments Page (Read-Only for Customers)
- **Important:** Customers can only VIEW payments. They cannot add or edit.
- All payments are entered by staff in the CRM (manual/offline transactions)
- Summary cards (total paid, pending, refunded)
- Table with columns: Date, Booking Ref, Amount, Method, Status
- Payment methods: Cash, Bank Transfer, Offline POS, Cheque (NO online payment in this phase)
- Status badge colors:
  - pending → yellow
  - partial → blue
  - full → green
  - refunded → gray
  - cancelled → red
- Download invoice button (PDF generation - future feature)

### Dashboard Home
- 4 stat cards (visa count, payment count, upcoming appointments, total spent)
- Recent activity timeline
- Quick action buttons (Apply for Visa, View Payments, Contact Support)

## Environment Variables (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://dnzvcvlebltbfcbcslkt.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRuenZjdmxlYmx0YmZjYmNzbGt0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODUxNDM2MjIsImV4cCI6MjEwMDcxOTYyMn0.7OSdoLhbYKRilnVYEa7H1jK2BhUjJjE5k43NL4ey73A
```

## File Structure
```
customer-portal/
├── app/
│   ├── (public)/
│   │   ├── page.tsx              # Home
│   │   ├── about/page.tsx
│   │   ├── services/page.tsx
│   │   ├── contact/page.tsx
│   │   ├── login/page.tsx
│   │   └── signup/page.tsx
│   ├── dashboard/
│   │   ├── layout.tsx            # Protected layout with sidebar
│   │   ├── page.tsx              # Dashboard home
│   │   ├── visa/page.tsx
│   │   ├── payments/page.tsx
│   │   └── profile/page.tsx
│   ├── layout.tsx                # Root layout
│   └── globals.css
├── components/
│   ├── ui/                       # shadcn/ui components
│   ├── auth/
│   │   ├── LoginForm.tsx
│   │   └── SignupForm.tsx
│   ├── dashboard/
│   │   ├── Sidebar.tsx
│   │   ├── StatCard.tsx
│   │   ├── VisaTimeline.tsx
│   │   └── PaymentTable.tsx
│   ├── layout/
│   │   ├── Header.tsx
│   │   ├── Footer.tsx
│   │   └── LangToggle.tsx
│   └── ...
├── lib/
│   ├── api.ts                    # API client (fetch wrapper)
│   ├── auth.ts                   # Auth helpers (login, signup, logout)
│   ├── utils.ts                  # Utility functions
│   └── types.ts                  # TypeScript types
├── hooks/
│   ├── useAuth.tsx               # Auth context + hook
│   └── useVisaApplications.tsx   # React Query hooks
├── stores/
│   └── authStore.ts              # Zustand store for auth state
├── public/
│   └── ...
├── .env.local
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## Implementation Steps
1. **Initialize Next.js project** with TypeScript + Tailwind
2. **Install dependencies**:
   ```bash
   npx shadcn-ui@latest init
   npm install @tanstack/react-query zustand react-hook-form zod framer-motion lucide-react next-intl
   ```
3. **Set up API client** in `lib/api.ts`:
   - Create fetch wrapper that attaches Bearer token
   - Handle 401 errors (redirect to login)
   - Handle network errors gracefully
4. **Build auth context** (`hooks/useAuth.tsx`):
   - Manage session state (logged in / out)
   - Persist session in localStorage
   - Auto-refresh token before expiry (optional)
5. **Create all pages** listed above
6. **Implement protected route wrapper** (check auth before rendering dashboard pages)
7. **Build reusable components** (Sidebar, StatCard, VisaTimeline, etc.)
8. **Add i18n** with next-intl (AR/EN)
9. **Test thoroughly**:
   - Signup flow
   - Login flow
   - Visa tracking (empty state + with data)
   - Payment history
   - Logout
10. **Deploy to Vercel** (optional)

## Notes
- Use `'use client'` directive for interactive components
- Use React Server Components where possible for better performance
- Add loading.tsx and error.tsx files for proper UX
- Use Next.js Image component for optimized images
- Add proper meta tags for SEO
- Ensure all forms have validation (client + server)
- Show success/error toast messages using sonner or react-hot-toast

## Success Criteria
- ✅ Customer can sign up and log in
- ✅ Customer sees their own visa applications (not others')
- ✅ Visa status is displayed with a visual timeline
- ✅ Payment history is shown correctly (read-only — no payment form)
- ✅ Customer understands payments are entered by staff (show helper text)
- ✅ Arabic and English languages work perfectly with RTL
- ✅ All pages are responsive (mobile, tablet, desktop)
- ✅ Loading states and error handling work smoothly
- ✅ No TypeScript errors
- ✅ Clean, maintainable code

## Important Notes
⚠️ **No online payment gateway in this phase** — all payments are offline (cash/bank/POS/cheque) and entered manually by staff in the CRM. The customer portal only displays payment history for transparency.

Build this step by step, starting with the Next.js setup and API client, then the auth flow, then the protected pages. Test each feature as you build it.
```

---

## نهاية الملف

الملف ده فيه كل التفاصيل. انسخه وابعته للـ agent اللي هيبني الموقع.
