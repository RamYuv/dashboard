# EnvBooking Architecture

## Overview

EnvBooking is a Flask-based environment management application with two tightly related runtime concerns:

1. Environment booking and deployment request management.
2. Environment health monitoring and dashboard refresh.

The application follows a layered structure:

- `webapp/routes`: HTTP endpoints and HTML page rendering.
- `webapp/services`: booking and deployment workflows.
- `webapp/domain`: domain rules such as reservation conflict checks and deployment target resolution.
- `webapp/models.py`: SQLAlchemy persistence model.
- `monitoring/*`: monitoring refresh pipeline, shared state, and monitoring API endpoints.

The main app entry point is the Flask app factory in `webapp/__init__.py`. Local development runs through `run.py`, which starts both the Flask server and an embedded monitoring background thread.

## High-Level Runtime View

```mermaid
flowchart LR
    Browser[Browser / Frontend JS]
    MainBP[Main Blueprint]
    MonBP[Monitoring Blueprint]
    Auth[Auth Service]
    BookingSvc[BookingService]
    DeploySvc[DeploymentRequestService]
    ConflictSvc[ReservationConflictService]
    TargetDomain[Deployment Target Domain]
    Models[SQLAlchemy Models]
    DB[(SQLite / SQLAlchemy DB)]
    MonitorState[MonitorState Cache]
    Container[AppContainer]
    Worker[EnvMonitorWorker]
    Fetcher[VmStatusFetcher]
    Aggregator[EnvStatusAggregator]
    Events[EventBroker]
    CacheFile[monitoring_cache.json]
    AutoDeploy[AutoDeploymentService]
    Script[External Deployment Script]

    Browser --> MainBP
    Browser --> MonBP
    MainBP --> Auth
    MainBP --> BookingSvc
    MainBP --> DeploySvc
    MonBP --> MonitorState
    MonBP --> Models

    BookingSvc --> ConflictSvc
    BookingSvc --> Models
    DeploySvc --> ConflictSvc
    DeploySvc --> TargetDomain
    DeploySvc --> AutoDeploy
    DeploySvc --> Models

    Models --> DB
    AutoDeploy --> Script

    Container --> Worker
    Container --> Fetcher
    Container --> Aggregator
    Container --> Events
    Worker --> Fetcher
    Worker --> Aggregator
    Worker --> MonitorState
    Worker --> Models
    MonitorState --> CacheFile
```

## Core Modules

### 1. Web Application Layer

- `webapp/__init__.py` creates the Flask app, configures logging, initializes `db`, `MonitorState`, and `AppContainer`, and registers blueprints.
- `webapp/routes/main.py` owns authentication pages, dashboards, booking APIs, deployment request APIs, and current deployment lookup APIs.
- `booking/routes/booking.py` is registered separately for booking-specific screens.

Responsibilities:

- Accept HTTP requests.
- Enforce login and screen access using decorators from `auth_service.py`.
- Delegate business logic to service classes instead of embedding workflow rules in routes.

### 2. Service Layer

The service layer contains the main business workflows.

#### `BookingService`

Responsibilities:

- Validate booking payloads through `BookingValidator`.
- Detect booking-to-booking conflicts.
- Detect booking-to-deployment conflicts through `ReservationConflictService`.
- Create, update, and cancel `EnvironmentBooking` records.

#### `DeploymentRequestService`

Responsibilities:

- Validate deployment request payloads.
- Resolve deployment scope (`ENV` vs `ENV_TYPE` for shared tool deployments).
- Resolve target packages and environment host mappings.
- Create `DeploymentRequest` and `Deployment` records.
- Progress deployment requests through approval and execution states.
- Trigger external auto-deployment scripts through `AutoDeploymentService`.
- Update `CurrentDeploymentState` after successful completion.

### 3. Domain Layer

#### `ReservationConflictService`

Encapsulates overlap logic between:

- `EnvironmentBooking`
- `DeploymentRequest`

This keeps time-window conflict rules outside the route layer and shared across workflows.

#### `deployment_targets.py`

Loads and normalizes deployment target definitions from `configs/deployment_targets.json`, then resolves:

- canonical target keys
- component types
- selected package keys
- concrete `EnvironmentHostMapping` targets

This module is the bridge between JSON target configuration and deployable DB-backed infrastructure mappings.

### 4. Data Layer

`webapp/models.py` is the canonical persistence model and currently contains:

