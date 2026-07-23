# CLMStore — Product Requirements Document
**Version:** 1.0  
**Date:** 2026-07-01  
**Status:** Active — Single source of truth for all engineering, design, and product decisions.

---

## 1. Product Vision

CLMStore is Sierra Leone's restaurant delivery marketplace. It connects customers in Freetown with restaurants through a fast, simple mobile-first experience. Every important action is achievable in three taps or fewer.

The backend is architected generically (businesses, products, orders) so future categories (grocery, pharmacy) can be enabled without redesigning the database or API. Today it launches as a restaurant-only platform.

**Primary market:** Freetown, Sierra Leone  
**Primary device:** Android smartphones (low-to-mid range)  
**Primary payment:** Orange Money, Afrimoney, Cash on delivery  
**Language:** English

---

## 2. User Roles

| Role | Description |
|------|-------------|
| `customer` | Discovers restaurants, orders food, tracks delivery |
| `restaurant_owner` | Manages restaurant profile, menu, orders, staff, promotions |
| `restaurant_employee` | Limited dashboard access (manage orders, mark items unavailable) |
| `rider` | Accepts delivery jobs, navigates, updates status |
| `admin` | Manages platform — approvals, disputes, analytics, commissions |
| `super_admin` | Full platform control including admin management |

---

## 3. User Journeys

### 3.1 Customer Journey
```
Discover → Search/Browse → View Restaurant → Customize Meal →
Add to Cart → Checkout → Pay → Track Order in Real Time →
Receive Food → Rate Experience → Reorder
```

### 3.2 Restaurant Journey
```
Register → Upload License (optional) → Verify Phone →
Configure Profile → Set Hours/Days → Build Menu →
Get Approved → Go Live → Receive Orders →
Prepare Food → Mark Ready → Get Paid → View Insights
```

### 3.3 Rider Journey
```
Register → Get Verified → Set Available → Receive Request →
Accept → Navigate to Restaurant → Confirm Pickup →
Navigate to Customer → Confirm Delivery → Get Paid
```

### 3.4 Admin Journey
```
Review Restaurant Applications → Approve/Reject →
Monitor Orders → Handle Disputes → Manage Commissions →
View Platform Analytics → Generate Reports
```

---

## 4. Features

### 4.1 Customer Features

#### Discovery & Search
- Home feed with featured restaurants and "Open Now" section
- Smart search: by restaurant name, food name, cuisine, ingredient, price range, location
  - Searching "Jollof Rice" returns every restaurant serving it
  - Searching "Chicken" returns all chicken dishes
- Filters: rating, delivery fee, distance, estimated delivery time, open now, cuisine
- Recently viewed restaurants
- Favorite restaurants and favorite food items

#### Restaurant & Menu
- Restaurant detail page: photos, rating breakdown, hours, delivery info
- Menu organized by categories (Starters, Mains, Drinks, Desserts)
- Food item detail: photo, description, price, nutritional info (optional)
- **Meal customization** (critical feature):
  - Choose variant (e.g., Chicken / Fish / Beef / Shrimp)
  - Add extras (e.g., Extra Cheese, Extra Pepper, Extra Sauce)
  - Remove ingredients (e.g., No Onion, No Tomato)
  - Special instructions text field
- Real-time stock status (item available / unavailable)

#### Cart & Checkout
- Cart persists across sessions
- Cart shows restaurant name, items, quantities, subtotal
- One-click reorder from order history
- Coupon / promo code field at checkout
- Loyalty points redemption
- Address selection or add new
- Payment method selection (Orange Money, Afrimoney, Visa, Cash)
- Order summary before confirming

#### Order Tracking
- Real-time status updates via WebSocket
- Status stages with time estimates:
  1. Order Placed
  2. Restaurant Confirmed
  3. Kitchen Preparing
  4. Ready for Pickup
  5. Rider Accepted
  6. Rider at Restaurant
  7. Food Picked Up
  8. Rider En Route
  9. Delivered
