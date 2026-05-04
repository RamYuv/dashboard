# UI/UX Design Specifications
## Environment Booking & Deployment Request Screens

---

## 1. ENVIRONMENT BOOKING SCREEN

### 1.1 Overview & Purpose
Clean, intuitive screen for users to browse available environments, check availability, and create booking reservations. This is a **discovery + booking workflow**.

### 1.2 Page Layout Architecture

```
┌─────────────────────────────────────────────────────────┐
│           NAVBAR (Navigation + User Info)               │
├─────────────────────────────────────────────────────────┤
│  Page Title | Breadcrumb                                │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌───────────────────────────────────┐ │
│  │  SIDEBAR    │  │                                     │ │
│  │ Filters     │  │     MAIN CONTENT AREA              │ │
│  │ & Search    │  │  ┌─────────────────────────────┐   │ │
│  │             │  │  │  Environment Cards Grid     │   │ │
│  │             │  │  │  (3-4 columns)              │   │ │
│  │             │  │  │                             │   │ │
│  └─────────────┘  │  │ ┌────────┐ ┌────────┐      │   │ │
│                   │  │ │  Card  │ │  Card  │      │   │ │
│                   │  │ │ ENV-01 │ │ ENV-02 │      │   │ │
│                   │  │ └────────┘ └────────┘      │   │ │
│                   │  │                             │   │ │
│                   │  └─────────────────────────────┘   │ │
│                   └───────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 1.3 Components & Features

#### 1.3.1 LEFT SIDEBAR - Filters & Search
**Height:** Full viewport
**Width:** 280px (collapsible on mobile)
**Background:** Light gray (#f9fafb)

**Elements:**
```
┌─ Search Box ──────────────┐
│ 🔍 Search environment     │
│                           │
└───────────────────────────┘

┌─ ENVIRONMENT TYPE ────────┐
│ ☐ DEV     (Count: 5)      │
│ ☐ QA      (Count: 3)      │
│ ☐ STAGING (Count: 2)      │
│ ☐ PROD    (Count: 1)      │
│ ☐ Other   (Count: 0)      │
└───────────────────────────┘

┌─ STATUS ──────────────────┐
│ ○ Available (12)          │
│ ○ Partial   (2)           │
│ ○ Unavailable (0)         │
│ ○ Maintenance (0)         │
└───────────────────────────┘

┌─ FEATURES ───────────────┐
│ ☐ Deployable Only         │
│ ☐ High Capacity           │
│ ☐ Monitoring Enabled      │
└───────────────────────────┘

┌─ SORT BY ─────────────────┐
│ ○ Availability            │
│ ○ Environment ID          │
│ ○ Capacity                │
│ ○ Last Booked             │
└───────────────────────────┘

      [Reset Filters]
