# Implementation Guide: Screens & Components

---

## 1. ENVIRONMENT BOOKING SCREEN - IMPLEMENTATION

### 1.1 File Structure
```
webapp/
├── templates/
│   ├── booking_new.html           (Main booking page - NEW)
│   ├── components/
│   │   ├── env_filter_sidebar.html (Reusable sidebar filter)
│   │   ├── env_card.html           (Reusable environment card)
│   │   └── booking_modal.html      (Reusable booking form modal)
│
├── static/
│   ├── css/
│   │   ├── booking-new.css        (NEW - Booking page styles)
│   │   └── components.css         (NEW - Reusable component styles)
│   │
│   ├── js/
│   │   ├── booking-new.js         (NEW - Main booking logic)
│   │   ├── filters.js             (NEW - Filter/search logic)
│   │   └── booking-modal.js       (NEW - Modal interactions)
│
└── routes/
    └── booking.py                  (EXISTING - Add new endpoints)
```

### 1.2 New Routes Required (Flask)
```python
# In booking.py

@booking.route('/environments', methods=['GET'])
def get_environments():
    """
    GET /environments?type=QA&status=available&search=DEV
    Returns filtered list of environments
    """
    pass

@booking.route('/environment/<env_id>/availability', methods=['GET'])
def get_availability(env_id):
    """
    GET /environment/ENV-QA-01/availability?date=2026-03-28
    Returns available slots for specific environment
    """
    pass

@booking.route('/book', methods=['POST'])
def create_booking():
    """
    POST /book
    {
        'env_id': 'ENV-QA-01',
        'start_time': '2026-03-25T14:00:00Z',
        'end_time': '2026-03-26T14:00:00Z',
        'booking_type': 'RESERVATION',
        'description': 'API testing'
    }
    """
    pass
```

### 1.3 HTML Component Example - Environment Card
```html
<!-- templates/components/env_card.html -->
<div class="env-card env-card--{{ environment.status }}" 
     data-env-id="{{ environment.env_id }}"
     data-env-type="{{ environment.env_type }}">
  
  <!-- Status Badge -->
  <div class="env-card__header">
    <span class="status-badge status-badge--{{ environment.status }}">
      {% if environment.status == 'available' %}
        ✓ Available Now
      {% elif environment.status == 'partial' %}
        ⚠ Limited Slots
      {% else %}
        ✕ Unavailable
      {% endif %}
    </span>
    <button class="env-card__menu" type="button" aria-label="Options">
      ⋯
    </button>
  </div>

  <!-- Environment Title & Details -->
  <div class="env-card__content">
    <h3 class="env-card__title">{{ environment.env_id }}</h3>
    <p class="env-card__subtitle">
      {{ environment.env_type }} Environment • v{{ environment.version }}
    </p>

    <!-- Capacity Indicator -->
    <div class="env-card__metric">
      <span class="metric-label">📊 Capacity:</span>
      <div class="progress" role="progressbar" 
           aria-valuenow="{{ environment.capacity_used }}" 
           aria-valuemin="0" 
           aria-valuemax="100">
        <div class="progress-bar" 
             style="width: {{ environment.capacity_used }}%"></div>
      </div>
      <span class="metric-value">{{ environment.capacity_used }}%</span>
    </div>

    <!-- Next Available -->
    <div class="env-card__metric">
      <span class="metric-label">🗓️ Available Next:</span>
      <span class="metric-value">
        {% if environment.status == 'available' %}
          Now
        {% else %}
          {{ environment.next_available | format_datetime }}
        {% endif %}
      </span>
    </div>

    <!-- Owner Info -->
    <div class="env-card__metric">
      <span class="metric-label">👥 Owner:</span>
      <span class="metric-value">{{ environment.owner }} ({{ environment.team }})</span>
    </div>

    <!-- Location -->
    <div class="env-card__metric">
      <span class="metric-label">📍 Location:</span>
      <span class="metric-value">{{ environment.location }}</span>
    </div>

    <!-- Features List -->
    <div class="env-card__features">
      <h4 class="features-label">Features:</h4>
      <ul class="features-list">
        <li>{{ environment.components | join(', ') }} ({{ environment.components | length }} components)</li>
        <li>Max Booking: 7 days</li>
        <li>Deployable: {% if environment.deployable %}Yes{% else %}No{% endif %}</li>
      </ul>
    </div>

    <!-- Quick Stats -->
    <div class="env-card__stats">
      <div class="stat">
        <span class="stat-label">Bookings This Week</span>
        <span class="stat-value">{{ environment.bookings_this_week }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Utilization</span>
        <span class="stat-value">{{ environment.utilization }}%</span>
      </div>
    </div>
  </div>

  <!-- Action Buttons -->
  <div class="env-card__actions">
    <button class="btn btn-secondary btn-sm" 
            data-action="view-calendar"
            data-env-id="{{ environment.env_id }}">
      📅 View Calendar
    </button>
    <button class="btn btn-primary btn-sm" 
            data-action="book-now"
            data-env-id="{{ environment.env_id }}"
            {% if environment.status == 'unavailable' %}disabled{% endif %}>
      🚀 Book Now →
    </button>
  </div>
</div>
```

