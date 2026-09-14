
# AI Assignment — Customer Service Agent for Ticket Booking (LangGraph + Groq)

## Overview

Build a **Customer Service AI Agent** that handles travel ticket booking operations through tool-calling:
- **Book** tickets (flights, trains, buses)
- **Inquiry** about bookings, schedules, availability
- **Refund** processing and cancellation

The agent uses a **ReAct-style tool-calling pattern** with LangGraph to route user requests and execute actions via defined tools against a local SQLite database.

**Model Provider:** Use **Groq** (free tier API) or any free model provider.

- Runs on: normal PC (CPU ok), 16GB RAM recommended

---

## Data & Schema (create locally)

### Database Setup

Create a local SQLite database (`data/travel.sqlite`) with the following schema:

```sql
-- Customers
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    loyalty_tier TEXT DEFAULT 'standard'  -- standard, silver, gold, platinum
);

-- Routes / Schedules
CREATE TABLE routes (
    route_id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    transport_type TEXT NOT NULL,          -- flight, train, bus
    carrier TEXT NOT NULL,                 -- airline/train company name
    departure_time TEXT NOT NULL,          -- ISO datetime
    arrival_time TEXT NOT NULL,
    price REAL NOT NULL,
    available_seats INTEGER NOT NULL,
    route_code TEXT UNIQUE NOT NULL        -- e.g., "EG-101", "TR-450"
);

-- Bookings
CREATE TABLE bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    route_id INTEGER NOT NULL,
    booking_ref TEXT UNIQUE NOT NULL,      -- e.g., "BK-20250801-001"
    status TEXT DEFAULT 'confirmed',       -- confirmed, cancelled, refunded, pending
    seat_number TEXT,
    booking_date TEXT NOT NULL,            -- ISO date
    payment_amount REAL NOT NULL,
    payment_method TEXT,                   -- credit_card, wallet, cash
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (route_id) REFERENCES routes(route_id)
);

-- Refunds
CREATE TABLE refunds (
    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    refund_amount REAL NOT NULL,
    refund_reason TEXT,
    refund_status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    requested_date TEXT NOT NULL,
    processed_date TEXT,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id)
);
```

### Seed Data Script

Create `data/seed.py` to populate the database with:
- **10+ customers** (mix of loyalty tiers)
- **20+ routes** (flights, trains, buses across 8+ cities)
- **15+ bookings** (various statuses)
- **5+ refunds** (various states)

### SQL Seed Query (20 records per table)

After creating the tables, run the following SQL to populate all tables with 20 linked records:

```sql
-- =========================
-- 1. CUSTOMERS (20 records)
-- =========================
INSERT INTO customers (full_name, email, phone, loyalty_tier) VALUES
('Ahmed Hassan', 'ahmed.hassan@gmail.com', '+201001234567', 'gold'),
('Fatma El-Sayed', 'fatma.elsayed@yahoo.com', '+201112345678', 'platinum'),
('Mohamed Ali', 'mohamed.ali@outlook.com', '+201223456789', 'standard'),
('Nour Ibrahim', 'nour.ibrahim@gmail.com', '+201034567890', 'silver'),
('Yasmin Khaled', 'yasmin.khaled@hotmail.com', '+201145678901', 'standard'),
('Omar Mostafa', 'omar.mostafa@gmail.com', '+201256789012', 'gold'),
('Hana Adel', 'hana.adel@yahoo.com', '+201067890123', 'standard'),
('Karim Samir', 'karim.samir@gmail.com', '+201178901234', 'silver'),
('Salma Tarek', 'salma.tarek@outlook.com', '+201289012345', 'platinum'),
('Youssef Magdy', 'youssef.magdy@gmail.com', '+201090123456', 'standard'),
('Mariam Fouad', 'mariam.fouad@yahoo.com', '+201101234560', 'gold'),
('Tamer Reda', 'tamer.reda@gmail.com', '+201212345601', 'standard'),
('Dina Sherif', 'dina.sherif@hotmail.com', '+201023456012', 'silver'),
('Amr Gamal', 'amr.gamal@outlook.com', '+201134560123', 'standard'),
('Rania Nabil', 'rania.nabil@gmail.com', '+201245601234', 'platinum'),
('Khaled Mahmoud', 'khaled.mahmoud@yahoo.com', '+201056012345', 'gold'),
('Sara Wael', 'sara.wael@gmail.com', '+201167012345', 'standard'),
('Hazem Ashraf', 'hazem.ashraf@outlook.com', '+201278012345', 'silver'),
('Laila Hossam', 'laila.hossam@gmail.com', '+201089012345', 'standard'),
('Mostafa Emad', 'mostafa.emad@yahoo.com', '+201190123456', 'gold');

-- =========================
-- 2. ROUTES (20 records)
-- =========================
INSERT INTO routes (origin, destination, transport_type, carrier, departure_time, arrival_time, price, available_seats, route_code) VALUES
('Cairo', 'Alexandria', 'train', 'Egyptian Railways', '2025-09-15T08:00:00', '2025-09-15T10:30:00', 150.00, 120, 'TR-101'),
('Cairo', 'Luxor', 'flight', 'EgyptAir', '2025-09-15T06:00:00', '2025-09-15T07:15:00', 1800.00, 45, 'EG-201'),
('Cairo', 'Aswan', 'flight', 'Nile Air', '2025-09-16T09:00:00', '2025-09-16T10:30:00', 2200.00, 38, 'NA-301'),
('Cairo', 'Hurghada', 'bus', 'Go Bus', '2025-09-15T22:00:00', '2025-09-16T04:00:00', 350.00, 49, 'GB-401'),
('Alexandria', 'Cairo', 'train', 'Egyptian Railways', '2025-09-16T14:00:00', '2025-09-16T16:30:00', 150.00, 95, 'TR-102'),
('Luxor', 'Aswan', 'train', 'Egyptian Railways', '2025-09-17T07:00:00', '2025-09-17T10:00:00', 120.00, 80, 'TR-103'),
('Hurghada', 'Cairo', 'flight', 'EgyptAir', '2025-09-18T12:00:00', '2025-09-18T13:00:00', 1600.00, 50, 'EG-202'),
('Cairo', 'Sharm El Sheikh', 'flight', 'Nile Air', '2025-09-15T10:00:00', '2025-09-15T11:00:00', 2000.00, 42, 'NA-302'),
('Sharm El Sheikh', 'Cairo', 'flight', 'EgyptAir', '2025-09-19T16:00:00', '2025-09-19T17:00:00', 1900.00, 55, 'EG-203'),
('Cairo', 'Marsa Alam', 'bus', 'Blue Bus', '2025-09-16T20:00:00', '2025-09-17T04:30:00', 400.00, 44, 'BB-501'),
('Alexandria', 'Luxor', 'train', 'Egyptian Railways', '2025-09-17T22:00:00', '2025-09-18T08:00:00', 280.00, 60, 'TR-104'),
('Aswan', 'Cairo', 'flight', 'EgyptAir', '2025-09-20T11:00:00', '2025-09-20T12:30:00', 2100.00, 40, 'EG-204'),
('Cairo', 'Dahab', 'bus', 'Go Bus', '2025-09-15T18:00:00', '2025-09-16T02:00:00', 380.00, 46, 'GB-402'),
('Luxor', 'Hurghada', 'bus', 'Blue Bus', '2025-09-18T06:00:00', '2025-09-18T10:00:00', 200.00, 48, 'BB-502'),
('Cairo', 'Siwa Oasis', 'bus', 'West Delta', '2025-09-19T07:00:00', '2025-09-19T15:00:00', 300.00, 35, 'WD-601'),
('Hurghada', 'Luxor', 'bus', 'Go Bus', '2025-09-20T08:00:00', '2025-09-20T12:00:00', 220.00, 47, 'GB-403'),
('Cairo', 'Ain Sokhna', 'bus', 'Go Bus', '2025-09-15T07:00:00', '2025-09-15T09:00:00', 100.00, 50, 'GB-404'),
('Sharm El Sheikh', 'Hurghada', 'flight', 'Nile Air', '2025-09-21T09:00:00', '2025-09-21T10:00:00', 1500.00, 36, 'NA-303'),
('Alexandria', 'Marsa Matrouh', 'bus', 'West Delta', '2025-09-16T06:00:00', '2025-09-16T10:00:00', 180.00, 42, 'WD-602'),
('Cairo', 'Fayoum', 'bus', 'Blue Bus', '2025-09-17T09:00:00', '2025-09-17T11:00:00', 80.00, 44, 'BB-503');

-- =========================
-- 3. BOOKINGS (20 records)
-- =========================
INSERT INTO bookings (customer_id, route_id, booking_ref, status, seat_number, booking_date, payment_amount, payment_method) VALUES
(1,  1,  'BK-20250901-001', 'confirmed',  'A12', '2025-09-01', 150.00,  'credit_card'),
(2,  2,  'BK-20250901-002', 'confirmed',  'B03', '2025-09-01', 1800.00, 'credit_card'),
(3,  3,  'BK-20250902-003', 'confirmed',  'C07', '2025-09-02', 2200.00, 'wallet'),
(4,  4,  'BK-20250902-004', 'confirmed',  'D15', '2025-09-02', 350.00,  'cash'),
(5,  5,  'BK-20250903-005', 'cancelled',  'A08', '2025-09-03', 150.00,  'credit_card'),
(6,  6,  'BK-20250903-006', 'confirmed',  'B22', '2025-09-03', 120.00,  'wallet'),
(7,  7,  'BK-20250904-007', 'confirmed',  'C01', '2025-09-04', 1600.00, 'credit_card'),
(8,  8,  'BK-20250904-008', 'pending',    'D10', '2025-09-04', 2000.00, 'wallet'),
(9,  9,  'BK-20250905-009', 'confirmed',  'A05', '2025-09-05', 1900.00, 'credit_card'),
(10, 10, 'BK-20250905-010', 'confirmed',  'B18', '2025-09-05', 400.00,  'cash'),
(11, 11, 'BK-20250906-011', 'confirmed',  'C14', '2025-09-06', 280.00,  'credit_card'),
(12, 12, 'BK-20250906-012', 'cancelled',  'D02', '2025-09-06', 2100.00, 'wallet'),
(1,  13, 'BK-20250907-013', 'confirmed',  'A20', '2025-09-07', 380.00,  'cash'),
(2,  14, 'BK-20250907-014', 'confirmed',  'B09', '2025-09-07', 200.00,  'credit_card'),
(13, 15, 'BK-20250908-015', 'pending',    'C11', '2025-09-08', 300.00,  'wallet'),
(14, 16, 'BK-20250908-016', 'confirmed',  'D06', '2025-09-08', 220.00,  'cash'),
(15, 17, 'BK-20250909-017', 'confirmed',  'A03', '2025-09-09', 100.00,  'credit_card'),
(16, 18, 'BK-20250909-018', 'refunded',   'B25', '2025-09-09', 1500.00, 'credit_card'),
(17, 19, 'BK-20250910-019', 'confirmed',  'C19', '2025-09-10', 180.00,  'wallet'),
(18, 20, 'BK-20250910-020', 'confirmed',  'D08', '2025-09-10', 80.00,   'cash');

-- =========================
-- 4. REFUNDS (20 records)
-- =========================
INSERT INTO refunds (booking_id, refund_amount, refund_reason, refund_status, requested_date, processed_date) VALUES
(5,  150.00,  'Schedule change',              'approved',  '2025-09-03', '2025-09-05'),
(12, 2100.00, 'Flight cancelled by airline',  'approved',  '2025-09-06', '2025-09-08'),
(18, 1500.00, 'Personal emergency',           'approved',  '2025-09-09', '2025-09-11'),
(8,  2000.00, 'Changed travel plans',         'pending',   '2025-09-05', NULL),
(1,  150.00,  'Found cheaper option',         'rejected',  '2025-09-04', '2025-09-06'),
(2,  1800.00, 'Medical reason',               'approved',  '2025-09-05', '2025-09-07'),
(3,  1650.00, 'Partial refund - 24hr policy', 'approved',  '2025-09-06', '2025-09-08'),
(4,  175.00,  'Partial refund - 12hr policy', 'approved',  '2025-09-07', '2025-09-09'),
(6,  120.00,  'Duplicate booking',            'approved',  '2025-09-08', '2025-09-10'),
(7,  0.00,    'Too close to departure',       'rejected',  '2025-09-09', '2025-09-09'),
(9,  1900.00, 'Trip postponed',               'pending',   '2025-09-10', NULL),
(10, 400.00,  'Wrong destination booked',     'approved',  '2025-09-10', '2025-09-12'),
(11, 280.00,  'Family emergency',             'approved',  '2025-09-11', '2025-09-13'),
(13, 380.00,  'Weather concerns',             'pending',   '2025-09-12', NULL),
(14, 200.00,  'Schedule conflict',            'approved',  '2025-09-12', '2025-09-14'),
(15, 300.00,  'Changed mind',                 'rejected',  '2025-09-13', '2025-09-13'),
(16, 220.00,  'Health issue',                 'pending',   '2025-09-13', NULL),
(17, 100.00,  'Road closure reported',        'approved',  '2025-09-14', '2025-09-15'),
(19, 180.00,  'Visa issue',                   'pending',   '2025-09-15', NULL),
(20, 80.00,   'Found alternative transport',  'rejected',  '2025-09-15', '2025-09-15');
```