```

**Key Features:**
- Multi-select checkboxes with badge counts
- Real-time filtering without page reload
- Recent searches/bookmarks
- Expandable sections
- Color-coded status indicators

---

#### 1.3.2 MAIN CONTENT AREA - Environment Grid Cards

**Card Design (Responsive):**
```
┌────────────────────────────────────────────┐
│ ┌──────────────────────────────────────┐  │
│ │  STATUS BADGE (Green/Yellow/Red)     │  │
│ │                          [⋯ Actions] │  │
│ └──────────────────────────────────────┘  │
│                                            │
│  ENV-QA-01                                 │
│  QA Environment • v2.3.1                   │
│                                            │
│  📊 Capacity: 85% Used  ████████░          │
│  🗓️  Available Next: Mar 28, 2:00 PM       │
│  👥 Owner: John Smith (Team-A)             │
│  📍 Location: US-East                      │
│                                            │
│  Features:                                 │
│  • TCS, DB, MQ (3 components)              │
│  • Max Booking: 7 days                     │
│  • Deployable: Yes                         │
│                                            │
│  Quick Stats:                              │
│  Bookings This Week: 4 | Utilization: 75% │
│                                            │
│  ┌─────────────────┬───────────────────┐  │
│  │ 📅 View Calendar│ 🚀 Book Now ⟶     │  │
│  └─────────────────┴───────────────────┘  │
└────────────────────────────────────────────┘
```

**Card Variants (Status-based styling):**
- **Available:** Green accent, fully interactive
- **Partial (Limited slots):** Yellow/Orange accent, warning badge
- **Unavailable:** Grayed out, disabled buttons
- **Maintenance:** Special notice overlay, info-only mode

**Hover State:**
- Subtle elevation shadow
- Button becomes more prominent
- Quick preview tooltip on components

---

### 1.4 Booking Flow

#### Step 1: Click "Book Now" on card
Opens a modal/drawer with pre-filled environment selection

#### Step 2: Modal - Quick Booking Form
```
┌─────────────────────────────────────────────────┐
│ 📅 Book: ENV-QA-01                        [×]   │
├─────────────────────────────────────────────────┤
│                                                  │
│ BOOKING DETAILS                                 │
│ ─────────────────────────────────────────────   │
│                                                  │
│ Start Date/Time: [Mar 25 ▼] [2:00 PM ▼]         │
│ (Today available from 2:00 PM)                   │
│                                                  │
│ Duration:        [1 day ▼] or [Custom ▼]        │
│                                                  │
│ End Date/Time:   [Mar 26 ▼] [2:00 PM ▼]         │
│ (Remaining slot until March 28)                 │
│                                                  │
│ Purpose/Description:                            │
│ ┌──────────────────────────────────────────┐   │
│ │ Testing API integration...               │   │
│ └──────────────────────────────────────────┘   │
│                                                  │
│ Booking Type: ◉ Reservation ○ Deployment       │
│                                                  │
│ ☐ I need monitoring alerts                      │
│ ☐ I need deployment credentials                 │
│                                                  │
├─────────────────────────────────────────────────┤
│  Availability Check:  ✓ Slots Available         │
│  Your Limit:  7 days max | Current: 1 day      │
│                                                  │
│  [Cancel]                    [Reserve Booking] │
└─────────────────────────────────────────────────┘
```

---

### 1.5 View Options

**Option A: Grid View (Default)**
- 3-4 responsive columns
- Card-based design
- Best for browsing multiple environments

**Option B: List View**
```
ENV ID        | Type  | Status    | Owner    | Next Available | Actions
─────────────────────────────────────────────────────────────────────────
ENV-DEV-01    | DEV   | Available | Smith, J | Now            | [Book]
ENV-QA-01     | QA    | Partial   | Lee, M   | 2h             | [Book]
ENV-PROD-01   | PROD  | Unavail   | Admin    | Mar 28 2PM     | [Waitlist]
```

**Option C: Calendar View (Heat Map)**
- Timeline showing next 30 days
- Color intensity = booking frequency
- Quick visual for best booking windows

---

### 1.6 Additional Features

#### Search & Filtering Results Counter
```
Showing 8 of 14 environments  [Filters Active: 3]
```

#### Empty States
```
┌──────────────────────────────────┐
│                                  │
│         🔍 No Results Found      │
│                                  │
│  Try adjusting your filters:     │
│  • Remove status filter          │
│  • Search by different keyword   │
│  • Check 'Unavailable' option    │
│                                  │
│         [Clear All Filters]      │
└──────────────────────────────────┘
```

#### Notifications/Alerts
- "5 bookings ending today - release environments"
- "New environment available: ENV-PERF-01"
- "Your booking reminder: ENV-QA-01 expires in 2 hours"

---

## 2. DEPLOYMENT REQUEST SCREEN

### 2.1 Overview & Purpose
Dedicated, structured interface for users to **submit, track, and manage deployment requests**. This is a **form-driven + task management workflow**.

### 2.2 Page Layout Architecture

```
┌────────────────────────────────────────────────────────────┐
│              NAVBAR (Navigation + User Info)               │
├────────────────────────────────────────────────────────────┤
│  Page Title | Breadcrumb | View Toggle (List/Board)        │
├────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌────────────────────────────────┐ │
│  │   LEFT SIDEBAR   │  │    MAIN CONTENT AREA           │ │
│  │ Status Filters   │  │  ┌────────────────────────────┐│ │
│  │ Priority         │  │  │  [+ New Deployment Request]││ │
│  │ Team             │  │  └────────────────────────────┘│ │
│  │ Component Type   │  │                                 │ │
│  │ Date Range       │  │  Kanban Board View             │ │
│  │                  │  │  ┌────────┬────────┬────────┐  │ │
│  │ Quick Stats:     │  │  │ New    │Active  │Success │  │ │
│  │ • Pending: 5     │  │  │        │        │        │  │ │
│  │ • In Progress: 2 │  │  │ [Card] │ [Card] │ [Card] │  │ │
│  │ • Completed: 18  │  │  │ [Card] │ [Card] │ [Card] │  │ │
│  │ • Failed: 1      │  │  └────────┴────────┴────────┘  │ │
│  │                  │  │                                 │ │
│  └──────────────────┘  └────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

