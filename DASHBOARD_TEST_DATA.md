# Environment Dashboard - Test Data Structure

## Template Analysis

The `env_health_dashboard.html` template expects the following data structure from the Flask route:

### Required Template Variables

```python
# User Info
id = "user123"  # User ID
role = "admin"  # User role (admin, qa, user, manager)

# Summary Statistics
summary = {
    'total': 33,
    'healthy': 26,
    'warning': 4,
    'critical': 2,
    'last_updated': '2026-04-25T14:30:00'
}

# Refresh interval in seconds
refresh_seconds = 30

# Grouped environments by type
grouped_statuses = {
    'DEV': [
        {
            'env_id': 'DEV01',
            'env_type': 'DEV',
            'host': 'host1.example.local',
            'owner_team': 'alpha',
            'status': 'healthy',  # healthy, warning, or critical
            'cpu_percent': 45,
            'memory_percent': 60,
            'disk_percent': 72,
            'database_status': 'running',
            'message': '',
            'logical_servers': ['cor-tcs', 'gateway-tcs']
        },
        {
            'env_id': 'DEV02',
            'env_type': 'DEV',
            'host': 'host1.example.local',
            'owner_team': 'alpha',
            'status': 'warning',
            'cpu_percent': 85,
            'memory_percent': 88,
            'disk_percent': 91,
            'database_status': 'running',
            'message': 'High resource usage',
            'logical_servers': ['cor-tcs', 'gateway-tcs']
        },
        # ... more DEV environments
    ],
    'QA': [
        # Similar structure for QA environments
    ],
    'ST': [
        # Similar structure for ST environments
    ],
    'PROD': [
        # Similar structure for PROD environments
    ]
}

# List of active booking environment IDs (for highlighting with green glow)
active_envs = ['DEV01', 'PROD01']
```

---

## Complete Dummy Data Example

### For Testing the Template

```python
DUMMY_DASHBOARD_DATA = {
    'id': 'john.doe',
    'role': 'admin',
    'summary': {
        'total': 33,
        'healthy': 26,
        'warning': 4,
        'critical': 2,
        'last_updated': '2026-04-25T14:30:15'
    },
    'refresh_seconds': 30,
    'grouped_statuses': {
        'DEV': [
            {
                'env_id': 'DEV01',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'alpha',
                'status': 'healthy',
                'cpu_percent': 45,
                'memory_percent': 60,
                'disk_percent': 72,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            },
            {
                'env_id': 'DEV02',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'alpha',
                'status': 'healthy',
                'cpu_percent': 42,
                'memory_percent': 58,
                'disk_percent': 70,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            },
            {
                'env_id': 'DEV03',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'beta',
                'status': 'warning',
                'cpu_percent': 78,
                'memory_percent': 85,
                'disk_percent': 88,
                'database_status': 'running',
                'message': 'High resource utilization',
                'logical_servers': ['cor-tcs']
            },
            {
                'env_id': 'DEV04',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'alpha',
                'status': 'healthy',
                'cpu_percent': 50,
                'memory_percent': 62,
                'disk_percent': 75,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['gateway-tcs']
            },
            {
                'env_id': 'DEV05',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'support',
                'status': 'healthy',
                'cpu_percent': 40,
                'memory_percent': 55,
                'disk_percent': 68,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            },
            {
                'env_id': 'DEV06',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'alpha',
                'status': 'healthy',
                'cpu_percent': 48,
                'memory_percent': 63,
                'disk_percent': 73,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs']
            },
            {
                'env_id': 'DEV07',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'beta',
                'status': 'healthy',
                'cpu_percent': 44,
                'memory_percent': 59,
                'disk_percent': 71,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['gateway-tcs']
            },
            {
                'env_id': 'DEV08',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'alpha',
                'status': 'warning',
                'cpu_percent': 82,
                'memory_percent': 89,
                'disk_percent': 92,
                'database_status': 'running',
                'message': 'Disk usage approaching limit',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            },
            {
                'env_id': 'DEV09',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'support',
                'status': 'healthy',
                'cpu_percent': 46,
                'memory_percent': 61,
                'disk_percent': 72,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs']
            },
            {
                'env_id': 'DEV10',
                'env_type': 'DEV',
                'host': 'host1.example.local',
                'owner_team': 'beta',
                'status': 'healthy',
                'cpu_percent': 43,
                'memory_percent': 57,
                'disk_percent': 69,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['gateway-tcs']
            }
        ],
        'ST': [
            {
                'env_id': 'ST01',
                'env_type': 'ST',
                'host': 'host1.example.local',
                'owner_team': 'qa',
                'status': 'healthy',
                'cpu_percent': 52,
                'memory_percent': 65,
                'disk_percent': 76,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            },
            {
                'env_id': 'ST02',
                'env_type': 'ST',
                'host': 'host1.example.local',
                'owner_team': 'qa',
                'status': 'healthy',
                'cpu_percent': 51,
                'memory_percent': 64,
                'disk_percent': 75,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs']
            },
            {
                'env_id': 'ST03',
                'env_type': 'ST',
                'host': 'host1.example.local',
                'owner_team': 'qa',
                'status': 'healthy',
                'cpu_percent': 49,
                'memory_percent': 62,
                'disk_percent': 74,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['gateway-tcs']
            }
        ],
        'QA': [
            {
                'env_id': 'QA01',
                'env_type': 'QA',
                'host': 'host2.example.local',
                'owner_team': 'qa',
                'status': 'healthy',
                'cpu_percent': 55,
                'memory_percent': 68,
                'disk_percent': 78,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            },
            {
                'env_id': 'QA02',
                'env_type': 'QA',
                'host': 'host2.example.local',
                'owner_team': 'qa',
                'status': 'warning',
                'cpu_percent': 79,
                'memory_percent': 86,
                'disk_percent': 89,
                'database_status': 'running',
                'message': 'Memory pressure detected',
                'logical_servers': ['cor-tcs']
            },
            {
                'env_id': 'QA03',
                'env_type': 'QA',
                'host': 'host2.example.local',
                'owner_team': 'qa',
                'status': 'healthy',
                'cpu_percent': 53,
                'memory_percent': 66,
                'disk_percent': 77,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['gateway-tcs']
            }
        ],
        'PROD': [
            {
                'env_id': 'PROD01',
                'env_type': 'PROD',
                'host': 'host2.example.local',
                'owner_team': 'support',
                'status': 'healthy',
                'cpu_percent': 35,
                'memory_percent': 48,
                'disk_percent': 65,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            },
            {
                'env_id': 'PROD02',
                'env_type': 'PROD',
                'host': 'host2.example.local',
                'owner_team': 'support',
                'status': 'healthy',
                'cpu_percent': 38,
                'memory_percent': 51,
                'disk_percent': 67,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs']
            },
            {
                'env_id': 'PROD03',
                'env_type': 'PROD',
                'host': 'host2.example.local',
                'owner_team': 'support',
                'status': 'critical',
                'cpu_percent': 95,
                'memory_percent': 98,
                'disk_percent': 99,
                'database_status': 'degraded',
                'message': 'Critical: Service unavailable',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            },
            {
                'env_id': 'PROD04',
                'env_type': 'PROD',
                'host': 'host2.example.local',
                'owner_team': 'support',
                'status': 'healthy',
                'cpu_percent': 36,
                'memory_percent': 49,
                'disk_percent': 66,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['gateway-tcs']
            },
            {
                'env_id': 'PROD05',
                'env_type': 'PROD',
                'host': 'host2.example.local',
                'owner_team': 'support',
                'status': 'critical',
                'cpu_percent': 92,
                'memory_percent': 95,
                'disk_percent': 97,
                'database_status': 'unhealthy',
                'message': 'Critical: Multiple component failures',
                'logical_servers': ['cor-tcs']
            },
            {
                'env_id': 'PROD06',
                'env_type': 'PROD',
                'host': 'host2.example.local',
                'owner_team': 'support',
                'status': 'healthy',
                'cpu_percent': 37,
                'memory_percent': 50,
                'disk_percent': 66,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            }
        ],
        'UAT': [
            {
                'env_id': 'UAT01',
                'env_type': 'UAT',
                'host': 'host2.example.local',
                'owner_team': 'qa',
                'status': 'healthy',
                'cpu_percent': 54,
                'memory_percent': 67,
                'disk_percent': 77,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs', 'gateway-tcs']
            },
            {
                'env_id': 'UAT02',
                'env_type': 'UAT',
                'host': 'host2.example.local',
                'owner_team': 'qa',
                'status': 'healthy',
                'cpu_percent': 56,
                'memory_percent': 69,
                'disk_percent': 79,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['cor-tcs']
            },
            {
                'env_id': 'UAT03',
                'env_type': 'UAT',
                'host': 'host2.example.local',
                'owner_team': 'qa',
                'status': 'healthy',
                'cpu_percent': 57,
                'memory_percent': 70,
                'disk_percent': 80,
                'database_status': 'running',
                'message': '',
                'logical_servers': ['gateway-tcs']
            }
        ]
    },
    'active_envs': ['DEV01', 'PROD01']
}
```

