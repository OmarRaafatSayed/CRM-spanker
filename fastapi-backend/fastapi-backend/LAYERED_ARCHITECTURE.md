# Layered Architecture - FastAPI Backend

## 🏗️ Architecture Overview

This backend follows a **3-tier layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────┐
│           PRESENTATION LAYER (Routers)          │
│  - REST API endpoints                           │
│  - Request validation                           │
│  - Response formatting                          │
│  - Authentication & Authorization               │
└───────────────────┬─────────────────────────────┘
                    │ depends on
┌───────────────────▼─────────────────────────────┐
│        BUSINESS LOGIC LAYER (Services)          │
│  - Business rules & workflows                   │
│  - Data transformation                          │
│  - Cross-entity operations                      │
│  - Complex calculations                         │
└───────────────────┬─────────────────────────────┘
                    │ depends on
┌───────────────────▼─────────────────────────────┐
│       DATA ACCESS LAYER (Repositories)          │
│  - CRUD operations                              │
│  - Database queries                             │
│  - Data persistence                             │
│  - Query optimization                           │
└───────────────────┬─────────────────────────────┘
                    │ uses
┌───────────────────▼─────────────────────────────┐
│              MODELS (Domain)                    │
│  - Data structures                              │
│  - Entity definitions                           │
│  - Validation rules                             │
└─────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```
app/
├── models/                     # Domain Models Layer
│   ├── base.py                # Base model with common fields
│   ├── customer.py            # Customer entity
│   ├── visa_application.py    # Visa application entity
│   ├── document.py            # Document entity
│   ├── quotation.py           # Quotation entity
│   ├── booking.py             # Booking entity
│   ├── transaction.py         # Financial transaction entity
│   └── __init__.py
│
├── repositories/               # Data Access Layer
│   ├── base.py                # Generic CRUD repository
│   ├── customer_repository.py
│   ├── visa_repository.py
│   ├── document_repository.py
│   ├── quotation_repository.py
│   ├── booking_repository.py
│   ├── transaction_repository.py
│   └── __init__.py
│
├── business/                   # Business Logic Layer (Services)
│   ├── customer_service.py
│   ├── visa_service.py
│   ├── quotation_service.py
│   ├── booking_service.py
│   ├── payment_service.py
│   └── __init__.py
│
├── routers/                    # Presentation Layer (Controllers)
│   ├── crm_customers_v2.py    # New layered architecture router
│   ├── crm_customers.py       # Old router (legacy)
│   ├── auth.py
│   ├── flights.py
│   └── ...
│
├── core/
│   ├── dependencies.py         # Dependency injection
│   ├── security.py            # Auth & security
│   └── ...
│
└── services/
    └── supabase_client.py     # Database client
```

---

## 🎯 Layer Responsibilities

### 1. **Models Layer** (`app/models/`)

**Purpose:** Define domain entities and data structures

**Responsibilities:**
- Define entity structure (fields, types)
- Validation rules
- Data serialization/deserialization
- Type hints

**Example:**
```python
from app.models.customer import Customer

customer = Customer(
    auth_user_id="auth123",
    email="user@example.com",
    full_name="Ahmed Mohamed",
    status="LEAD"
)
```

**Rules:**
- ✅ No database logic
- ✅ No business logic
- ✅ Pure data structures
- ✅ Validation only

---

### 2. **Repository Layer** (`app/repositories/`)

**Purpose:** Handle all database operations

**Responsibilities:**
- CRUD operations (Create, Read, Update, Delete)
- Database queries
- Data filtering and sorting
- Transaction management
- Query optimization

**Example:**
```python
from app.repositories.customer_repository import CustomerRepository

repo = CustomerRepository(supabase)

# Get customer by ID
customer = repo.get_by_id("customer_123")

# Find customers by status
leads = repo.get_by_status("LEAD", limit=50)

# Create new customer
new_customer = repo.create({
    "email": "new@example.com",
    "status": "LEAD"
})
```

**Rules:**
- ✅ Only database operations
- ✅ Return domain models
- ✅ No business logic
- ✅ No HTTP/API logic

---

### 3. **Service Layer** (`app/business/`)

**Purpose:** Implement business logic and workflows

**Responsibilities:**
- Business rules enforcement
- Multi-step operations
- Data transformation
- Cross-entity coordination
- Complex calculations
- Business validations

**Example:**
```python
from app.business.booking_service import BookingService

service = BookingService(supabase)

# Complex operation with business logic
booking = service.create_booking({
    "user_id": "user_123",
    "quotation_id": "quote_456"
})
# ^ This automatically:
#   - Generates booking reference
#   - Gets quotation details
#   - Updates quotation status
#   - Creates transaction
#   - Sets proper status
```

**Rules:**
- ✅ Orchestrate repositories
- ✅ Implement business rules
- ✅ Handle complex workflows
- ✅ Transform data
- ❌ No database queries directly
- ❌ No HTTP/API logic

---

### 4. **Router Layer** (`app/routers/`)

**Purpose:** Handle HTTP requests and responses

**Responsibilities:**
- Define API endpoints
- Request validation
- Response formatting
- Authentication & authorization
- HTTP error handling
- Call services (not repositories directly)