---

### 2.3 Components & Features

#### 2.3.1 Navigation Tabs (Alternatives)
```
┌─ My Deployments ─┬─ Team Deployments ─┬─ All Deployments ─┐
│                  │                     │                   │
│ Showing only     │ Shows team members' │ Shows everything  │
│ your requests    │ requests (shared)   │ if you're admin   │
└──────────────────┴─────────────────────┴───────────────────┘
```

---

#### 2.3.2 NEW DEPLOYMENT REQUEST BUTTON

**Primary CTA:**
```
┌────────────────────────────────────┐
│  🚀 + New Deployment Request       │
└────────────────────────────────────┘
```

**Trigger:** Opens multi-step form modal/drawer

---

### 2.4 Deployment Request Form (Multi-Step)

#### STEP 1: Basic Information
```
┌─────────────────────────────────────────────────────┐
│ DEPLOYMENT REQUEST - STEP 1 of 3                    │
├─────────────────────────────────────────────────────┤
│ 1. BASIC INFO        2. COMPONENTS    3. SCHEDULE  │
│ ═══════════════════                                 │
│                                                     │
│ Request Title *                                     │
│ ┌──────────────────────────────────┐               │
│ │ QA Release v2.3.1 - TCS Component │               │
│ └──────────────────────────────────┘               │
│                                                     │
│ Description *                                       │
│ ┌──────────────────────────────────┐               │
│ │ Deploy v2.3.1 to QA environment. │               │
│ │ Includes 5 bug fixes and 2 new   │               │
│ │ features.                         │               │
│ └──────────────────────────────────┘               │
│                                                     │
│ Target Environment *                                │
│ ┌─────────────────────────────────────────────────┐│
│ │ ENV-QA-01 (QA Environment • 85% Utilized)  ▼   ││
│ └─────────────────────────────────────────────────┘│
│                                                     │
│ Priority ○ Low ● Medium ○ High ○ Critical        │
│                                                     │
│ Risk Level ○ Low ◉ Medium ○ High                 │
│                                                     │
│ Assign To                                           │
│ ┌─────────────────────────────────────────────────┐│
│ │ John Smith (jsmith@company.com)            [×]  ││
│ │ Add another user...                             ││
│ └─────────────────────────────────────────────────┘│
│                                                     │
├─────────────────────────────────────────────────────┤
│ [Previous]                         [Next Step →]   │
└─────────────────────────────────────────────────────┘
```

---

#### STEP 2: Components & Configuration
```
┌─────────────────────────────────────────────────────┐
│ DEPLOYMENT REQUEST - STEP 2 of 3                    │
├─────────────────────────────────────────────────────┤
│ 1. BASIC INFO        2. COMPONENTS ✓   3. SCHEDULE│
│                      ═══════════════                │
│                                                     │
│ Components to Deploy *                              │
│                                                     │
│ ┌─ TCS Component ──────────────────────────────┐  │
│ │ ☑ Deploy this component                      │  │
│ │                                               │  │
│ │ Version: v2.3.1 (Release Notes →)             │  │
│ │ Build Artifact: tcs-2.3.1.tar.gz              │  │
│ │ Rollback Plan: [Auto-restore to v2.2.5 ▼]    │  │
│ │                                               │  │
│ │ Pre-Deployment Actions:                       │  │
│ │ ☐ Database migrations required                │  │
│ │ ☐ Configuration updates                       │  │
│ │ ☐ Health checks                               │  │
│ │                                               │  │
│ │ Post-Deployment Validation:                   │  │
│ │ ☐ Run smoke tests                             │  │
│ │ ☐ Performance benchmarks                      │  │
│ │ ☐ Integration tests                           │  │
│ └─────────────────────────────────────────────┘  │
│                                                     │
│ ┌─ DB Schema Updates ──────────────────────────┐  │
│ │ ☑ Deploy this component                      │  │
│ │                                               │  │
│ │ SQL Script: [migration_v2.3.1.sql]             │  │
│ │ Estimated Duration: 45 minutes                │  │
│ │ Rollback: [Auto-rollback script ▼]            │  │
│ │                                               │  │
│ │ Dry Run First: ☑ Recommended                 │  │
│ └─────────────────────────────────────────────┘  │
│                                                     │
│ [+ Add Component]                                   │
│                                                     │
├─────────────────────────────────────────────────────┤
│ [← Previous Step]                   [Next Step →]  │
└─────────────────────────────────────────────────────┘
```