### 1.4 CSS Styling - Environment Card
```css
/* static/css/components.css */

.env-card {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
  transition: all 0.3s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  padding: 20px;
  gap: 16px;
}

.env-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
  border-color: #2563eb;
}

/* Status variants */
.env-card--unavailable {
  opacity: 0.6;
  pointer-events: none;
}

.env-card--partial {
  border-left: 4px solid #f59e0b;
}

.env-card--available {
  border-left: 4px solid #059669;
}

/* Header */
.env-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge--available {
  background: #e0fdf4;
  color: #059669;
}

.status-badge--partial {
  background: #fef3c7;
  color: #d97706;
}

.status-badge--unavailable {
  background: #f3f4f6;
  color: #4b5563;
}

/* Content */
.env-card__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.env-card__subtitle {
  margin: 4px 0 0 0;
  font-size: 13px;
  color: #6b7280;
}

/* Metrics */
.env-card__metric {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #4b5563;
}

.metric-label {
  font-weight: 500;
}

.metric-value {
  color: #111827;
  font-weight: 500;
}

/* Progress bar */
.progress {
  flex: 1;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #1d4ed8);
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* Features */
.env-card__features {
  margin: 8px 0;
}

.features-label {
  margin: 0 0 6px 0;
  font-size: 12px;
  font-weight: 600;
  color: #4b5563;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.features-list {
  margin: 0;
  padding-left: 16px;
  list-style: none;
}

.features-list li {
  font-size: 13px;
  color: #4b5563;
  margin: 2px 0;
}

/* Stats */
.env-card__stats {
  display: flex;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid #e5e7eb;
}

.stat {
  flex: 1;
  text-align: center;
}

.stat-label {
  display: block;
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
  margin-bottom: 2px;
}

.stat-value {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #2563eb;
}

/* Actions */
.env-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.env-card__actions .btn {
  flex: 1;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.env-card__actions .btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

/* Responsive */
@media (max-width: 768px) {
  .env-card {
    padding: 16px;
    gap: 12px;
  }

  .env-card__metric {
    flex-wrap: wrap;
  }

  .env-card__actions {
    flex-direction: column;
  }
}
```

