# routes

HTTP route handlers for the simulation FastAPI application.

## API Endpoints

### Authentication (`auth.py`)

| Method | Path | Auth Required | Role | Description |
|--------|------|---------------|------|-------------|
| `POST` | `/auth/login` | No | — | Authenticate with email/password; returns session `api_key`, `role`, `email` |
| `POST` | `/auth/register` | Yes | admin | Provision a new viewer account (or update password of existing one) |
| `GET` | `/auth/validate` | Yes | any | Validate API key; returns 200 if valid, 401 if not |

### Simulation Lifecycle (`simulation.py`)

| Method | Path | Auth Required | Role | Description |
|--------|------|---------------|------|-------------|
| `POST` | `/simulation/start` | Yes | admin | Start the simulation |
| `POST` | `/simulation/pause` | Yes | admin | Two-phase pause (draining → paused) |
| `POST` | `/simulation/resume` | Yes | admin | Resume from paused state |
| `POST` | `/simulation/stop` | Yes | admin | Stop the simulation |
| `POST` | `/simulation/reset` | Yes | admin | Reset to initial state, clear all data |
| `PUT` | `/simulation/speed` | Yes | admin | Change speed multiplier (0.5–128) |
| `GET` | `/simulation/status` | Yes | any | Current state, agent counts, uptime |

### Agent Management (`agents.py`)

| Method | Path | Auth Required | Role | Description |
|--------|------|---------------|------|-------------|
| `POST` | `/agents/drivers` | Yes | admin | Queue driver agents for spawning |
| `POST` | `/agents/riders` | Yes | admin | Queue rider agents for spawning |
| `GET` | `/agents/spawn-status` | Yes | any | Current spawn queue depth |
| `GET` | `/agents/drivers/{driver_id}` | Yes | any | Full state, DNA, statistics for a driver |
| `GET` | `/agents/riders/{rider_id}` | Yes | any | Full state, DNA, statistics for a rider |
| `PUT` | `/agents/drivers/{driver_id}/status` | Yes | admin | Toggle driver online/offline |
| `POST` | `/agents/riders/{rider_id}/request-trip` | Yes | any | Trigger a trip request for a rider |

### Puppet Agent Control (`puppet.py`)

All puppet mutation endpoints require admin role. State-inspection endpoints accept any valid key.

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/puppet/drivers` | admin | Create a puppet driver |
| `POST` | `/puppet/riders` | admin | Create a puppet rider |
| `PUT` | `/puppet/drivers/{id}/go-online` | admin | Transition puppet driver to available |
| `PUT` | `/puppet/drivers/{id}/go-offline` | admin | Transition puppet driver to offline |
| `PUT` | `/puppet/drivers/{id}/accept-offer` | admin | Accept pending trip offer |
| `PUT` | `/puppet/drivers/{id}/reject-offer` | admin | Reject pending trip offer |
| `PUT` | `/puppet/drivers/{id}/drive-to-pickup` | admin | Start driving to pickup location |
| `PUT` | `/puppet/drivers/{id}/arrive-pickup` | admin | Signal arrival at pickup |
| `PUT` | `/puppet/drivers/{id}/start-trip` | admin | Start the trip |
| `PUT` | `/puppet/drivers/{id}/drive-to-destination` | admin | Start driving to dropoff |
| `PUT` | `/puppet/drivers/{id}/complete-trip` | admin | Complete the trip |
| `PUT` | `/puppet/drivers/{id}/cancel-trip` | admin | Cancel an in-progress trip |
| `PUT` | `/puppet/drivers/{id}/location` | admin | Teleport driver to coordinates |
| `PUT` | `/puppet/riders/{id}/go-offline` | admin | Transition puppet rider offline |

### Performance Controller Proxy (`controller.py`)

| Method | Path | Auth Required | Role | Description |
|--------|------|---------------|------|-------------|
| `GET` | `/controller/status` | Yes | any | Proxy to performance-controller GET /status |
| `PUT` | `/controller/mode` | Yes | admin | Proxy to performance-controller PUT /controller/mode |

### Metrics (`metrics.py`)

| Method | Path | Auth Required | Role | Description |
|--------|------|---------------|------|-------------|
| `GET` | `/metrics` | Yes | any | Aggregated Prometheus + cAdvisor + simulation metrics (500ms cache) |
| `GET` | `/metrics/infrastructure` | Yes | any | Infrastructure service health statuses |

## Rate Limits

| Endpoint Group | Limit |
|----------------|-------|
| `POST /auth/login` | 10/minute |
| `POST /auth/register` | 20/minute |
| Simulation lifecycle mutations | 10/minute |
| Agent creation | 120/minute |
| Agent state reads | 60/minute |
| Driver status toggle | 30/minute |
| Metrics polling | 100/minute (`/status`), 60/minute (metrics) |