---

#### STEP 3: Deployment Schedule & Approval
```
┌─────────────────────────────────────────────────────┐
│ DEPLOYMENT REQUEST - STEP 3 of 3                    │
├─────────────────────────────────────────────────────┤
│ 1. BASIC INFO        2. COMPONENTS    3. SCHEDULE ✓│
│                                        ════════════ │
│                                                     │
│ DEPLOYMENT SCHEDULE                                 │
│ ─────────────────────────────────────────────────   │
│                                                     │
│ Deployment Window *                                 │
│ ○ Immediate                                         │
│ ◉ Scheduled                                         │
│ ○ Manual (Only deploy when approved)               │
│                                                     │
│ Preferred Date: [Mar 28 ▼]                          │
│ Preferred Time: [02:00 PM ▼] (Maintenance window) │
│ Estimated Duration: 60 minutes                      │
│                                                     │
│ Maintenance Mode:                                   │
│ ☑ Enable maintenance page during deployment        │
│ ☑ Notify users before deployment (15 min warning)  │
│ ☑ Auto-revert on failure                           │
│                                                     │
│ APPROVAL                                            │
│ ─────────────────────────────────────────────────   │
│                                                     │
│ Required Approvers:                                 │
│ ☐ Tech Lead (Assigned: Pending)                    │
│ ☐ QA Manager (Assigned: Pending)                   │
│ ☐ DevOps Lead (Assigned: Pending)                  │
│                                                     │
│ Additional Notes for Approvers:                     │
│ ┌──────────────────────────────────┐               │
│ │ This is a standard release with   │               │
│ │ no database changes or schema     │               │
│ │ alterations.                      │               │
│ └──────────────────────────────────┘               │
│                                                     │
│ Notifications:                                      │
│ ☑ Email me when approved                           │
│ ☑ Email me on deployment start                     │
│ ☑ Email me on deployment completion                │
│                                                     │
├─────────────────────────────────────────────────────┤
│ [← Previous Step]      [Cancel] [Submit Request] ✓ │
│                       (Awaiting approval)           │
└─────────────────────────────────────────────────────┘
```

---

### 2.5 Deployment Board/List View

#### Kanban Board (Drag-and-drop status flow)
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│   PENDING   │  SCHEDULED  │  DEPLOYING  │  COMPLETED  │
│   (5)       │     (2)     │     (0)     │    (18)     │
├─────────────┼─────────────┼─────────────┼─────────────┤
│             │             │             │             │
│ ┌─────────┐ │ ┌─────────┐ │             │ ┌─────────┐ │
│ │ QA v2.3 │ │ │ QA v2.2 │ │             │ │ QA v2.1 │ │
│ │ TCS+DB  │ │ │ DB Only │ │             │ │ Full    │ │
│ │         │ │ │         │ │             │ │         │ │
│ │ ⚠ High  │ │ │ 🔵 Med  │ │             │ │ ✓       │ │
│ │ Awaiting │ │ │ Mar 28  │ │             │ │ Deployed│ │
│ │ approval │ │ │ 02:00PM │ │             │ │ Mar 24  │ │
│ └─────────┘ │ └─────────┘ │             │ └─────────┘ │
│             │             │             │             │
│ ┌─────────┐ │             │             │ ┌─────────┐ │
│ │ PROD    │ │             │             │ │ STAGING │ │
│ │ v1.9.8  │ │             │             │ │ v2.3.0  │ │
│ │ MQ Only │ │             │             │ │ All     │ │
│ │ 🟠 Low  │ │             │             │ │ ✓       │ │
│ │ For Dev │ │             │             │ │ Deployed│ │
│ │ review  │ │             │             │ │ Mar 23  │ │
│ └─────────┘ │             │             │ └─────────┘ │
│             │             │             │             │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

---

