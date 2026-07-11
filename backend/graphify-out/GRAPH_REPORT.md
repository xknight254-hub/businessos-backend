# Graph Report - /root/businessos/backend  (2026-07-11)

## Corpus Check
- Corpus is ~17,722 words - fits in a single context window. You may not need a graph.

## Summary
- 476 nodes · 1096 edges · 28 communities (25 shown, 3 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 80 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Core Infra
- Sales
- Memory/Agent
- DNA/Analytics
- Automation
- AI Services
- Partner/Chat
- Payments/M-Pesa
- Reports
- Products
- Customers
- Misc/Shared
- Core Infra
- Core Infra
- AI Services
- DNA/Analytics
- Payments/M-Pesa
- Reports
- AI Services

## God Nodes (most connected - your core abstractions)
1. `User` - 72 edges
2. `NotFoundError` - 25 edges
3. `ObservationEngine` - 24 edges
4. `Base` - 21 edges
5. `Product` - 20 edges
6. `Sale` - 19 edges
7. `BusinessDNA` - 19 edges
8. `BusinessMemory` - 18 edges
9. `get_current_user()` - 17 edges
10. `ConflictError` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_typed_errors_map_to_uniform_schema()` --calls--> `NotFoundError`  [EXTRACTED]
  tests/test_m14_typed_errors.py → app/core/exceptions.py
- `test_business_error_handler_shape()` --calls--> `ConflictError`  [EXTRACTED]
  tests/test_foundation.py → app/core/exceptions.py
- `test_typed_errors_map_to_uniform_schema()` --calls--> `ForbiddenError`  [EXTRACTED]
  tests/test_m14_typed_errors.py → app/core/exceptions.py
- `register()` --indirect_call--> `Business`  [INFERRED]
  app/api/auth/routes.py → app/models/__init__.py
- `login()` --indirect_call--> `User`  [INFERRED]
  app/api/auth/routes.py → app/models/__init__.py

## Import Cycles
- None detected.

## Communities (28 total, 3 thin omitted)

### Community 0 - "Core Infra"
Cohesion: 0.10
Nodes (37): get_current_user(), AsyncSession, login(), AsyncSession, refresh(), register(), send_code(), verify_code() (+29 more)

### Community 1 - "Sales"
Cohesion: 0.13
Nodes (32): require_role(), create_sale(), daily_summary(), get_sale(), list_sales(), AsyncSession, _sale_to_response(), void_sale() (+24 more)

### Community 2 - "Memory/Agent"
Cohesion: 0.08
Nodes (28): consolidate(), memory_stats(), AsyncSession, Store a new memory entry., Semantic search over business memory., Get memory usage statistics., Consolidate memory — prune stale, promote patterns., Get recent memory entries. (+20 more)

### Community 3 - "DNA/Analytics"
Cohesion: 0.09
Nodes (23): category_velocity(), customer_segments(), dna_profile(), health_score(), AsyncSession, Full Business DNA profile — categories, customers, suppliers, health., Category velocity signature — which categories sell fastest at what times., Customer segmentation using K-means clustering. (+15 more)

### Community 4 - "Automation"
Cohesion: 0.11
Nodes (27): automation_logs(), automation_suggestions(), create_rule(), delete_rule(), list_rules(), AsyncSession, BaseModel, Create default automation templates for this business. (+19 more)

### Community 5 - "AI Services"
Cohesion: 0.10
Nodes (18): anomalies(), check_readiness(), fast_movers(), get_observations(), peak_hours(), AsyncSession, AsyncSession, ObservationEngine (+10 more)

### Community 6 - "Partner/Chat"
Cohesion: 0.09
Nodes (20): capabilities(), chat(), AsyncSession, Chat with the AI Business Partner., List what the AI Business Partner can do., ChatMessage, ChatRequest, ChatResponse (+12 more)

### Community 7 - "Payments/M-Pesa"
Cohesion: 0.14
Nodes (20): initiate_stk_push(), mpesa_callback(), payment_history(), AsyncSession, query_payment_status(), Query the status of an STK Push transaction., List recent payments for the business., Initiate M-Pesa STK Push payment. (+12 more)

### Community 8 - "Reports"
Cohesion: 0.26
Nodes (18): get_me(), analytics_dashboard_view(), _day_start(), profit_loss(), AsyncSession, revenue_summary(), sales_chart(), top_customers() (+10 more)

### Community 9 - "Products"
Cohesion: 0.29
Nodes (17): adjust_stock(), create_product(), delete_product(), get_product(), list_categories(), list_products(), lookup_barcode(), AsyncSession (+9 more)

### Community 10 - "Customers"
Cohesion: 0.33
Nodes (14): add_credit(), create_customer(), get_customer(), list_customers(), pay_credit(), AsyncSession, update_customer(), NotFoundError (+6 more)

### Community 11 - "Misc/Shared"
Cohesion: 0.19
Nodes (7): MpesaClient, Client for Safaricom Daraja API (STK Push, C2B, B2C, reconciliation)., Query STK Push transaction status., Returns True if running without real Daraja credentials., Get OAuth access token from Daraja., Generate STK Push password: base64(shortcode + passkey + timestamp)., Initiate STK Push (Lipa na M-Pesa Online).

### Community 13 - "Core Infra"
Cohesion: 0.31
Nodes (7): Any, get_logger(), JsonFormatter, Structured logging for BusinessOS backend.  Provides a JSON formatter with reque, _redact(), Logger, LogRecord

### Community 14 - "Core Infra"
Cohesion: 0.31
Nodes (6): init_db(), new_correlation_id(), correlation_middleware(), lifespan(), FastAPI, Request

### Community 19 - "Payments/M-Pesa"
Cohesion: 0.22
Nodes (4): STK Push in mock mode should return success., Simulate M-Pesa callback for a successful payment., test_mpesa_callback_success(), test_stk_push_mock()

### Community 22 - "AI Services"
Cohesion: 0.43
Nodes (7): AIObservationListResponse, AIObservationResponse, AnomalyResponse, FastMoversResponse, InsightResponse, PeakHoursResponse, BaseModel

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `Reports` to `Core Infra`, `Sales`, `Memory/Agent`, `DNA/Analytics`, `Automation`, `AI Services`, `Partner/Chat`, `Payments/M-Pesa`, `Products`, `Customers`?**
  _High betweenness centrality (0.212) - this node is a cross-community bridge._
- **Why does `ObservationEngine` connect `AI Services` to `Automation`, `Partner/Chat`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `BusinessMemory` connect `Memory/Agent` to `Sales`, `AI Services`, `Partner/Chat`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `User` (e.g. with `login()` and `refresh()`) actually correct?**
  _`User` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `NotFoundError` (e.g. with `RuleCreate` and `RuleUpdate`) actually correct?**
  _`NotFoundError` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `ObservationEngine` (e.g. with `AutomationEngine` and `BusinessPartner`) actually correct?**
  _`ObservationEngine` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `Base` (e.g. with `AuditLog` and `AutomationLog`) actually correct?**
  _`Base` has 16 INFERRED edges - model-reasoned connections that need verification._