- identity and access models: `User`, `Team`, `TeamMember`
- infrastructure models: `Environment`, `Host`, `ServerType`, `EnvironmentHostMapping`
- deployment models: `ComponentBuild`, `DeploymentRequest`, `Deployment`, `CurrentDeploymentState`
- reservation model: `EnvironmentBooking`

Important design choices:

- `EnvironmentHostMapping` is the central infrastructure join model that ties environment, host, and server type together.
- `DeploymentRequest` is the workflow parent record.
- `Deployment` stores per-target execution detail under a request.
- `CurrentDeploymentState` is the read-optimized snapshot of what is currently deployed per mapping/package.

### 5. Monitoring Subsystem

The monitoring subsystem is designed so the same refresh workflow can run:

- inside the Flask process for local/dev (`run.py`)
- in a standalone worker process (`monitoring/worker_main.py`)

Key parts:

- `AppContainer`: wires monitoring dependencies together.
- `EnvMonitorWorker`: executes one refresh cycle.
- `VmStatusFetcher`: fetches and parses raw VM/service status.
- `EnvStatusAggregator`: converts VM-level health into environment summaries and deltas.
- `MonitorState`: thread-safe in-memory snapshot plus persisted cache file.
- `monitoring/api.py`: exposes environment health as JSON and enriches it with booking activity and server-type metadata.

## Main Execution Flows

### Booking Flow

```mermaid
sequenceDiagram
    participant Client
    participant Route as main.py /api/bookings
    participant Service as BookingService
    participant Conflict as ReservationConflictService
    participant Model as EnvironmentBooking
    participant DB as Database

    Client->>Route: POST /api/bookings
    Route->>Service: create(payload, user)
    Service->>Conflict: find_conflicting_booking(...)
    Service->>Conflict: find_conflicting_deployment_request(...)
    Service->>Model: create EnvironmentBooking
    Model->>DB: commit
    Route-->>Client: booking response
```

### Deployment Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant Route as main.py /api/deployment-requests
    participant Service as DeploymentRequestService
    participant Target as deployment_targets.py
    participant Conflict as ReservationConflictService
    participant DB as Database
    participant Auto as AutoDeploymentService
    participant Script as External Script

    Client->>Route: POST deployment request
    Route->>Service: create(payload, user)
    Service->>Conflict: check booking overlap
    Service->>Target: resolve_request_targets(...)
    Service->>DB: create DeploymentRequest + Deployment rows
    Route-->>Client: created request

    Client->>Route: POST action=auto_deploy
    Route->>Service: apply_action(...)
    Service->>Auto: start(deployment_request)
    Auto->>Script: launch script with payload
    Route-->>Client: updated workflow state
```

### Monitoring Refresh Flow

```mermaid
sequenceDiagram
    participant BG as BackgroundMonitoringService
    participant Worker as EnvMonitorWorker
    participant DB as EnvironmentHostMapping query
    participant Fetcher as VmStatusFetcher
    participant Agg as EnvStatusAggregator
    participant State as MonitorState
    participant API as monitoring/api.py

    BG->>Worker: refresh()
    Worker->>DB: load mappings
    Worker->>Fetcher: fetch_vm_status(host, user, password)
    Worker->>Agg: aggregate_env_statuses(...)
    Worker->>Agg: calculate_status_delta(...)
    Worker->>State: update(snapshot, delta)
    API->>State: snapshot()
    API-->>Browser: environment health payload
```

## Architectural Strengths

- Clear route-to-service separation.
- Domain logic extracted from controllers.
- Monitoring pipeline is reusable across embedded and standalone modes.
- `CurrentDeploymentState` provides a stable read model for current deployments.
- `MonitorState` gives a thread-safe shared cache between refresh workers and HTTP reads.

## Current Boundaries And Practical Notes

- `models.py` is still a large consolidation point; the domain model is centralized rather than split by feature.
- Some legacy duplicate modules remain in `webapp/` alongside the newer `webapp/services/` and `webapp/domain/` packages. Current routes use the service/domain package structure.
- Monitoring fetch is currently stubbed by `VmStatusFetcher.service_status()` and is ready for a real remote execution adapter.
- Auto deployment is asynchronous and delegated to external scripts, so deployment orchestration crosses the Python process boundary intentionally.

## Suggested Documentation Pairing

- Use [CLASS_DIAGRAM.md](/d:/copilet_vscode/envbooking/docs/CLASS_DIAGRAM.md) for the structural view.
- Use this document for responsibility boundaries, runtime flows, and deployment/monitoring interactions.