> Use realistic Egyptian/Middle Eastern cities (Cairo, Alexandria, Luxor, Aswan, Hurghada, Sharm El Sheikh, etc.) and international routes.

---

## Policies Document (create `docs/policies.md`)

```markdown
# Customer Service Policies

## Booking Policy
- Bookings require: customer_id, route_id, payment_method
- Seat assignment is automatic unless specified
- Booking confirmation generates a unique booking_ref (format: BK-YYYYMMDD-XXX)
- Overbooking is not allowed (check available_seats before confirming)

## Refund Policy
- Full refund: cancellation ≥48 hours before departure
- Partial refund (75%): cancellation 24–48 hours before departure
- Partial refund (50%): cancellation 12–24 hours before departure
- No refund: cancellation <12 hours before departure
- Gold/Platinum loyalty members get +10% refund bonus (capped at 100%)
- Refunds processed within 3–5 business days

## Inquiry Scope
- Agent can provide: booking status, schedule info, availability, pricing, refund status
- Agent cannot provide: personal financial advice, competitor comparisons, or medical travel advice
- If question is out of scope, politely redirect
```

---

## What to Build

### Agent Role

You are a **Customer Service Agent** for a travel booking platform. You handle user requests by:
1. Understanding the user's intent (book, inquire, refund)
2. Calling the appropriate tools with validated parameters
3. Applying business rules from the policies document
4. Returning structured, helpful responses