### 1.5 JavaScript Logic - Booking
```javascript
// static/js/booking-new.js

class BookingManager {
  constructor() {
    this.environments = [];
    this.filters = {
      type: [],
      status: [],
      features: [],
      sortBy: 'availability'
    };
    this.init();
  }

  init() {
    this.loadEnvironments();
    this.setupEventListeners();
    this.setupFilters();
  }

  // Load environments from API
  async loadEnvironments() {
    try {
      const params = new URLSearchParams(this.filters);
      const response = await fetch(`/environments?${params}`);
      this.environments = await response.json();
      this.render();
    } catch (error) {
      console.error('Failed to load environments:', error);
      this.showErrorMessage('Failed to load environments');
    }
  }

  // Setup filter event listeners
  setupFilters() {
    // Type filters
    document.querySelectorAll('[data-filter="type"]').forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        if (e.target.checked) {
          this.filters.type.push(e.target.value);
        } else {
          this.filters.type = this.filters.type.filter(t => t !== e.target.value);
        }
        this.loadEnvironments();
      });
    });

    // Status filters
    document.querySelectorAll('[data-filter="status"]').forEach(radio => {
      radio.addEventListener('change', (e) => {
        if (e.target.checked) {
          this.filters.status = [e.target.value];
          this.loadEnvironments();
        }
      });
    });

    // Search
    const searchInput = document.querySelector('[data-action="search"]');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
          this.filters.search = e.target.value;
          this.loadEnvironments();
        }, 300);
      });
    }
  }

  // Render grid
  render() {
    const grid = document.querySelector('[data-container="env-grid"]');
    grid.innerHTML = this.environments.map(env => this.createCardHTML(env)).join('');
    
    // Re-attach event listeners to new cards
    this.setupCardListeners();
  }

  // Create card HTML
  createCardHTML(env) {
    return `
      <div class="env-card env-card--${env.status}" data-env-id="${env.env_id}">
        <!-- Card content -->
      </div>
    `;
  }

  // Setup card-level interactions
  setupCardListeners() {
    document.querySelectorAll('[data-action="book-now"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const envId = e.target.dataset.envId;
        this.openBookingModal(envId);
      });
    });

    document.querySelectorAll('[data-action="view-calendar"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const envId = e.target.dataset.envId;
        this.openCalendarView(envId);
      });
    });
  }

  // Open booking modal
  openBookingModal(envId) {
    const env = this.environments.find(e => e.env_id === envId);
    const modal = new BookingModal(env);
    modal.open();
  }

  // Show error
  showErrorMessage(message) {
    const container = document.querySelector('[data-container="message"]');
    container.innerHTML = `
      <div class="alert alert-danger alert-dismissible fade show">
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      </div>
    `;
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  new BookingManager();
});
```

---

## 2. DEPLOYMENT REQUEST SCREEN - IMPLEMENTATION

### 2.1 File Structure
```
webapp/
├── templates/
│   ├── deployment_request.html        (Main deployment page - NEW)
│   ├── components/
│   │   ├── deployment_form_step1.html (Step 1: Basic info)
│   │   ├── deployment_form_step2.html (Step 2: Components)
│   │   ├── deployment_form_step3.html (Step 3: Schedule)
│   │   ├── deployment_card.html       (Reusable deployment card)
│   │   └── approval_flow.html         (Approval visualization)
│
├── static/
│   ├── css/
│   │   ├── deployment.css             (NEW - Deployment styles)
│   │
│   ├── js/
│   │   ├── deployment-form.js         (NEW - Multi-step form)
│   │   ├── deployment-board.js        (NEW - Kanban board)
│   │   └── deployment-live.js         (NEW - Live monitoring)
│
└── routes/
    └── deployment.py                  (NEW - Deployment endpoints)
```

