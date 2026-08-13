# Travel Agency CRM — Integration Guide
> كل المعلومات اللي محتاجها تربط موقع تاني بنفس الـ Supabase والـ Backend

---

## 1. المعلومات الأساسية

| Item | Value |
|---|---|
| **Supabase URL** | `https://dnzvcvlebltbfcbcslkt.supabase.co` |
| **Supabase Project ID** | `dnzvcvlebltbfcbcslkt` |
| **Backend Port** | `8000` |
| **Frontend Port** | `4000` |
| **API Base URL** | `http://localhost:8000/api/v1` |

---

## 2. Architecture

```
Browser (React SPA)
    │
    │  VITE_API_URL → http://localhost:8000/api/v1
    │
    ▼
FastAPI Backend (Python, port 8000)
    │  يستخدم SERVICE_ROLE_KEY → يتجاوز RLS
    │  يتحقق من Supabase JWT Bearer (ES256 + HS256 fallback)
    │
    ▼
Supabase  (dnzvcvlebltbfcbcslkt.supabase.co)
    5 جداول في public schema
    RLS مفعّل على كل الجداول
    Auth عبر supabase.auth (GoTrue)
```

**قرار تصميمي مهم:** الـ Frontend لا يستخدم Supabase JS SDK.
يتكلم فقط مع الـ FastAPI backend، اللي بيستخدم service_role key.

---

## 3. Environment Variables

### Backend (`fastapi-backend/fastapi-backend/.env`)

```env
ENVIRONMENT=development

SUPABASE_URL=https://dnzvcvlebltbfcbcslkt.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRuenZjdmxlYmx0YmZjYmNzbGt0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTE0MzYyMiwiZXhwIjoyMTAwNzE5NjIyfQ.qiYMkdbMY9bkVkHySv_IpOAT336KL_zERKFPPfhkJ-o
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRuenZjdmxlYmx0YmZjYmNzbGt0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODUxNDM2MjIsImV4cCI6MjEwMDcxOTYyMn0.7OSdoLhbYKRilnVYEa7H1jK2BhUjJjE5k43NL4ey73A
SUPABASE_JWT_SECRET=2XgGHCS2PFqjhIAkikiiut0AZNW3YHM+B9iwCNHyS1rwfabrIddquwXGh6Engj+j4zR0mRgXSGbSKXVlMLLt4A==

JWT_SECRET_KEY=2XgGHCS2PFqjhIAkikiiut0AZNW3YHM+B9iwCNHyS1rwfabrIddquwXGh6Engj+j4zR0mRgXSGbSKXVlMLLt4A==
JWT_ALGORITHM=HS256

API_HOST=0.0.0.0
API_PORT=8000

# أضف domain موقعك الجديد هنا
CORS_ORIGINS=http://localhost:4000,http://localhost:5173,http://localhost:3000
```

### Frontend (`.env`)
```env
VITE_API_URL=http://localhost:8000/api/v1
```

---

## 4. قاعدة البيانات — الجداول

### جدول: `public.profiles`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | الـ PK الخاص بالـ profile (يُستخدم كـ FK في باقي الجداول) |
| `user_id` | UUID UNIQUE | يربط بـ `auth.users(id)` |
| `email` | TEXT | |
| `first_name` | TEXT | |
| `last_name` | TEXT | |
| `role` | TEXT | default: `user` |
| `organization_id` | UUID | nullable |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**RLS Policies:**
- `service_role` → كامل الصلاحيات
- `authenticated` → SELECT و UPDATE على الـ row الخاصة به فقط

---

### جدول: `public.visa_applications`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `client_name` | TEXT NOT NULL | |
| `passport_number` | TEXT NOT NULL | |
| `destination_country` | TEXT NOT NULL | |
| `status` | INTEGER | CHECK (1–7) |
| `appointment_date` | DATE | nullable |
| `appointment_notes` | TEXT | nullable |
| `email` | TEXT | nullable |
| `phone` | TEXT | nullable |
| `visa_type` | TEXT | nullable |
| `application_notes` | TEXT | nullable |
| `organization_id` | UUID | nullable |
| `created_by` | UUID | FK → profiles(id) |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | auto-updated via trigger |

**قيم الـ status:**
```
1 = Documents Collected (تم جمع المستندات)
2 = In Review (قيد المراجعة)
3 = Embassy Appointment (موعد السفارة)
4 = Submitted to Consulate (مقدم للقنصلية)
5 = Approved (موافق عليه)
6 = Rejected (مرفوض)
7 = Cancelled (ملغي)
```
**RLS:** `service_role` فقط — كل الوصول عبر الـ backend.

---