#### Table View (Detailed list)
```
REQUEST ID | TITLE          | ENV    | COMPONENTS | STATUS    | PRIORITY | WINDOW      | OWNER
──────────────────────────────────────────────────────────────────────────────────────────────
DR-001     | QA v2.3.1 TCS  | QA-01  | TCS, DB    | Pending   | 🔴 High  | Mar 28 2PM  | Smith
DR-002     | PROD Hotfix    | PROD   | TCS        | Scheduled | 🟢 Low   | Apr 1 1AM   | Lee
DR-003     | STAGING v2.2   | STG-01 | All        | Completed | 🔵 Med   | Mar 25      | Jones
```

---

### 2.6 Deployment Request Detail View

**When clicking on a request:**
```
┌─────────────────────────────────────────────────────────┐
│ DR-001: QA Release v2.3.1 - TCS Component    [Edit][×]  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ STATUS: 🔵 PENDING APPROVAL                             │
│                                                          │
│ TIMELINE:                                                │
│ Created: Mar 24, 10:30 AM by John Smith                 │
│ Approved: ─ (Awaiting approvers)                        │
│ Scheduled: Mar 28, 2:00 PM                              │
│ Deployed: ─                                              │
│                                                          │
├─ BASIC INFO ───────────────────────────────────────────┤
│ Title: QA Release v2.3.1 - TCS Component               │
│ Description: Deploy v2.3.1 to QA environment...        │
│ Environment: ENV-QA-01 (QA • 85% utilized)             │
│ Priority: High | Risk: Medium                           │
│ Owner: John Smith | Assigned to: John Smith            │
│                                                          │
├─ COMPONENTS ───────────────────────────────────────────┤
│ ✓ TCS v2.3.1 | Rollback: Auto v2.2.5                   │
│ ✓ DB Schema  | Rollback: Auto script                   │
│                                                          │
├─ APPROVALS ────────────────────────────────────────────┤
│ ☐ Tech Lead (Pending) — Send reminder                  │
│ ☐ QA Manager (Pending) — Send reminder                 │
│ ☐ DevOps Lead (Pending) — Send reminder                │
│                                                          │
├─ ACTIVITY LOG ──────────────────────────────────────────┤
│ 10:30 AM | John Smith created request                  │
│  10:35 AM | Email sent to approvers                    │
│  (No updates yet)                                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

### 2.7 Key UX Features

#### Real-time Status Indicators
```
Status Legend:
● DRAFT           (Form in progress, not submitted)
● PENDING         (Awaiting approval)
● SCHEDULED       (Approved, waiting for deployment window)
● DEPLOYING       (Deployment in progress, live updates)
● COMPLETED       (Successfully deployed)
● FAILED          (Deployment failed, review logs)
● CANCELLED       (Request cancelled by user/admin)
● ROLLBACK        (Active rollback in progress)
```

#### Approval Workflow Visualization
```
Submitter → Tech Lead → QA Manager → DevOps Lead → Deploy
   ✓            ⏳           ⏳           ⏳          -