### 2.2 New Routes Required
```python
# routes/deployment.py (NEW FILE)

from flask import Blueprint, request, jsonify

deployment = Blueprint('deployment', __name__, url_prefix='/deployment')

@deployment.route('/requests', methods=['GET'])
def get_requests():
    """GET /deployment/requests?status=pending&view=my"""
    pass

@deployment.route('/request', methods=['POST'])
def create_request():
    """
    POST /deployment/request
    {
        'title': 'QA Release v2.3.1',
        'description': '...',
        'env_id': 'ENV-QA-01',
        'components': [...],
        'priority': 'high',
        'schedule_window': '2026-03-28T14:00:00Z'
    }
    """
    pass

@deployment.route('/request/<dr_id>', methods=['GET'])
def get_request(dr_id):
    """GET /deployment/request/DR-001"""
    pass

@deployment.route('/request/<dr_id>/approve', methods=['POST'])
def approve_request(dr_id):
    """POST /deployment/request/DR-001/approve"""
    pass

@deployment.route('/request/<dr_id>/deploy', methods=['POST'])
def deploy_request(dr_id):
    """POST /deployment/request/DR-001/deploy"""
    pass

@deployment.route('/request/<dr_id>/status', methods=['GET'])
def get_deployment_status(dr_id):
    """GET /deployment/request/DR-001/status (WebSocket for live updates)"""
    pass
```

### 2.3 HTML - Multi-Step Form
```html
<!-- templates/components/deployment_form_step1.html -->

<form id="deploymentForm" class="deployment-form">
  <!-- Progress Indicator -->
  <div class="form-progress">
    <div class="progress-item active">
      <span class="progress-number">1</span>
      <span class="progress-label">Basic Info</span>
    </div>
    <div class="progress-line"></div>
    <div class="progress-item">
      <span class="progress-number">2</span>
      <span class="progress-label">Components</span>
    </div>
    <div class="progress-line"></div>
    <div class="progress-item">
      <span class="progress-number">3</span>
      <span class="progress-label">Schedule</span>
    </div>
  </div>

  <!-- Step 1: Basic Information -->
  <div class="form-step form-step--active" data-step="1">
    <div class="step-title">
      <h3>Basic Information</h3>
      <p>Provide core details about your deployment request</p>
    </div>

    <!-- Request Title -->
    <div class="form-group">
      <label for="requestTitle" class="form-label">
        Request Title <span class="required">*</span>
      </label>
      <input 
        type="text" 
        id="requestTitle" 
        class="form-control" 
        placeholder="e.g., QA Release v2.3.1 - TCS Component"
        required
        minlength="5"
        maxlength="100"
      >
      <small class="form-text text-muted">Brief, descriptive title for your deployment</small>
    </div>

    <!-- Description -->
    <div class="form-group">
      <label for="requestDesc" class="form-label">
        Description <span class="required">*</span>
      </label>
      <textarea 
        id="requestDesc" 
        class="form-control" 
        rows="4"
        placeholder="Describe what is being deployed and why..."
        required
        minlength="10"
        maxlength="1000"
      ></textarea>
      <small class="form-text text-muted">Character count: <span id="descCount">0</span>/1000</small>
    </div>

    <!-- Target Environment -->
    <div class="form-group">
      <label for="targetEnv" class="form-label">
        Target Environment <span class="required">*</span>
      </label>
      <select id="targetEnv" class="form-control" required>
        <option value="">Select environment...</option>
        {% for env in environments %}
          <option value="{{ env.env_id }}" data-type="{{ env.env_type }}">
            {{ env.env_id }} ({{ env.env_type }} • {{ env.capacity_used }}% utilized)
          </option>
        {% endfor %}
      </select>
      <small class="form-text text-muted">Choose the target environment</small>
    </div>

    <!-- Priority -->
    <div class="form-group">
      <label class="form-label">Priority <span class="required">*</span></label>
      <div class="radio-group">
        <label class="radio-label">
          <input type="radio" name="priority" value="low" checked>
          <span class="radio-badge badge-low">🟢 Low</span>
          <span class="radio-desc">Minor updates, no time pressure</span>
        </label>
        <label class="radio-label">
          <input type="radio" name="priority" value="medium">
          <span class="radio-badge badge-medium">🔵 Medium</span>
          <span class="radio-desc">Standard deployment, normal priority</span>
        </label>
        <label class="radio-label">
          <input type="radio" name="priority" value="high">
          <span class="radio-badge badge-high">🟠 High</span>
          <span class="radio-desc">Important update, elevated priority</span>
        </label>
        <label class="radio-label">
          <input type="radio" name="priority" value="critical">
          <span class="radio-badge badge-critical">🔴 Critical</span>
          <span class="radio-desc">Urgent hotfix, needs immediate attention</span>
        </label>
      </div>
    </div>

    <!-- Risk Level -->
    <div class="form-group">
      <label class="form-label">Risk Level <span class="required">*</span></label>
      <div class="radio-group">
        <label class="radio-label">
          <input type="radio" name="riskLevel" value="low">
          <span class="risk-badge">🟢 Low Risk</span>
          <span class="radio-desc">Minimal impact, well-tested changes</span>
        </label>
        <label class="radio-label">
          <input type="radio" name="riskLevel" value="medium" checked>
          <span class="risk-badge">🟡 Medium Risk</span>
          <span class="radio-desc">Standard deployment, normal impact</span>
        </label>
        <label class="radio-label">
          <input type="radio" name="riskLevel" value="high">
          <span class="risk-badge">🔴 High Risk</span>
          <span class="radio-desc">Complex changes, significant impact</span>
        </label>
      </div>
    </div>

    <!-- Assignee -->
    <div class="form-group">
      <label for="assignee" class="form-label">Assign To</label>
      <select id="assignee" class="form-control" multiple>
        <option value="">Select team members...</option>
        {% for user in team_members %}
          <option value="{{ user.user_id }}">{{ user.name }} ({{ user.role }})</option>
        {% endfor %}
      </select>
      <small class="form-text text-muted">Optional: Assign to specific team members</small>
    </div>
  </div>

  <!-- Navigation -->
  <div class="form-navigation">
    <button type="button" class="btn btn-secondary" data-action="prev-step" disabled>
      ← Previous
    </button>
    <button type="button" class="btn btn-primary" data-action="next-step">
      Next Step →
    </button>
  </div>
</form>
```