**Example:**
```python
from app.core.dependencies import get_booking_service

@router.get("/bookings/{booking_id}")
async def get_booking(
    booking_id: str,
    token: AuthToken = Depends(require_auth),
    booking_service: BookingService = Depends(get_booking_service),
):
    """Get booking details"""
    _require_staff(token)
    
    booking = booking_service.get_booking(booking_id)
    
    if not booking:
        raise HTTPException(status_code=404, detail="Not found")
    
    return booking.to_dict()
```

**Rules:**
- ✅ Use services via dependency injection
- ✅ Handle HTTP concerns only
- ✅ Validate requests
- ❌ No business logic
- ❌ No database queries
- ❌ Don't call repositories directly

---

## 🔄 Request Flow Example

### Example: Record a payment

```
1. HTTP Request
   POST /api/v1/transactions/txn_123/payment
   Body: { amount_paid: 500, payment_method: "BANK_TRANSFER" }
   ↓

2. Router (crm_customers_v2.py)
   - Validates request
   - Checks authentication
   - Extracts parameters
   ↓

3. PaymentService
   - Gets transaction from repository
   - Calculates new totals
   - Validates payment amount
   - Updates payment status
   - If fully paid → confirms booking
   ↓

4. TransactionRepository
   - Updates transaction in database
   - Returns updated entity
   ↓

5. BookingRepository (if fully paid)
   - Updates booking status
   ↓

6. Response
   - Return success with updated data
```

---

## 🧩 Dependency Injection

All services and repositories are injected using FastAPI's `Depends()`.

### Using Services in Routers

```python
from app.core.dependencies import get_customer_service
from app.business.customer_service import CustomerService

@router.get("/customers")
async def list_customers(
    customer_service: CustomerService = Depends(get_customer_service)
):
    result = customer_service.list_customers(limit=50)
    return result
```

### Available Dependencies

```python
# Services
from app.core.dependencies import (
    get_customer_service,
    get_visa_service,
    get_quotation_service,
    get_booking_service,
    get_payment_service
)

# Repositories (if needed directly)
from app.core.dependencies import (
    get_customer_repository,
    get_visa_repository,
    get_document_repository,
    # ...
)
```

---

## ✅ Benefits of Layered Architecture

### 1. **Separation of Concerns**
- Each layer has a single responsibility
- Easy to understand and maintain
- Changes in one layer don't affect others

### 2. **Testability**
- Services can be tested without HTTP
- Repositories can be mocked
- Business logic isolated from infrastructure

### 3. **Reusability**
- Services can be used by multiple routers
- Repositories can be used by multiple services
- Models can be used everywhere

### 4. **Maintainability**
- Clear structure
- Easy to locate code
- Consistent patterns

### 5. **Scalability**
- Easy to add new features
- Can replace data layer (e.g., switch from Supabase to PostgreSQL)
- Can add caching layer easily

---

## 📝 Best Practices

### DO ✅

1. **Use dependency injection**
   ```python
   service: CustomerService = Depends(get_customer_service)
   ```

2. **Return models from repositories**
   ```python
   def get_by_id(self, id: str) -> Optional[Customer]:
       # ...
       return Customer.from_db(data)
   ```

3. **Keep business logic in services**
   ```python
   class BookingService:
       def confirm_booking(self, booking_id: str):
           # Complex business logic here
   ```

4. **Handle HTTP errors in routers only**
   ```python
   if not customer:
       raise HTTPException(status_code=404)
   ```

### DON'T ❌

1. **Don't call repositories from routers**
   ```python
   # ❌ Bad
   repo = CustomerRepository(supabase)
   customer = repo.get_by_id(id)
   
   # ✅ Good
   customer = customer_service.get_customer(id)
   ```

2. **Don't put business logic in repositories**
   ```python
   # ❌ Bad - repository
   def create_booking(self, data):
       data["reference"] = generate_reference()  # Business logic!
   
   # ✅ Good - service
   def create_booking(self, data):
       data["reference"] = self._generate_reference()
       return self.repository.create(data)
   ```

3. **Don't raise HTTPException in services**
   ```python
   # ❌ Bad - service
   if not customer:
       raise HTTPException(404)
   
   # ✅ Good - service
   return None  # Let router handle HTTP response
   ```

---

## 🚀 Migration Guide

### Old Pattern (Direct Database Access)
```python
@router.get("/customers")
async def list_customers(supabase = Depends(get_supabase)):
    response = supabase.table("users").select("*").execute()
    return {"customers": response.data}
```

### New Pattern (Layered Architecture)
```python
@router.get("/customers")
async def list_customers(
    customer_service: CustomerService = Depends(get_customer_service)
):
    result = customer_service.list_customers(limit=50)
    return result
```

---

## 📚 Usage Examples

See `app/routers/crm_customers_v2.py` for complete examples using the new architecture.

---

## 🎓 Summary

| Layer | Folder | Purpose | Can Use |
|-------|--------|---------|---------|
| **Models** | `app/models/` | Data structures | Nothing |
| **Repositories** | `app/repositories/` | Database operations | Models |
| **Services** | `app/business/` | Business logic | Repositories, Models |
| **Routers** | `app/routers/` | API endpoints | Services, Models |

**Remember:** 
- **Routers** → call **Services**
- **Services** → call **Repositories**
- **Repositories** → return **Models**

This creates a clean, maintainable, and testable codebase! 🎉