- Map showing rider location (phase 2 with GPS)
- Push notification at each stage
- In-app notification center

#### Profile & Account
- Saved delivery addresses (with labels: Home, Work, etc.)
- Order history with reorder button
- Favorite restaurants and foods
- Loyalty points balance and history
- Payment history / receipts
- Profile settings (name, phone, email, password)
- Dietary preferences (vegetarian, no pork, etc.) — phase 2
- Notification preferences

#### Ratings
After delivery confirmation:
- Rate the restaurant (1–5 stars)
- Rate food quality (1–5 stars)
- Rate delivery experience (1–5 stars)
- Optional text review
- Photo upload with review (phase 2)

---

### 4.2 Restaurant Dashboard Features

#### Onboarding
- Register with name, email, password
- Business details: restaurant name, address, phone, cuisine type
- Upload business license (optional at registration, required before going live)
- Phone number verification via SMS OTP
- Submit for admin approval
- Notification when approved/rejected

#### Restaurant Status (Day-to-Day Operations)
Restaurant can toggle between these states at any time:
- **Open** — accepting orders normally
- **Busy** — accepting orders but with extended wait time (auto-adds 15 min to estimate)
- **Temporarily Closed** — paused, not accepting orders (e.g., out of gas, staff issue)
- **Closed** — outside operating hours (auto-set by schedule)

#### Operating Schedule
- Set working days (Mon–Sun toggle)
- Set opening and closing times per day
- Different hours for different days
- Set holidays / special closures (specific dates)
- "Open Now" calculated automatically from schedule + status

#### Menu Management
Three onboarding methods:
1. **Manual entry** — add categories and items one by one
2. **Upload PDF/photo** — AI extracts menu items (admin reviews before publishing)
3. **CLMStore team assisted** — admin builds menu on restaurant's behalf

Menu structure:
```
Menu
└── Category (e.g., Mains)
    └── Menu Item (e.g., Fried Rice)
        ├── Base price
        ├── Photo
        ├── Description
        ├── Is Available (toggle)
        ├── Variant Groups (Choose One)
        │   └── Variants (Chicken +0, Fish +500 SLE, Shrimp +1000 SLE)
        ├── Option Groups (Choose Any — Add-Ons)
        │   └── Options (Extra Cheese +500, Extra Sauce +200)
        └── Removal Groups (Remove Ingredients)
            └── Removable Items (Onion, Tomato, Pepper)
```

#### Promotions
Restaurants can create:
- **Percentage discount** — e.g., 20% off all orders
- **Fixed amount discount** — e.g., SLE 5,000 off orders above SLE 30,000
- **BOGO** — Buy one item, get one free
- **Happy Hour** — discount active during specified time window
- **Lunch Special** — discount active between 11 AM and 2 PM
- **Free Delivery** — waive delivery fee (restaurant absorbs it)
- **Weekend Promotion** — discount active on Sat/Sun only
- **Coupon Code** — customer enters code at checkout
- Each promotion has: name, type, value, start date, end date, usage limit, per-user limit

#### Order Management
- Real-time incoming orders via WebSocket (sound alert)
- Accept / Reject pending orders
- Mark order as: Preparing → Ready for Pickup
- View order details (items with customizations, customer notes)
- Order history with search and filter
- Print receipt (optional)
- Set estimated preparation time per order

#### Employee Management
- Add employees with limited roles (view orders, mark items unavailable)
- Set employee permissions

#### Analytics & Business Insights
- Today's revenue and order count
- Revenue chart (last 7 days, 30 days, 3 months)
- Best-selling items ranked
- "Chicken Fried Rice sold 42 times today"
- Sales comparison vs previous period ("Revenue up 18% vs yesterday")
- Peak hours heatmap ("Customers order most between 12 PM and 2 PM")
- Busiest day of week
- Average preparation time
- Item-level ratings ("Your Jollof Rice is rated 4.9★")
- Cancelled order rate
- Customer retention rate (returning vs new)

#### Notifications
- New order alert (sound + push)
- Order cancelled by customer
- Customer rated order
- Weekly summary report
- Admin messages