### 2.4 CSS - Deployment Form
```css
/* static/css/deployment.css */

.deployment-form {
  background: white;
  border-radius: 12px;
  padding: 32px;
  max-width: 700px;
}

/* Progress Indicator */
.form-progress {
  display: flex;
  align-items: center;
  margin-bottom: 40px;
  gap: 12px;
}

.progress-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  opacity: 0.5;
  transition: opacity 0.3s ease;
}

.progress-item.active {
  opacity: 1;
}

.progress-number {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #e5e7eb;
  font-weight: 600;
  color: #4b5563;
  border: 2px solid transparent;
  transition: all 0.3s ease;
}

.progress-item.active .progress-number {
  background: #2563eb;
  color: white;
  border-color: #1d4ed8;
}

.progress-item.completed .progress-number {
  background: #059669;
  color: white;
  content: '✓';
}

.progress-label {
  font-size: 12px;
  font-weight: 500;
  color: #4b5563;
  text-align: center;
  min-width: 60px;
}

.progress-line {
  flex: 1;
  height: 2px;
  background: #e5e7eb;
  max-width: 60px;
  margin: 0 12px;
}

.progress-item.completed ~ .progress-line {
  background: #059669;
}

/* Form Steps */
.form-step {
  display: none;
}

.form-step.form-step--active {
  display: block;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.step-title {
  margin-bottom: 28px;
}

.step-title h3 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
  color: #111827;
}

.step-title p {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
}

/* Form Groups */
.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #111827;
  font-size: 14px;
}

.required {
  color: #dc2626;
}

.form-control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  transition: all 0.2s ease;
}

.form-control:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.form-control:invalid {
  border-color: #dc2626;
}

/* Radio/Checkbox Groups */
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.radio-label {
  display: flex;
  gap: 12px;
  padding: 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.radio-label:hover {
  border-color: #9ca3af;
  background: #f9fafb;
}

.radio-label input[type="radio"] {
  margin: 2px 0 0 0;
  cursor: pointer;
  width: 18px;
  height: 18px;
}

.radio-label input[type="radio"]:checked ~ .radio-badge {
  font-weight: 600;
}

.radio-badge {
  font-weight: 500;
  white-space: nowrap;
}

.badge-low { color: #059669; }
.badge-medium { color: #2563eb; }
.badge-high { color: #f59e0b; }
.badge-critical { color: #dc2626; }

.radio-desc {
  font-size: 13px;
  color: #6b7280;
  flex-shrink: 0;
}

/* Form Navigation */
.form-navigation {
  display: flex;
  gap: 12px;
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
}

.btn {
  padding: 10px 16px;
  border-radius: 8px;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.btn-primary {
  background: #2563eb;
  color: white;
  margin-left: auto;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: #e5e7eb;
  color: #111827;
}

.btn-secondary:hover:not(:disabled) {
  background: #d1d5db;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Responsive */
@media (max-width: 768px) {
  .deployment-form {
    padding: 20px;
  }

  .form-progress {
    flex-wrap: wrap;
    margin-bottom: 24px;
  }

  .progress-line {
    max-width: 40px;
  }
}
```