### جدول: `public.hotel_offers`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `hotel_name` | TEXT NOT NULL | |
| `hotel_location` | TEXT NOT NULL | |
| `hotel_city` | TEXT NOT NULL | |
| `hotel_country` | TEXT NOT NULL | |
| `hotel_rating` | NUMERIC(3,1) | nullable |
| `hotel_category` | TEXT | nullable |
| `room_type` | TEXT NOT NULL | |
| `board_basis` | TEXT | nullable |
| `price_per_night` | NUMERIC(12,2) NOT NULL | |
| `price_currency` | TEXT | default: `EGP` |
| `special_offer_price` | NUMERIC(12,2) | nullable |
| `available_from` | DATE NOT NULL | |
| `available_to` | DATE NOT NULL | |
| `booking_deadline` | DATE | nullable |
| `max_occupancy` | INTEGER | nullable |
| `available_rooms` | INTEGER | nullable |
| `amenities` | JSONB | default: `[]` |
| `description` | TEXT | nullable |
| `terms_conditions` | TEXT | nullable |
| `cancellation_policy` | TEXT | nullable |
| `source` | TEXT | `manual/excel_upload/word_upload/csv_upload` |
| `uploaded_file_reference` | TEXT | nullable |
| `is_active` | BOOLEAN | default: `true` |
| `created_by` | UUID | FK → profiles(id) |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | auto-updated |

**RLS:** `service_role` كامل؛ `authenticated` SELECT فقط (كل الصفوف).

---

### جدول: `public.payment_records`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `client_name` | TEXT NOT NULL | |
| `booking_reference` | TEXT | nullable |
| `amount` | NUMERIC(12,2) | CHECK (> 0) |
| `payment_method` | TEXT | `cash / bank / pos / cheque` |
| `status` | TEXT | `pending / partial / full / refunded / cancelled` |
| `payment_date` | DATE | nullable |
| `notes` | TEXT | nullable |
| `organization_id` | UUID | nullable |
| `created_by` | UUID | FK → profiles(id) |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | auto-updated |

**RLS:** `service_role` فقط.

---

### جدول: `public.flight_search_cache`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `cache_key` | TEXT UNIQUE | |
| `origin` | TEXT | |
| `destination` | TEXT | |
| `departure_date` | DATE | |
| `return_date` | DATE | nullable |
| `response_data` | JSONB | نتائج البحث |
| `expires_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ | |

**RLS:** `service_role` فقط — للاستخدام الداخلي.

---

### العلاقات بين الجداول
```
auth.users (Supabase managed)
    └── profiles.user_id  (one-to-one)
         profiles.id ──┬── visa_applications.created_by
                       ├── hotel_offers.created_by
                       └── payment_records.created_by
```

---

## 5. كل الـ API Endpoints

**Base URL:** `http://localhost:8000/api/v1`
> الـ Docs متاحة فقط في `ENVIRONMENT=development` على `/docs`

### Auth — `/api/v1/auth`
| Method | Path | Auth | Body |
|---|---|---|---|
| POST | `/auth/signup` | ❌ | `{email, password, first_name?, last_name?}` |
| POST | `/auth/login` | ❌ | `{email, password}` |
| GET | `/auth/health` | ❌ | — |

**Response للـ login:**
```json
{
  "success": true,
  "user": { "id": "uuid", "email": "..." },
  "session": { "access_token": "...", "refresh_token": "..." }
}
```

---

### Flights — `/api/v1/flights`

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/flights/search` | 🔒 | `{origin, destination, departure_date, return_date?, passenger_count, travel_class}` |
| POST | `/flights/clear-cache` | 🔒 | — |
| GET | `/flights/test-connection` | ❌ | — |
| GET | `/flights/health` | ❌ | — |

**`travel_class` values:** `economy / premium_economy / business / first`

---

### Documents — `/api/v1/documents`
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/documents/parse-hotel-data` | 🔒 | multipart/form-data — ملف `.xlsx/.xls/.csv/.docx` |
| GET | `/documents/health` | ❌ | — |

---

### Hotels — `/api/v1/hotels`
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/hotels/bulk-insert` | 🔒 | `[HotelOfferCreate, ...]` (max 500) |
| GET | `/hotels/search` | 🔒 | Query: `city?, country?, min_price?, max_price?, available_from?, available_to?, limit, offset` |
| DELETE | `/hotels/offers/{id}` | 🔒 | Soft delete (is_active=false) |
| GET | `/hotels/health` | ❌ | — |

---

### Visa — `/api/v1/visa`
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/visa/applications` | 🔒 | إنشاء طلب فيزا |
| GET | `/visa/applications` | 🔒 | Query: `client_name?, status?, limit, offset` |
| GET | `/visa/applications/{id}` | 🔒 | — |
| PATCH | `/visa/applications/{id}` | 🔒 | تعديل جزئي |
| PATCH | `/visa/applications/{id}/status` | 🔒 | Query: `new_status=1-7` |
| PATCH | `/visa/applications/{id}/appointment` | 🔒 | Query: `appointment_date, appointment_notes?` |
| DELETE | `/visa/applications/{id}` | 🔒 | — |
| GET | `/visa/status-summary` | 🔒 | إحصائيات الحالات |
| GET | `/visa/health` | ❌ | — |