---

### 4.3 Rider Features

#### Registration & Profile
- Register with name, phone, email
- Upload: national ID, vehicle photo (motorbike/bicycle)
- Phone verification
- Admin verification before going live
- Vehicle details

#### Availability
- Toggle "Available" / "Unavailable"
- Set working area (Freetown zones)

#### Delivery Requests
- Real-time delivery request notification (sound + push)
- Request card shows: restaurant name, customer distance, delivery fee, estimated time
- Accept or Reject within 30 seconds (auto-reject if no response)
- Only one active delivery at a time (configurable)

#### Active Delivery Flow
1. Navigate to restaurant (Google Maps / map link)
2. Arrive at restaurant → "I'm here" button
3. Pick up food → "Picked Up" button
4. Navigate to customer
5. Arrive at customer → "Delivered" button (requires PIN or photo confirmation)

#### Earnings
- Today's earnings
- Weekly/monthly earnings
- Per-delivery breakdown
- Withdrawal request (Orange Money / Afrimoney)
- Earnings history

---

### 4.4 Admin Dashboard Features

#### Restaurant Management
- List all restaurants with status filter
- Review and approve/reject applications
- View restaurant documents
- Suspend / unsuspend restaurants
- Edit commission rate per restaurant
- View restaurant analytics

#### User Management
- List all customers, riders, restaurant owners
- Suspend / activate accounts
- View user order history
- Reset passwords

#### Order Management
- View all orders across platform
- Filter by status, restaurant, date, rider
- Manually update order status (edge cases)
- Assign rider to order manually

#### Rider Management
- List all riders with verification status
- Approve / reject rider applications
- View rider earnings and delivery history
- Suspend / activate riders

#### Promotions & Coupons
- Create platform-wide coupons
- View all active restaurant promotions
- Deactivate promotions if abuse detected

#### Disputes
- View open disputes
- See order history for dispute context
- Resolve with or without refund
- Issue manual refunds

#### Commission Management
- Set default commission rate (%)
- Override per restaurant
- View commission earnings

#### Analytics
- Platform-wide revenue
- Order volume trend
- Top restaurants by revenue and orders
- Customer acquisition (new vs returning)
- Rider performance
- Average delivery time
- Cancellation rate

#### Notifications
- Broadcast message to all customers
- Broadcast to all restaurant owners
- Broadcast to all riders

---

## 5. Business Rules

### Ordering
- Customer can only order from one restaurant per cart
- Minimum order amount enforced per restaurant
- Orders auto-cancel if restaurant doesn't respond within 10 minutes
- Customer can cancel within 2 minutes of placing (before restaurant accepts)

### Delivery
- CLMStore commission: 10–15% of order subtotal (configurable per restaurant)
- Rider earns: delivery fee minus 10% platform fee
- Restaurant can choose: CLMStore riders only, own riders only, or both
- If own rider: restaurant manages delivery outside platform

### Ratings
- Customer must complete rating before placing next order (enforced via soft prompt, not hard block)
- Restaurant rating formula:
  ```
  overall = (food_quality × 0.40) + (service × 0.25) + (delivery × 0.20) + (accuracy × 0.10) + (speed × 0.05)
  ```
- Minimum 5 ratings before restaurant rating displays publicly

### Promotions
- Promotions stack: delivery discount + item discount may apply simultaneously
- Coupons cannot be combined with each other
- BOGO applies to the cheaper item being free

### Loyalty Points
- Earn 1 point per SLE 1,000 spent
- Redeem 100 points = SLE 1,000 discount
- Points expire after 12 months
- Points not earned on orders using points redemption (prevent abuse)

---

## 6. Database Schema

### Core Entities