### 2.5 JavaScript - Multi-Step Form
```javascript
// static/js/deployment-form.js

class DeploymentFormManager {
  constructor() {
    this.currentStep = 1;
    this.totalSteps = 3;
    this.formData = {};
    this.init();
  }

  init() {
    this.setupEventListeners();
    this.validateStep(1);
  }

  setupEventListeners() {
    const form = document.getElementById('deploymentForm');

    // Next button
    document.querySelector('[data-action="next-step"]').addEventListener('click', () => {
      if (this.validateStep(this.currentStep)) {
        this.collectFormData();
        this.nextStep();
      }
    });

    // Previous button
    document.querySelector('[data-action="prev-step"]').addEventListener('click', () => {
      this.previousStep();
    });

    // Form input tracking
    form.querySelectorAll('input, textarea, select').forEach(input => {
      input.addEventListener('change', () => this.validateStep(this.currentStep));
      input.addEventListener('blur', () => this.validateStep(this.currentStep));
    });
  }

  nextStep() {
    if (this.currentStep < this.totalSteps) {
      this.showStep(this.currentStep + 1);
      this.currentStep++;
      this.updateProgress();
    }
  }

  previousStep() {
    if (this.currentStep > 1) {
      this.showStep(this.currentStep - 1);
      this.currentStep--;
      this.updateProgress();
    }
  }

  showStep(stepNumber) {
    document.querySelectorAll('.form-step').forEach(step => {
      step.classList.remove('form-step--active');
    });
    document.querySelector(`[data-step="${stepNumber}"]`).classList.add('form-step--active');
  }

  updateProgress() {
    const items = document.querySelectorAll('.progress-item');
    items.forEach((item, index) => {
      item.classList.remove('active', 'completed');
      if (index + 1 < this.currentStep) {
        item.classList.add('completed');
      } else if (index + 1 === this.currentStep) {
        item.classList.add('active');
      }
    });

    // Update button states
    document.querySelector('[data-action="prev-step"]').disabled = this.currentStep === 1;
    document.querySelector('[data-action="next-step"]').disabled = this.currentStep === this.totalSteps;
  }

  validateStep(step) {
    const stepElement = document.querySelector(`[data-step="${step}"]`);
    const inputs = stepElement.querySelectorAll('input[required], textarea[required], select[required]');
    
    let isValid = true;
    inputs.forEach(input => {
      if (!input.value.trim()) {
        isValid = false;
        input.classList.add('is-invalid');
      } else {
        input.classList.remove('is-invalid');
      }
    });

    return isValid;
  }

  collectFormData() {
    const stepElement = document.querySelector(`[data-step="${this.currentStep}"]`);
    const inputs = stepElement.querySelectorAll('input, textarea, select');
    
    inputs.forEach(input => {
      if (input.type === 'radio' || input.type === 'checkbox') {
        if (input.checked) {
          this.formData[input.name] = input.value;
        }
      } else {
        this.formData[input.id] = input.value;
      }
    });
  }

  async submit() {
    this.collectFormData();
    console.log('Submitting:', this.formData);
    
    try {
      const response = await fetch('/deployment/request', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(this.formData)
      });

      if (response.ok) {
        const result = await response.json();
        // Redirect or show success
        window.location.href = `/deployment/request/${result.dr_id}`;
      } else {
        alert('Error submitting request');
      }
    } catch (error) {
      console.error('Submission error:', error);
    }
  }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  new DeploymentFormManager();
});
```