---

### LangGraph Architecture (≥6 nodes, stateful)

Implement the agent with at least these nodes:

1. **Intent Classifier** — Classify user message into: `book` | `inquiry` | `refund` | `out_of_scope`
2. **Entity Extractor** — Extract entities: customer_id, route, dates, booking_ref, cities, etc.
3. **Policy Checker** — Validate request against business rules (refund eligibility, seat availability)
4. **Tool Executor** — Execute the appropriate tool(s) based on intent
5. **Response Generator** — Format the final response for the customer
6. **Confirmation Node** — For destructive actions (booking, refund), ask for user confirmation before executing
7. **Error Handler / Repair Loop** — On tool failure or policy violation, explain the issue and suggest alternatives (max 2 retries)

---

### Tools to Implement (in `agent/tools/`)

Each tool is a callable function the agent invokes:

#### `search_routes`
```python
# Input: origin, destination, date, transport_type (optional)
# Output: list of available routes with prices and seats
# Action: SELECT from routes table with filters
```

#### `book_ticket`
```python
# Input: customer_id, route_id, payment_method, seat_number (optional)
# Output: booking confirmation with booking_ref
# Action: INSERT into bookings, UPDATE available_seats in routes
# Validation: check seat availability, valid customer, valid route
```

#### `get_booking_status`
```python
# Input: booking_ref OR customer_id
# Output: booking details (status, route info, payment)
# Action: SELECT from bookings JOIN routes
```

#### `request_refund`
```python
# Input: booking_ref, reason
# Output: refund eligibility + amount based on policy
# Action: INSERT into refunds, UPDATE booking status
# Validation: apply refund policy rules (time-based %)
```

#### `cancel_booking`
```python
# Input: booking_ref
# Output: cancellation confirmation
# Action: UPDATE booking status to 'cancelled', restore available_seats
```

---

## Eval File

Create `sample_questions_eval.jsonl`:

```jsonl
{"id":"inquiry_route_search","message":"What flights are available from Cairo to Luxor on 2025-09-15?","expected_intent":"inquiry","expected_tool":"search_routes"}
{"id":"book_simple","message":"I'd like to book a train from Cairo to Alexandria. My customer ID is 3, and I'll pay by credit card.","expected_intent":"book","expected_tool":"book_ticket"}
{"id":"inquiry_booking_status","message":"Can you check the status of my booking BK-20250801-003?","expected_intent":"inquiry","expected_tool":"get_booking_status"}
{"id":"refund_eligible","message":"I need to cancel and get a refund for booking BK-20250801-005. My flight is in 3 days.","expected_intent":"refund","expected_tool":"request_refund"}
{"id":"refund_ineligible","message":"I want a refund for booking BK-20250801-007. The bus leaves in 6 hours.","expected_intent":"refund","expected_tool":"request_refund"}
{"id":"out_of_scope","message":"Can you recommend a good hotel in Sharm El Sheikh?","expected_intent":"out_of_scope","expected_tool":"none"}
{"id":"book_no_seats","message":"Book me on route EG-101 please. Customer ID 5, paying with wallet.","expected_intent":"book","expected_tool":"book_ticket"}
{"id":"inquiry_refund_status","message":"What's the status of my refund for booking BK-20250801-005?","expected_intent":"inquiry","expected_tool":"get_booking_status"}
```