```sql
-- Users (all roles)
users
  id, email, phone_number, password_hash, first_name, last_name,
  role (customer/restaurant_owner/restaurant_employee/rider/admin/super_admin),
  is_active, is_phone_verified, is_email_verified,
  profile_photo_url, device_token (push notifications),
  loyalty_points, created_at, updated_at

-- Addresses
user_addresses
  id, user_id, label, address_line1, address_line2,
  city, latitude, longitude, delivery_instructions, is_default

-- Businesses (generic name, configured for restaurants)
businesses (= restaurants)
  id, owner_id, name, slug, description, business_type (restaurant/grocery/pharmacy),
  store_type, cuisine_type, phone_number, email,
  address, city, latitude, longitude,
  logo_url, cover_image_url,
  status (pending_approval/approved/suspended/rejected),
  operating_status (open/busy/temp_closed/closed),
  minimum_order_amount, delivery_fee, estimated_delivery_time, estimated_prep_time,
  commission_rate, uses_clm_riders, uses_own_riders,
  avg_rating, total_ratings, is_featured,
  created_at, updated_at

-- Business documents
business_documents
  id, business_id, document_type, file_url, is_verified, verified_by, created_at

-- Operating hours
business_hours
  id, business_id, day_of_week (0=Mon, 6=Sun),
  opens_at (time), closes_at (time), is_closed

-- Business holidays
business_holidays
  id, business_id, date, reason

-- Menu categories
menu_categories
  id, business_id, name, description, display_order, is_active

-- Menu items
menu_items
  id, business_id, category_id, name, slug, description,
  base_price, photo_url, is_available, display_order,
  avg_rating, total_ratings, created_at

-- Option groups (Choose One / Choose Many)
menu_option_groups
  id, menu_item_id, name, type (single/multiple/removal),
  is_required, min_selections, max_selections, display_order

-- Options within groups
menu_options
  id, option_group_id, name, price_modifier (+ or - 0),
  is_default, is_available, display_order

-- Promotions
promotions
  id, business_id (null = platform-wide), name, description,
  type (percentage/fixed/bogo/free_delivery/happy_hour/coupon),
  discount_value, discount_type (percentage/fixed),
  min_order_amount, max_discount_amount,
  applies_to (order/item/delivery),
  applies_to_item_id (null = all items),
  coupon_code (unique, null for auto-applied),
  valid_from, valid_until,
  days_of_week (array, null = all days),
  hours_from, hours_until (happy hour),
  usage_limit, usage_count, per_user_limit,
  is_active, created_at

-- Orders
orders
  id, order_number, customer_id, business_id, rider_id,
  status (pending/accepted/preparing/ready/rider_accepted/
          rider_at_restaurant/picked_up/en_route/delivered/cancelled),
  subtotal, delivery_fee, discount_amount, coupon_id, total_amount,
  points_earned, points_redeemed,
  delivery_address_id, delivery_latitude, delivery_longitude,
  payment_method, payment_status, payment_reference,
  special_instructions, estimated_delivery_time,
  placed_at, accepted_at, ready_at, picked_up_at, delivered_at,
  cancelled_at, cancellation_reason, cancelled_by

-- Order items
order_items
  id, order_id, menu_item_id, menu_item_name,
  quantity, unit_price, total_price, special_instructions

-- Order item customizations (what options were selected)
order_item_selections
  id, order_item_id, option_group_id, option_id,
  option_name, price_modifier

-- Ratings
ratings
  id, order_id, customer_id, business_id, rider_id,
  food_quality (1-5), service (1-5), delivery_experience (1-5),
  order_accuracy (1-5), preparation_speed (1-5),
  overall_rating (computed), comment, created_at

-- Item ratings
menu_item_ratings
  id, order_item_id, menu_item_id, customer_id, rating (1-5), comment

-- Riders
riders
  id, user_id, national_id_url, vehicle_type, vehicle_photo_url,
  is_verified, is_available, current_latitude, current_longitude,
  total_deliveries, avg_rating, created_at

-- Deliveries
deliveries
  id, order_id, rider_id, status,
  pickup_latitude, pickup_longitude,
  dropoff_latitude, dropoff_longitude,
  distance_km, delivery_fee, rider_earnings,
  accepted_at, picked_up_at, delivered_at

-- Earnings
rider_earnings
  id, rider_id, delivery_id, amount, type (delivery/bonus/adjustment),
  created_at

restaurant_earnings
  id, business_id, order_id, gross_amount, commission_amount,
  net_amount, status (pending/paid), created_at

-- Withdrawals
withdrawals
  id, user_id, user_type (rider/restaurant), amount,
  payment_method, payment_details, status (pending/approved/rejected/paid),
  reference, requested_at, processed_at

-- Loyalty
loyalty_transactions
  id, user_id, order_id, type (earn/redeem/expire),
  points, balance_after, description, created_at

-- Notifications
notifications
  id, user_id, title, body, type, data (JSON), is_read, created_at

-- Disputes
disputes
  id, order_id, raised_by (user_id), reason, description,
  status (open/resolved), resolution, refund_amount,
  resolved_by, created_at, resolved_at

-- Favorites
user_favorites
  id, user_id, type (restaurant/menu_item),
  reference_id, created_at

-- Audit log
audit_logs
  id, user_id, action, entity_type, entity_id, details (JSON), created_at

-- Search index (denormalized for speed)
search_items
  id, type (restaurant/menu_item), reference_id,
  name, description, cuisine, business_name, business_id,
  tags (array), price, is_available, tsvector_column
```