---

## Status Values

The `status` field can have these values:
- `'healthy'` → Green light (bottom)
- `'warning'` → Yellow light (middle)
- `'critical'` → Red light (top)

---

## How to Use This Test Data

### Option 1: Render in Development

Add a test route to `main.py`:

```python
@main_bp.route("/dashboard-test")
def dashboard_test():
    """Test route to view dashboard with dummy data"""
    test_data = {
        'id': 'test.user',
        'role': 'admin',
        'summary': {
            'total': 33,
            'healthy': 26,
            'warning': 4,
            'critical': 2,
            'last_updated': datetime.now(timezone.utc).isoformat()
        },
        'refresh_seconds': 30,
        'grouped_statuses': {
            'DEV': [...],  # Use dummy data from above
            'ST': [...],
            'QA': [...],
            'PROD': [...]
        },
        'active_envs': ['DEV01', 'PROD01']
    }
    return render_template('env_health_dashboard.html', **test_data)
```

Then visit: `http://localhost:5000/dashboard-test`

### Option 2: Copy Dummy Data to Python Script

Create a test file `test_dashboard.py`:

```python
from flask import render_template_string
from webapp import create_app

app = create_app()

with app.app_context():
    with open('webapp/templates/env_health_dashboard.html', 'r') as f:
        template = f.read()
    
    html = render_template_string(template, **DUMMY_DASHBOARD_DATA)
    with open('dashboard_preview.html', 'w') as f:
        f.write(html)
    
    print("Dashboard preview saved to dashboard_preview.html")
```

Then open `dashboard_preview.html` in a browser.

---

## Traffic Light Status Codes

- **Green (Healthy)**: All systems operational, CPU < 70%, Memory < 75%, Disk < 80%
- **Yellow (Warning)**: Elevated resource usage, CPU 70-90%, Memory 75-90%, Disk 80-95%
- **Red (Critical)**: Critical state, CPU > 90%, Memory > 90%, Disk > 95%, or services down