---

## Output Contract (per interaction)

```json
{
  "id": "...",
  "intent": "book | inquiry | refund | out_of_scope",
  "tools_called": ["tool_name_1", "tool_name_2"],
  "tool_inputs": { "tool_name": { "param": "value" } },
  "tool_outputs": { "tool_name": { "result": "..." } },
  "policy_applied": "refund_policy::48hr_rule | booking_policy::seat_check | ...",
  "final_response": "<customer-facing message>",
  "confirmation_required": true | false,
  "confidence": 0.0
}
```

---

## CLI

```bash
# Batch mode (eval)
python run_agent.py --batch sample_questions_eval.jsonl --out outputs.jsonl

# Interactive mode (chat)
python run_agent.py --interactive --customer-id 3
```

---

## Project Skeleton

```
your_project/
├── agent/
│   ├── graph.py                 # LangGraph definition (≥6 nodes)
│   ├── nodes/
│   │   ├── intent_classifier.py
│   │   ├── entity_extractor.py
│   │   ├── policy_checker.py
│   │   ├── tool_executor.py
│   │   ├── response_generator.py
│   │   ├── confirmation.py
│   │   └── error_handler.py
│   └── tools/
│       ├── search_routes.py
│       ├── book_ticket.py
│       ├── get_booking_status.py
│       ├── request_refund.py
│       └── cancel_booking.py
├── data/
│   ├── travel.sqlite            # generated by seed.py
│   └── seed.py                  # database seeding script
├── docs/
│   └── policies.md             # business rules
├── sample_questions_eval.jsonl
├── run_agent.py                 # main entrypoint
└── requirements.txt
```

---

## Acceptance Criteria & Scoring

| Criteria | Weight | Description |
|----------|--------|-------------|
| **Correctness** | 40% | Correct intent classification, proper tool selection, accurate results |
| **Policy Compliance** | 20% | Refund calculations match policy, seat checks enforced |
| **Resilience** | 20% | Error handling works (no seats, invalid refs, policy violations), repair loop functional |
| **Clarity** | 20% | Clean code, helpful customer-facing responses, proper confirmation flow, README |

---

## Model Setup (Groq — Free Tier)

### Getting Started

1. Sign up at https://console.groq.com (free)
2. Create an API key
3. Set environment variable:
```bash
export GROQ_API_KEY="your-api-key-here"
```

### Usage

```python
from langchain_groq import ChatGroq

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0,
    api_key=os.environ["GROQ_API_KEY"]
)
```

### Alternative Free Providers

- **Together AI** — https://together.ai
- **OpenRouter** — https://openrouter.ai
- **Google AI Studio** (Gemini) — https://aistudio.google.com

---

## Implementation Hints

### Intent Classification
- Use a structured prompt with few-shot examples
- Map ambiguous intents to `inquiry` as default (safe fallback)

### Entity Extraction
- Extract: customer_id, booking_ref, origin, destination, date, transport_type, payment_method
- Handle partial info gracefully (ask user for missing required fields)

### Policy Checker
- Parse departure time from route, compare with current time
- Calculate refund percentage based on time difference
- Check loyalty tier for bonus calculation

### Confirmation Flow
- For `book` and `refund` intents, present a summary and ask "Confirm? (yes/no)"
- In batch mode, auto-confirm for evaluation purposes

### Error Handling
- No available seats → suggest alternative routes/dates
- Invalid booking_ref → ask user to verify
- Policy violation → explain why and suggest alternatives

---

## requirements.txt

```
langchain-groq>=0.1.0
langgraph>=0.1.0
langchain-core>=0.2.0
pydantic>=2.0.0
click>=8.1.7
rich>=13.7.0
numpy>=1.26.0
pandas>=2.2.0
```

---

## Deliverables

1. **Code** in `agent/` (graph, nodes, tools)
2. **Database** seeded with realistic data (`data/seed.py`)
3. **README.md** containing:
   - Architecture diagram description (nodes + edges)
   - How policies are enforced
   - Any assumptions made
4. **outputs.jsonl** generated by the CLI batch command

**Please share the Github link.**

---

## Notes & Constraints

- **Free tier limits**: Design efficient prompts to minimize API calls
- Keep prompts compact (≤1k tokens)
- Bound repair/retry to ≤2 iterations
- The agent should NEVER execute a booking or refund without confirmation (except in batch eval mode)
- All monetary values in EGP (Egyptian Pounds)

---

**Good luck — build a helpful, policy-compliant agent!**