---

## 7. API Endpoints

### Auth
```
POST   /auth/register
POST   /auth/login
POST   /auth/logout
POST   /auth/refresh
POST   /auth/verify-phone     (OTP)
POST   /auth/forgot-password
POST   /auth/reset-password
GET    /auth/me
```

### Restaurants (Public)
```
GET    /restaurants                    (browse + smart search)
GET    /restaurants/featured
GET    /restaurants/{slug}             (detail + hours + status)
GET    /restaurants/{id}/menu          (full menu with options)
GET    /restaurants/{id}/reviews
```

### Restaurant Dashboard
```
GET    /restaurants/my                 (own restaurant data)
PATCH  /restaurants/my                 (update profile)
PATCH  /restaurants/my/status          (open/busy/temp_closed)
GET    /restaurants/my/hours
PUT    /restaurants/my/hours           (update all hours)
POST   /restaurants/my/holidays
DELETE /restaurants/my/holidays/{id}

POST   /restaurants/my/menu/categories
PATCH  /restaurants/my/menu/categories/{id}
DELETE /restaurants/my/menu/categories/{id}
PATCH  /restaurants/my/menu/categories/{id}/reorder

POST   /restaurants/my/menu/items
PATCH  /restaurants/my/menu/items/{id}
DELETE /restaurants/my/menu/items/{id}
PATCH  /restaurants/my/menu/items/{id}/availability
POST   /restaurants/my/menu/items/{id}/option-groups
PATCH  /restaurants/my/menu/items/{id}/option-groups/{gid}
DELETE /restaurants/my/menu/items/{id}/option-groups/{gid}
POST   /restaurants/my/menu/items/{id}/option-groups/{gid}/options
PATCH  /restaurants/my/menu/items/{id}/option-groups/{gid}/options/{oid}
DELETE /restaurants/my/menu/items/{id}/option-groups/{gid}/options/{oid}

POST   /restaurants/my/promotions
PATCH  /restaurants/my/promotions/{id}
DELETE /restaurants/my/promotions/{id}

GET    /restaurants/my/orders          (incoming orders)
PATCH  /restaurants/my/orders/{id}/status

GET    /restaurants/my/analytics/overview
GET    /restaurants/my/analytics/sales
GET    /restaurants/my/analytics/items
GET    /restaurants/my/analytics/peak-hours

GET    /restaurants/my/earnings
GET    /restaurants/my/earnings/summary
POST   /restaurants/my/withdrawal

GET    /restaurants/my/employees
POST   /restaurants/my/employees
DELETE /restaurants/my/employees/{id}
```

### Orders
```
POST   /orders                         (place order)
GET    /orders                         (customer's orders)
GET    /orders/{id}
POST   /orders/{id}/cancel
POST   /orders/{id}/rate
GET    /orders/{id}/tracking
```