---

## 3. INTEGRATION WITH EXISTING CODE

### 3.1 Update base.html - Add New Navigation
```html
<!-- Add to navbar in templates/base.html -->

<li class="nav-item">
  <a class="nav-link" href="{{ url_for('booking.booking_screen_new') }}">
    📅 Book Environment
  </a>
</li>
<li class="nav-item">
  <a class="nav-link" href="{{ url_for('deployment.list_requests') }}">
    🚀 Deployment Requests
  </a>
</li>
```

### 3.2 Update Flask Routes
```python
# In routes/booking.py

@booking.route('/environments', methods=['GET'])
def get_environments():
    """Returns filtered environments for grid view"""
    filters = {
        'type': request.args.getlist('type'),
        'status': request.args.get('status'),
        'search': request.args.get('search', '')
    }
    
    query = Environment.query
    
    if filters['type']:
        query = query.filter(Environment.env_type.in_(filters['type']))
    
    if filters['search']:
        query = query.filter(
            Environment.env_id.ilike(f"%{filters['search']}%")
        )
    
    environments = query.all()
    
    return jsonify([{
        'env_id': env.env_id,
        'env_type': env.env_type,
        'status': get_environment_status(env),
        'capacity_used': calculate_capacity(env),
        # ... other fields
    } for env in environments])
```

---

## 4. DATABASE MODELS (If needed)

### 4.1 Deployment Request Model
```python
# Add to webapp/models.py

class DeploymentRequest(db.Model):
    __tablename__ = "deployment_requests"
    
    dr_id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    env_id = db.Column(db.String(50), db.ForeignKey("environments.env_id"))
    
    status = db.Column(
        db.String(20),
        nullable=False,
        default='draft'
    )  # draft, pending, scheduled, deploying, completed, failed
    
    priority = db.Column(db.String(20), default='medium')
    risk_level = db.Column(db.String(20), default='medium')
    
    created_by = db.Column(db.String(50), db.ForeignKey("users.user_id"))
    assigned_to = db.Column(db.String(200))  # JSON list of user_ids
    
    scheduled_window = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

## 5. NEXT STEPS

1. **Phase 1 - Setup:**
   - [ ] Create new template files (booking_new.html, deployment_request.html)
   - [ ] Add CSS files to static/css/
   - [ ] Add JavaScript files to static/js/
   - [ ] Create new Flask routes in deployment.py

2. **Phase 2 - API Integration:**
   - [ ] Implement `/environments` API endpoint
   - [ ] Implement `/deployment/requests` endpoint
   - [ ] Add database models if needed
   - [ ] Test API responses

3. **Phase 3 - Frontend Logic:**
   - [ ] Implement filter/search functionality
   - [ ] Build multi-step form validation
   - [ ] Add real-time updates
   - [ ] Testing & debugging

4. **Phase 4 - Polish:**
   - [ ] Mobile responsiveness
   - [ ] Accessibility (ARIA labels)
   - [ ] Error handling
   - [ ] Loading states