```

#### Live Deployment Monitoring (When deploying)
```
┌─────────────────────────────────────┐
│ DEPLOYMENT IN PROGRESS              │
│                                     │
│ [████████░░░░░░░░░] 45% Complete   │
│                                     │
│ Step 1: Pre-checks ................✓│
│ Step 2: Database migration ........⏳│
│ Step 3: Service deployment .........○│
│ Step 4: Health checks ..............○│
│ Step 5: Rollback prepared ...........○│
│                                     │
│ Logs: [View Real-time Logs]        │
│                                     │
│ Est. Remaining: 15 minutes         │
└─────────────────────────────────────┘
```

---

## 3. DESIGN SYSTEM & STYLING GUIDELINES

### 3.1 Color Scheme
```
Primary:     #2563eb (Blue - Actions, Links)
Success:     #059669 (Green - Available, Deployed)
Warning:     #f59e0b (Orange - Caution, Partial)
Danger:      #dc2626 (Red - Errors, Unavailable)
Gray-50:     #f9fafb (Lightest background)
Gray-100:    #f3f4f6 (Light background)
Gray-200:    #e5e7eb (Borders)
Gray-600:    #4b5563 (Secondary text)
Gray-900:    #111827 (Dark text)
```

### 3.2 Status Badge Colors
| Status      | Background | Text     | Icon |
|-------------|-----------|----------|------|
| Available   | #e0fdf4    | #059669  | ✓    |
| Partial     | #fef3c7    | #d97706  | ⚠    |
| Unavailable | #f3f4f6    | #4b5563  | ✕    |
| Deploying   | #dbeafe    | #2563eb  | ⟳    |
| Failed      | #fee2e2    | #dc2626  | ✕    |

### 3.3 Typography
- **Headers (h1):** 28px, Font-weight: 700, Color: #111827
- **Subheaders (h2):** 22px, Font-weight: 600, Color: #111827
- **Card Titles:** 16px, Font-weight: 600, Color: #111827
- **Body Text:** 14px, Font-weight: 400, Color: #4b5563
- **Labels:** 12px, Font-weight: 500, Color: #4b5563

### 3.4 Spacing & Borders
- Padding (Large): 24px | (Medium): 16px | (Small): 8px
- Border Radius: 12px (cards), 8px (inputs), 6px (buttons)
- Shadows: See booking calendar view CSS variables
- Gap between cards: 20px

### 3.5 Responsive Breakpoints
- **Desktop:** 1200px+ (3-4 columns)
- **Tablet:** 768px-1199px (2-3 columns)
- **Mobile:** <768px (1 column, full-width)

---

## 4. NAVIGATION STRUCTURE

### 4.1 Updated Navbar Links
```
Home | Dashboard | Health | Booking | Deployment Requests | Admin (if role) | Logout
```

### 4.2 Breadcrumb Navigation Examples
```
Booking Screen: Home / Environments / Booking
Deployment Screen: Home / Operations / Deployment Requests
Detail View: Home / Operations / Deployment Requests / DR-001
```

---

## 5. ACCESSIBILITY CONSIDERATIONS

1. **WCAG 2.1 Level AA Compliance**
   - Color contrast ratios ≥ 4.5:1
   - Keyboard navigation support
   - ARIA labels for interactive elements
   - Focus indicators visible

2. **Semantic HTML**
   - Use proper heading hierarchy (h1 → h2 → h3)
   - Semantic form labels and fieldsets
   - Buttons vs links distinction

3. **Alt Text & Descriptions**
   - Icons with `aria-label` attributes
   - Status badges with descriptive text
   - Charts/graphs with data tables

---

## 6. PROGRESSIVE ENHANCEMENT

1. **Without JavaScript:**
   - Form submission works
   - Filters via traditional form controls
   - Links navigate properly

2. **With JavaScript:**
   - Real-time filtering (no page reload)
   - Drag-and-drop Kanban board
   - Live status updates
   - Rich validations

---

## 7. IMPLEMENTATION PRIORITIES

### Phase 1 (MVP)
- [ ] Environment Booking Screen (Grid + Filters)
- [ ] Quick Book Modal
- [ ] Basic filtering & search
- [ ] Responsive design

### Phase 2
- [ ] Deployment Request Screen (Form + List)
- [ ] Multi-step deployment form
- [ ] Approval workflow visualization
- [ ] Real-time status updates

### Phase 3 (Enhancement)
- [ ] Calendar heat map view
- [ ] Kanban board with drag-drop
- [ ] Live deployment monitoring
- [ ] Advanced analytics

---

## 8. DATA ATTRIBUTES FOR TEMPLATES

```python
# For Environment Cards
environment = {
    'env_id': 'ENV-QA-01',
    'env_type': 'QA',
    'status': 'available',  # available, partial, unavailable, maintenance
    'capacity_used': 85,
    'owner': 'John Smith',
    'team': 'Team-A',
    'location': 'US-East',
    'components': ['TCS', 'DB', 'MQ'],
    'deployable': True,
    'next_available': '2026-03-28T14:00:00Z',
    'bookings_this_week': 4,
    'utilization': 75
}

# For Deployment Requests
deployment = {
    'dr_id': 'DR-001',
    'title': 'QA Release v2.3.1',
    'env_id': 'ENV-QA-01',
    'components': ['TCS', 'DB'],
    'status': 'pending',  # draft, pending, scheduled, deploying, completed, failed
    'priority': 'high',   # low, medium, high, critical
    'risk_level': 'medium',
    'owner': 'john.smith@company.com',
    'created_at': '2026-03-24T10:30:00Z',
    'scheduled_window': '2026-03-28T14:00:00Z',
    'approvals': {
        'tech_lead': 'pending',
        'qa_manager': 'pending',
        'devops_lead': 'pending'
    }
}
```