### Search
```
GET    /search?q=jollof+rice&type=all&cuisine=&lat=&lon=&radius=&min_price=&max_price=&sort=
```
Returns mixed results: restaurants + menu items matching query.

### Customer
```
GET    /users/me
PATCH  /users/me
GET    /users/me/addresses
POST   /users/me/addresses
PATCH  /users/me/addresses/{id}
DELETE /users/me/addresses/{id}
GET    /users/me/favorites
POST   /users/me/favorites
DELETE /users/me/favorites/{id}
GET    /users/me/loyalty
GET    /users/me/loyalty/transactions
GET    /users/me/notifications
PATCH  /users/me/notifications/{id}/read
```

### Riders
```
GET    /riders/profile
PATCH  /riders/profile
PATCH  /riders/availability
GET    /riders/deliveries/available    (available pickup requests)
POST   /riders/deliveries/{order_id}/accept
PATCH  /riders/deliveries/{id}/status
GET    /riders/earnings
GET    /riders/earnings/summary
POST   /riders/withdrawals
GET    /riders/withdrawals
```

### Payments
```
POST   /payments/initiate
POST   /payments/{id}/verify
POST   /payments/webhook/{provider}
GET    /payments/orders/{order_id}/receipt
```

### Admin
```
GET    /admin/dashboard
GET    /admin/restaurants
POST   /admin/restaurants/{id}/approve
POST   /admin/restaurants/{id}/reject
POST   /admin/restaurants/{id}/suspend
GET    /admin/users
POST   /admin/users/{id}/suspend
POST   /admin/users/{id}/activate
GET    /admin/riders
POST   /admin/riders/{id}/verify
GET    /admin/orders
GET    /admin/disputes
POST   /admin/disputes/{id}/resolve
GET    /admin/coupons
POST   /admin/coupons
DELETE /admin/coupons/{id}
GET    /admin/analytics
GET    /admin/withdrawals
POST   /admin/withdrawals/{id}/approve
POST   /admin/withdrawals/{id}/reject
POST   /admin/notifications/broadcast
```

### WebSockets
```
WS     /ws/restaurant/{restaurant_id}  (new orders, status changes)
WS     /ws/rider/{rider_id}            (new delivery requests)
WS     /ws/order/{order_id}            (customer tracking)
```

---

## 8. Design System

### Colors
```
Primary Green:    #1B8C4E
Dark Green:       #146B3A
Light Green:      #E8F5EE
Dark Navy:        #1A1A2E
White:            #FFFFFF
Light Gray:       #F8F9FA
Border Gray:      #E5E7EB
Text Primary:     #1A1A2E
Text Secondary:   #6B7280
Text Muted:       #9CA3AF
Warning Orange:   #F59E0B
Error Red:        #EF4444
Success Green:    #10B981
```

### Typography
```
Font Family:   Inter (web), SF Pro (iOS), Roboto (Android)
Heading 1:     28px / Bold / #1A1A2E
Heading 2:     22px / Bold / #1A1A2E
Heading 3:     18px / SemiBold / #1A1A2E
Body:          15px / Regular / #1A1A2E
Caption:       12px / Medium / #6B7280
Label:         11px / Bold / uppercase / #9CA3AF
```