---

### Payments — `/api/v1`
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/payments` | 🔒 | `{client_name, amount, payment_method, status?, ...}` |
| GET | `/payments` | 🔒 | Query: `client_name?, status?, payment_method?, date_from?, date_to?, limit, offset` |
| GET | `/payments/summary` | 🔒 | إحصائيات المدفوعات |
| PATCH | `/payments/{id}` | 🔒 | تعديل جزئي |
| DELETE | `/payments/{id}` | 🔒 | — |
| GET | `/payments/health` | ❌ | — |

---

## 6. Authentication Flow — خطوة بخطوة

```
1. POST /api/v1/auth/login  { email, password }
   ↓
2. Backend يتصل بـ supabase.auth.sign_in_with_password()
   ↓
3. يرجع { session: { access_token, refresh_token }, user: { id, email } }
   ↓
4. Frontend يحفظ في localStorage:
   key: 'travel_crm_sb_session'
   value: { session: { access_token, refresh_token, expires_at }, user: { id, email } }
   ↓
5. كل طلب محمي يرسل:
   Authorization: Bearer <access_token>
```

**مدة الـ Token:** 1 ساعة (Supabase default) — بعد انتهاء المدة المستخدم لازم يسجل دخول من جديد.

---

## 7. كيف تربط موقعك الجديد

### الطريقة الموصى بها — استخدام الـ FastAPI Backend

**الخطوة 1:** أضف origin موقعك في `CORS_ORIGINS` في ملف `.env` الخاص بالـ backend:

```env
CORS_ORIGINS=http://localhost:4000,http://localhost:5173,https://yoursite.com
```

**الخطوة 2:** في موقعك الجديد، اعمل login:
```javascript
const API_URL = 'http://localhost:8000/api/v1'

// Login
const res = await fetch(`${API_URL}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'user@example.com', password: 'Password123' })
})
const data = await res.json()

// احفظ الـ token
const accessToken = data.session.access_token
localStorage.setItem('access_token', accessToken)
```

**الخطوة 3:** استخدم الـ token في كل طلب محمي:
```javascript
const token = localStorage.getItem('access_token')

// مثال: جلب الفنادق
const hotels = await fetch(`${API_URL}/hotels/search?limit=50`, {
  headers: { 'Authorization': `Bearer ${token}` }
})
const data = await hotels.json()
// data.results = array of hotel offers

// مثال: جلب طلبات الفيزا
const visas = await fetch(`${API_URL}/visa/applications`, {
  headers: { 'Authorization': `Bearer ${token}` }
})

// مثال: إنشاء طلب فيزا جديد
const newVisa = await fetch(`${API_URL}/visa/applications`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    client_name: 'أحمد محمد',
    passport_number: 'A1234567',
    destination_country: 'Germany',
    visa_type: 'Tourist',
    status: 1
  })
})
```

### الطريقة البديلة — Supabase JS SDK مباشرة (للقراءة فقط)
```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://dnzvcvlebltbfcbcslkt.supabase.co',
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...ANON_KEY...'
)

// ملاحظة: hotel_offers متاحة للقراءة للـ authenticated users
// لكن visa_applications و payment_records تحتاج service_role → استخدم الـ backend
const { data } = await supabase
  .from('hotel_offers')
  .select('*')
  .eq('is_active', true)
  .limit(50)
```

---

## 8. Data Isolation Pattern

كل جدول عنده `created_by → profiles(id)`.
الـ backend:
1. يأخذ `user_id` من الـ JWT (`sub` claim)
2. يبحث عن `profiles.id` (الـ PK، مش `user_id`)
3. يفلتر كل القراءة/الكتابة بـ `.eq("created_by", profiles_id)`

يعني كل مستخدم يشوف بياناته بس.

---

## 9. Rate Limiting

الـ middleware بيطبق **100 request كل 60 ثانية لكل IP**.
الـ endpoints المعفاة: `/health`, `/`, `/docs`, `/redoc`

---

## 10. تشغيل الـ Backend

```bash
# Local
cd fastapi-backend/fastapi-backend
pip install -r requirements.txt
python main.py

# Docker
docker-compose up --build
```

**المتطلبات اللازمة عند الـ startup:**
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `JWT_SECRET_KEY`

---

## 11. تشغيل الـ migrations على Supabase

افتح Supabase Dashboard → SQL Editor → انسخ محتوى هذا الملف وشغّله:
```
supabase/migrations/RUN_THIS_IN_SUPABASE.sql
```
يعمل الـ 5 جداول كلهم مرة واحدة مع RLS و indexes.

---

## 12. ملاحظات أمنية

- ❌ لا تحط `SERVICE_ROLE_KEY` في الـ frontend أبداً
- ✅ الـ `ANON_KEY` آمن في الـ frontend
- ✅ كل الـ writes المهمة تمر عبر الـ backend بالـ service_role
- ⚠️ الـ access_token يتنتهي بعد 1 ساعة — لازم re-login