### Components
- **Cards:** white background, 16px border-radius, 1px border (#E5E7EB), subtle shadow
- **Buttons:** 12px border-radius, 48px minimum tap target height, bold labels
- **Inputs:** 12px border-radius, 2px focus ring (#1B8C4E)
- **Chips/Tags:** 100px border-radius (pill), small padding
- **Bottom sheets:** 24px top border-radius, white, drag handle
- **Avatars:** circle, with image fallback to initials + green background

### Mobile-First Rules
- Minimum tap target: 48×48px
- Bottom navigation for primary actions (customer app)
- Floating action button for primary action on listing pages
- All modals open as bottom sheets on mobile
- Swipe to go back (native behavior)
- Skeleton loaders, not spinners, for content loading
- No horizontal scroll except for category pills and image carousels

---

## 9. Screen Inventory

### Customer Web + Mobile
```
/ (landing)             → hero, how it works, featured restaurants, app download CTA
/login                  → email/password, role hints
/register               → name, email, phone, role, password
/forgot-password
/home                   → banner, "Open Now", featured, categories grid
/restaurants            → filter/search, restaurant list
/restaurants/{slug}     → restaurant detail, menu
/restaurants/{slug}/item/{id}  → item detail with customization modal
/cart                   → items, totals, coupon input
/checkout               → address, payment, order summary
/orders                 → order history
/orders/{id}            → order detail + real-time tracking
/account                → profile overview
/account/addresses
/account/favorites
/account/loyalty
/account/notifications
/account/settings
```

### Restaurant Dashboard
```
/dashboard              → overview stats + incoming orders
/dashboard/orders       → all orders
/dashboard/menu         → categories + items + options
/dashboard/promotions   → active promotions
/dashboard/analytics    → charts + insights
/dashboard/earnings     → balance + history + withdraw
/dashboard/settings     → profile, hours, delivery config, employees
```

### Rider Interface
```
/rider                  → available deliveries
/rider/active           → current delivery detail + map
/rider/earnings         → balance + history + withdraw
/rider/account          → profile + documents + settings
```

### Admin Dashboard
```
/admin                  → overview
/admin/restaurants      → list + approve/reject
/admin/users            → customers, riders, owners
/admin/orders           → all platform orders
/admin/disputes         → open + resolved
/admin/coupons          → platform-wide coupons
/admin/analytics        → platform metrics
/admin/withdrawals      → pending + processed
/admin/notifications    → broadcast messages
```

---

## 10. Notification Events

| Event | Customer | Restaurant | Rider | Admin |
|-------|----------|------------|-------|-------|
| Order placed | ✓ | ✓ (alert) | — | — |
| Order accepted | ✓ | — | — | — |
| Order preparing | ✓ | — | — | — |
| Order ready | ✓ | — | ✓ (alert) | — |
| Rider accepted | ✓ | ✓ | — | — |
| Rider at restaurant | ✓ | ✓ | — | — |
| Food picked up | ✓ | ✓ | — | — |
| Delivered | ✓ | ✓ | — | — |
| Order cancelled | ✓ | ✓ | ✓ | — |
| Restaurant approved | — | ✓ | — | — |
| Dispute opened | — | ✓ | — | ✓ |
| Payment received | ✓ | ✓ | — | — |
| Withdrawal approved | — | ✓ | ✓ | — |

Delivery channels:
- **Push notifications** (primary — via FCM / OneSignal)
- **In-app notifications** (always)
- **SMS** (OTP, critical events — via Africa's Talking)
- **Email** (receipts, account events)

---

## 11. Payment Flow

```
Customer selects payment method at checkout
↓
POST /payments/initiate → returns provider payment URL or USSD prompt
↓
Customer completes payment on provider side
↓
Provider sends webhook → POST /payments/webhook/{provider}
↓
Backend verifies → updates order.payment_status = 'paid'
↓
Order enters fulfillment pipeline
↓
(On delivery) Restaurant earnings credited to wallet
(On delivery) Rider earnings credited to wallet
```

**Providers:**
- Orange Money Sierra Leone
- Afrimoney Sierra Leone
- Visa/Mastercard (via Flutterwave or Paystack)
- Cash on Delivery (verified by rider at drop-off)

---

## 12. Delivery Workflow

```
Order placed
↓ (auto, within 10 min)
Restaurant accepts → status: accepted
↓
Restaurant starts cooking → status: preparing
↓
Restaurant marks ready → status: ready
↓
System broadcasts to available riders
↓
Rider accepts → status: rider_accepted
↓
Rider navigates to restaurant
Rider taps "I'm at Restaurant" → status: rider_at_restaurant
↓
Rider picks up → status: picked_up
↓
Rider navigates to customer
Rider taps "Delivered" + customer confirms → status: delivered
↓
Earnings calculated and credited
↓
Rating prompt sent to customer (24h window)
```

**Auto-cancel rules:**
- Restaurant no response in 10 min → auto-cancel, customer refunded
- No rider accepts in 20 min → alert admin, attempt reassignment
- Rider accepts but doesn't pick up in 30 min → reassign

---

## 13. Gap Analysis — Current vs Required

### Backend Gaps (must build)
| Feature | Status |
|---------|--------|
| Menu option groups / variants | ❌ Missing |
| Restaurant operating status (open/busy/temp_closed) | ❌ Missing |
| Working hours CRUD | ❌ Partial |
| Holidays management | ❌ Missing |
| Promotions system | ❌ Missing |
| Smart search (food name / ingredient) | ❌ Missing |
| Customer favorites | ❌ Missing |
| Loyalty points system | ❌ Missing |
| Business insights / analytics | ❌ Partial |
| OTP phone verification | ❌ Missing |
| Order status stage granularity (9 stages) | ❌ Partial (fewer stages) |
| Broadcast notifications | ❌ Missing |
| Restaurant employee management | ❌ Partial |

### Frontend Gaps (must build)
| Page / Feature | Status |
|----------------|--------|
| Meal customization UI (bottom sheet) | ❌ Missing |
| Restaurant status controls on dashboard | ❌ Missing |
| Promotions management page | ❌ Missing |
| Smart search UI | ❌ Missing |
| Favorites page | ❌ Missing |
| Loyalty page | ❌ Missing |
| Business analytics charts | ❌ Missing |
| Real-time order tracking page | ❌ Basic only |
| Cart (recently built) | ✓ |
| All admin pages | ✓ (recently built) |
| Dashboard menu management | ✓ (recently built) |
| Dashboard settings | ✓ (recently built) |

### Already Working
| Feature | Status |
|---------|--------|
| Auth (login, register, JWT) | ✓ |
| Restaurant listing (paginated) | ✓ |
| Order placement | ✓ |
| Order status updates | ✓ |
| Admin approval workflow | ✓ |
| Rider earnings / withdrawal | ✓ |
| Restaurant earnings / withdrawal | ✓ |
| WebSocket infrastructure | ✓ |
| Push notifications (OneSignal) | ✓ |
| File uploads | ✓ |
| Pagination (fixed) | ✓ |
| Redis caching | ✓ |

---

## 14. Development Roadmap

### Phase 1 — Foundation Complete (Current)
✅ Auth, restaurants, orders, riders, admin panel, payments structure

### Phase 2 — Core Operations (Next Sprint)
Priority order:
1. Menu option groups + variants (customization) — **highest impact**
2. Restaurant operating status (Open/Busy/Closed) — **needed daily**
3. Working hours + holidays — **needed for "Open Now"**
4. Order tracking granularity (9 stages) — **customer trust**
5. Smart search by food name — **discovery**
6. Customer favorites — **retention**
7. Promotions system — **restaurant growth**

### Phase 3 — Retention & Growth
8. Loyalty points system
9. Business analytics / insights for restaurants
10. Phone OTP verification
11. Menu upload (PDF/photo + AI extraction)
12. Rating refinement (weighted formula)

### Phase 4 — Scale
13. Flutter mobile app (customer)
14. GPS-based rider tracking
15. Live map for customers
16. Advanced analytics
17. Multi-language support (Krio)

---

## 15. Success Metrics

| Metric | Target (3 months post-launch) |
|--------|-------------------------------|
| Restaurants live | 50+ |
| Daily active customers | 500+ |
| Orders per day | 200+ |
| Average order value | SLE 80,000+ |
| Order completion rate | >85% |
| Average delivery time | <45 minutes |
| Restaurant rating average | 4.0+ |
| App store rating | 4.5+ |

---

*This document is the single source of truth. All features, API changes, and UI decisions must be consistent with what is written here. Update this document before changing behavior, not after.*
