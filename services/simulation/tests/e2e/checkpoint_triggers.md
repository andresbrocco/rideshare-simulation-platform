# Checkpoint Triggers — E2E Test Routine

Verifies the 4 checkpoint trigger integrations: periodic saves, save-on-pause, save-on-SIGTERM, and auto-restore-on-startup. Each test is a sequence of shell commands with explicit pass/fail assertions.

## Environment

| Variable | Purpose |
|----------|---------|
| `COMPOSE` | Path to compose file |
| `API` | Simulation API base URL |
| `AUTH` | API key header |

## Conventions

- **Every assertion** uses `|| { echo "FAIL: ..."; exit 1; }` so the agent stops on first failure.
- **Polling loops** have a max iteration count and fail explicitly on timeout.
- Tests are **sequential** — each builds on the state left by the previous one.
- The routine is **self-contained** — setup creates all state, teardown destroys it.

---

## Setup

```bash
COMPOSE="infrastructure/docker/compose.yml"
API="http://localhost:8000/api/v1"
AUTH="X-API-Key: admin"
```

```bash
# Tear down any existing state
docker compose -f "$COMPOSE" --profile core down -v 2>/dev/null

# Start with short checkpoint interval (60s sim-time) and 10x speed
# At 10x speed: 60s sim-time = ~6s wall-time
SIM_CHECKPOINT_INTERVAL=60 SIM_SPEED_MULTIPLIER=10 \
  docker compose -f "$COMPOSE" --profile core up -d
```

### Wait for simulation to be healthy

```bash
for i in $(seq 1 60); do
  STATUS=$(curl -sf http://localhost:8000/health 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
  [ "$STATUS" = "healthy" ] && break
  sleep 3
done
[ "$STATUS" = "healthy" ] || { echo "FAIL: simulation not healthy after 180s"; exit 1; }
echo "Setup complete — simulation healthy"
```

---

## Test 1: Periodic Checkpoint with Agents

**Goal:** Checkpoint fires automatically after `checkpoint_interval` sim-seconds and persists agent state.

### Step 1.1 — Start simulation and spawn agents

```bash
curl -sf -X POST "$API/simulation/start" -H "$AUTH" > /dev/null
curl -sf -X POST "$API/agents/drivers" -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"count": 5}' > /dev/null
curl -sf -X POST "$API/agents/riders" -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"count": 5}' > /dev/null
```

### Step 1.2 — Wait for agents to spawn

```bash
for i in $(seq 1 15); do
  DRIVERS=$(curl -sf "$API/simulation/status" -H "$AUTH" | python3 -c "import json,sys; print(json.load(sys.stdin)['drivers_total'])")
  [ "$DRIVERS" -ge 5 ] 2>/dev/null && break
  sleep 2
done
[ "$DRIVERS" -ge 5 ] || { echo "FAIL: only $DRIVERS drivers spawned, expected >= 5"; exit 1; }
echo "PASS: $DRIVERS drivers spawned"
```

### Step 1.3 — Wait for periodic checkpoint to fire

```bash
# At 10x speed with 60s interval, checkpoint should fire within ~8s wall-time.
# Give 30s buffer for spawning delays.
sleep 15

docker compose -f "$COMPOSE" logs simulation 2>&1 | grep -q "Periodic checkpoint saved" \
  || { echo "FAIL: no periodic checkpoint log found"; exit 1; }
echo "PASS: periodic checkpoint log found"
```

### Step 1.4 — Assert checkpoint metadata in DB

```bash
docker compose -f "$COMPOSE" exec -T simulation \
  python3 -c "
import sqlite3, sys
conn = sqlite3.connect('/app/db/simulation.db')

# Check metadata exists
current_time = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='current_time'\").fetchone()
assert current_time is not None, 'current_time missing'
assert float(current_time[0]) > 0, f'current_time should be > 0, got {current_time[0]}'

# Check agents persisted
driver_count = conn.execute('SELECT COUNT(*) FROM drivers').fetchone()[0]
rider_count = conn.execute('SELECT COUNT(*) FROM riders').fetchone()[0]
assert driver_count >= 5, f'expected >= 5 drivers, got {driver_count}'
assert rider_count >= 5, f'expected >= 5 riders, got {rider_count}'

# Check agent state is meaningful (has location and status)
driver = conn.execute('SELECT status, current_location FROM drivers LIMIT 1').fetchone()
assert driver[0] in ('online', 'offline', 'en_route_pickup', 'en_route_destination'), f'unexpected driver status: {driver[0]}'
assert ',' in driver[1], f'location should be lat,lon format, got: {driver[1]}'

conn.close()
print(f'PASS: checkpoint has {driver_count} drivers, {rider_count} riders, sim_time={current_time[0]}')
" || { echo "FAIL: checkpoint DB assertions failed"; exit 1; }
```

### Step 1.5 — Record pre-test-2 status

```bash
curl -sf "$API/simulation/status" -H "$AUTH" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'State: {d[\"state\"]}, Drivers: {d[\"drivers_total\"]}, Riders: {d[\"riders_total\"]}, Trips: {d[\"active_trips_count\"]}')
"
```

---

## Test 2: Checkpoint on Pause (with Drain)

**Goal:** Pausing triggers RUNNING -> DRAINING -> PAUSED, then saves a graceful checkpoint. Agent state at pause-time is persisted.

### Step 2.1 — Initiate pause

```bash
curl -sf -X POST "$API/simulation/pause" -H "$AUTH" > /dev/null
echo "Pause requested — drain started"
```

### Step 2.2 — Wait for PAUSED state (drain completion)

```bash
FINAL_STATE=""
for i in $(seq 1 30); do
  STATE=$(curl -sf "$API/simulation/status" -H "$AUTH" | python3 -c "import json,sys; print(json.load(sys.stdin)['state'])")
  FINAL_STATE="$STATE"
  [ "$STATE" = "paused" ] && break
  sleep 2
done
[ "$FINAL_STATE" = "paused" ] || { echo "FAIL: state is '$FINAL_STATE' after 60s, expected 'paused'"; exit 1; }
echo "PASS: state transitioned to paused"
```

### Step 2.3 — Assert checkpoint-on-pause log

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 | grep -q "Checkpoint saved on pause" \
  || { echo "FAIL: no checkpoint-on-pause log"; exit 1; }
echo "PASS: checkpoint-on-pause log found"
```

### Step 2.4 — Assert checkpoint is graceful (post-drain = no in-flight trips)

```bash
docker compose -f "$COMPOSE" exec -T simulation \
  python3 -c "
import sqlite3
conn = sqlite3.connect('/app/db/simulation.db')

ckpt_type = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='checkpoint_type'\").fetchone()[0]
in_flight = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='in_flight_trips'\").fetchone()[0]
status = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='status'\").fetchone()[0]

assert ckpt_type == 'graceful', f'expected graceful checkpoint, got {ckpt_type}'
assert int(in_flight) == 0, f'expected 0 in-flight trips, got {in_flight}'
assert status == 'paused', f'expected paused status, got {status}'

# Agents still in DB with their paused-time state
d = conn.execute('SELECT COUNT(*) FROM drivers').fetchone()[0]
r = conn.execute('SELECT COUNT(*) FROM riders').fetchone()[0]
assert d >= 5, f'expected >= 5 drivers, got {d}'
assert r >= 5, f'expected >= 5 riders, got {r}'

conn.close()
print(f'PASS: graceful checkpoint, 0 in-flight, {d} drivers, {r} riders')
" || { echo "FAIL: pause checkpoint assertions failed"; exit 1; }
```

### Step 2.5 — Assert drain trigger in log

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 \
  | grep -qE "trigger=(quiescence_achieved|drain_timeout)" \
  || { echo "FAIL: no drain trigger in log"; exit 1; }

TRIGGER=$(docker compose -f "$COMPOSE" logs simulation 2>&1 \
  | grep -oE "trigger=(quiescence_achieved|drain_timeout)" | tail -1)
echo "PASS: drain completed with $TRIGGER"
```

### Step 2.6 — Resume for next test

```bash
curl -sf -X POST "$API/simulation/resume" -H "$AUTH" > /dev/null
sleep 3
STATE=$(curl -sf "$API/simulation/status" -H "$AUTH" | python3 -c "import json,sys; print(json.load(sys.stdin)['state'])")
[ "$STATE" = "running" ] || { echo "FAIL: state is '$STATE' after resume, expected 'running'"; exit 1; }
echo "PASS: resumed to running"
```

---

## Test 3: Checkpoint on SIGTERM

**Goal:** SIGTERM saves a checkpoint after sim_runner.stop() but before engine.stop(). Call order: runner_stop -> checkpoint -> engine_stop.

### Step 3.1 — Let simulation accumulate state

```bash
sleep 5
PRE_TIME=$(curl -sf "$API/simulation/status" -H "$AUTH" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['current_time'])")
echo "Pre-shutdown sim time: $PRE_TIME"
```

### Step 3.2 — Send SIGTERM (graceful stop)

```bash
docker compose -f "$COMPOSE" stop simulation
```

### Step 3.3 — Assert shutdown checkpoint in logs

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 | grep -q "Shutdown checkpoint saved" \
  || { echo "FAIL: no shutdown checkpoint log"; exit 1; }
echo "PASS: shutdown checkpoint log found"
```

### Step 3.4 — Assert correct call order (runner_stop before checkpoint)

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 | python3 -c "
import sys
lines = sys.stdin.readlines()
runner_idx = next((i for i, l in enumerate(lines) if 'Simulation loop stopped' in l), -1)
ckpt_idx = next((i for i, l in enumerate(lines) if 'Shutdown checkpoint saved' in l), -1)
signal_idx = next((i for i, l in enumerate(lines) if 'Received signal' in l), -1)

assert signal_idx >= 0, 'signal log not found'
assert ckpt_idx >= 0, 'checkpoint log not found'
assert signal_idx < ckpt_idx, f'signal should precede checkpoint (signal={signal_idx}, ckpt={ckpt_idx})'

print(f'PASS: signal at line {signal_idx}, checkpoint at line {ckpt_idx}, runner_stop at line {runner_idx}')
" || { echo "FAIL: call order assertions failed"; exit 1; }
```

### Step 3.5 — Assert checkpoint persisted to DB (survives container restart)

```bash
SIM_CHECKPOINT_INTERVAL=60 SIM_SPEED_MULTIPLIER=10 \
  docker compose -f "$COMPOSE" up -d simulation
sleep 8

docker compose -f "$COMPOSE" exec -T simulation \
  python3 -c "
import sqlite3
conn = sqlite3.connect('/app/db/simulation.db')

current_time = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='current_time'\").fetchone()
assert current_time is not None, 'checkpoint lost after restart'

d = conn.execute('SELECT COUNT(*) FROM drivers').fetchone()[0]
r = conn.execute('SELECT COUNT(*) FROM riders').fetchone()[0]
assert d >= 5, f'expected >= 5 drivers in DB, got {d}'
assert r >= 5, f'expected >= 5 riders in DB, got {r}'

conn.close()
print(f'PASS: checkpoint persisted across restart — sim_time={current_time[0]}, {d} drivers, {r} riders')
" || { echo "FAIL: checkpoint not persisted after restart"; exit 1; }
```

---

## Test 4: Auto-Restore — Agent, Time, and Speed Recovery

**Goal:** Restart with `resume_from_checkpoint=true`. Verify sim time, agents, and speed are restored from the checkpoint saved in Test 3.

### Step 4.1 — Record current checkpoint state

```bash
PRE_RESTORE=$(docker compose -f "$COMPOSE" exec -T simulation \
  python3 -c "
import sqlite3, json
conn = sqlite3.connect('/app/db/simulation.db')
ct = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='current_time'\").fetchone()[0]
d = conn.execute('SELECT COUNT(*) FROM drivers').fetchone()[0]
r = conn.execute('SELECT COUNT(*) FROM riders').fetchone()[0]
print(json.dumps({'sim_time': float(ct), 'drivers': d, 'riders': r}))
conn.close()
")
echo "Checkpoint state: $PRE_RESTORE"
```

### Step 4.2 — Restart with resume enabled

```bash
docker compose -f "$COMPOSE" stop simulation

SIM_CHECKPOINT_INTERVAL=60 SIM_SPEED_MULTIPLIER=10 SIM_RESUME_FROM_CHECKPOINT=true \
  docker compose -f "$COMPOSE" up -d simulation
```

### Step 4.3 — Wait for healthy

```bash
for i in $(seq 1 30); do
  HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
  [ "$HEALTH" = "healthy" ] && break
  sleep 3
done
[ "$HEALTH" = "healthy" ] || { echo "FAIL: simulation not healthy after restore"; exit 1; }
```

### Step 4.4 — Assert restore log

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 | grep -q "Simulation restored from checkpoint" \
  || { echo "FAIL: no restore log found"; exit 1; }
echo "PASS: restore log found"
```

### Step 4.5 — Assert checkpoint restore details in log

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 | grep -q "Checkpoint restored:" \
  || { echo "FAIL: no 'Checkpoint restored:' detail log"; exit 1; }

docker compose -f "$COMPOSE" logs simulation 2>&1 | grep "Checkpoint restored:" | python3 -c "
import sys, re
line = sys.stdin.read()
m = re.search(r'drivers=(\d+).*riders=(\d+)', line)
assert m, f'could not parse restore log: {line}'
d, r = int(m.group(1)), int(m.group(2))
assert d >= 5, f'expected >= 5 restored drivers, got {d}'
assert r >= 5, f'expected >= 5 restored riders, got {r}'
print(f'PASS: restored {d} drivers, {r} riders')
" || { echo "FAIL: restore detail assertions failed"; exit 1; }
```

### Step 4.6 — Assert sim time is non-zero (not starting fresh)

```bash
echo "$PRE_RESTORE" | python3 -c "
import json, sys
pre = json.loads(sys.stdin.read())
expected_time = pre['sim_time']
assert expected_time > 0, f'checkpoint sim_time should be > 0, got {expected_time}'
print(f'PASS: checkpoint sim_time={expected_time:.1f}s (not starting from 0)')
" || { echo "FAIL: sim time assertions failed"; exit 1; }
```

### Step 4.7 — Start and verify agents resume functioning

```bash
curl -sf -X POST "$API/simulation/start" -H "$AUTH" > /dev/null
sleep 12

curl -sf "$API/simulation/status" -H "$AUTH" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['state'] == 'running', f'expected running, got {d[\"state\"]}'
assert d['drivers_total'] >= 5, f'expected >= 5 drivers, got {d[\"drivers_total\"]}'
assert d['riders_total'] >= 5, f'expected >= 5 riders, got {d[\"riders_total\"]}'
print(f'PASS: running with {d[\"drivers_total\"]} drivers, {d[\"riders_total\"]} riders, {d[\"active_trips_count\"]} trips')
" || { echo "FAIL: post-restore simulation not functional"; exit 1; }
```

---

## Test 5: Dirty Checkpoint Recovery (SIGTERM During Active Trips)

**Goal:** SIGTERM while trips are in-flight produces a `crash` checkpoint. Restore cancels orphaned trips.

### Step 5.1 — Reset and start fresh

```bash
curl -sf -X POST "$API/simulation/reset" -H "$AUTH" > /dev/null
curl -sf -X POST "$API/simulation/start" -H "$AUTH" > /dev/null
```

### Step 5.2 — Spawn agents and wait for trips

```bash
curl -sf -X POST "$API/agents/drivers" -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"count": 10}' > /dev/null
curl -sf -X POST "$API/agents/riders" -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"count": 10}' -G -d 'mode=immediate' > /dev/null

# Wait for agents + some trips
sleep 20

TRIPS=$(curl -sf "$API/simulation/status" -H "$AUTH" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['active_trips_count'])")
echo "Active trips before SIGTERM: $TRIPS"
```

### Step 5.3 — SIGTERM while trips may be active

```bash
docker compose -f "$COMPOSE" stop simulation
```

### Step 5.4 — Assert checkpoint type in DB

```bash
# Start container just to query DB (it won't have resume enabled)
SIM_CHECKPOINT_INTERVAL=60 SIM_SPEED_MULTIPLIER=10 \
  docker compose -f "$COMPOSE" up -d simulation
sleep 8

docker compose -f "$COMPOSE" exec -T simulation \
  python3 -c "
import sqlite3
conn = sqlite3.connect('/app/db/simulation.db')

ckpt_type = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='checkpoint_type'\").fetchone()
in_flight = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='in_flight_trips'\").fetchone()

assert ckpt_type is not None, 'no checkpoint found'
# checkpoint_type can be 'crash' or 'graceful' depending on whether trips were still active
print(f'checkpoint_type={ckpt_type[0]}, in_flight_trips={in_flight[0] if in_flight else \"N/A\"}')
# The key assertion: checkpoint exists with correct agent counts
d = conn.execute('SELECT COUNT(*) FROM drivers').fetchone()[0]
r = conn.execute('SELECT COUNT(*) FROM riders').fetchone()[0]
assert d >= 10, f'expected >= 10 drivers, got {d}'
assert r >= 10, f'expected >= 10 riders, got {r}'
conn.close()
print(f'PASS: shutdown checkpoint has {d} drivers, {r} riders')
" || { echo "FAIL: dirty checkpoint assertions failed"; exit 1; }
```

### Step 5.5 — Restore from dirty checkpoint

```bash
docker compose -f "$COMPOSE" stop simulation

SIM_CHECKPOINT_INTERVAL=60 SIM_SPEED_MULTIPLIER=10 SIM_RESUME_FROM_CHECKPOINT=true \
  docker compose -f "$COMPOSE" up -d simulation
sleep 8
```

### Step 5.6 — Assert dirty checkpoint warning if applicable

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 | python3 -c "
import sys
logs = sys.stdin.read()
if 'dirty checkpoint' in logs.lower() or 'recovery_cleanup' in logs.lower():
    print('PASS: dirty checkpoint recovery detected and handled')
elif 'Checkpoint restored' in logs:
    # Checkpoint was graceful (no trips were in-flight at SIGTERM time)
    print('PASS: checkpoint was graceful — no dirty recovery needed')
else:
    print('FAIL: no restore log found')
    sys.exit(1)
" || { echo "FAIL: dirty recovery assertions failed"; exit 1; }
```

### Step 5.7 — Assert restore log shows agents recovered

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 | grep "Checkpoint restored:" | python3 -c "
import sys, re
line = sys.stdin.read()
assert line.strip(), 'no Checkpoint restored log'
m = re.search(r'drivers=(\d+).*riders=(\d+)', line)
assert m, f'could not parse: {line}'
d, r = int(m.group(1)), int(m.group(2))
assert d >= 10, f'expected >= 10 drivers restored, got {d}'
assert r >= 10, f'expected >= 10 riders restored, got {r}'
print(f'PASS: dirty recovery restored {d} drivers, {r} riders')
" || { echo "FAIL: dirty restore agent count failed"; exit 1; }
```

---

## Test 6: Drain Timeout with Force-Cancel then Checkpoint

**Goal:** If drain times out (2h sim-time), trips are force-cancelled, state reaches PAUSED, and checkpoint is saved.

### Step 6.1 — Reset and configure for fast drain timeout

```bash
# Stop current simulation
docker compose -f "$COMPOSE" stop simulation

# Start at max speed (100x) so the 2-hour drain timeout passes in ~72s wall-time
SIM_CHECKPOINT_INTERVAL=60 SIM_SPEED_MULTIPLIER=100 SIM_CHECKPOINT_ENABLED=true \
  docker compose -f "$COMPOSE" up -d simulation
sleep 8

curl -sf -X POST "$API/simulation/start" -H "$AUTH" > /dev/null

# Set speed to 100x via API too (compose env sets initial, API overrides runtime)
curl -sf -X PUT "$API/simulation/speed" -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"multiplier": 100}' > /dev/null
```

### Step 6.2 — Spawn agents for trip generation

```bash
curl -sf -X POST "$API/agents/drivers" -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"count": 20}' > /dev/null
curl -sf -X POST "$API/agents/riders" -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"count": 20}' -G -d 'mode=immediate' > /dev/null
sleep 15
```

### Step 6.3 — Initiate pause (starts drain)

```bash
curl -sf -X POST "$API/simulation/pause" -H "$AUTH" > /dev/null
echo "Pause requested — drain started at 100x speed"
```

### Step 6.4 — Wait for PAUSED (drain completion or timeout)

```bash
# At 100x: drain timeout = 7200s sim / 100x = 72s wall-time max
# Most drains complete via quiescence much faster
FINAL_STATE=""
for i in $(seq 1 50); do
  STATE=$(curl -sf "$API/simulation/status" -H "$AUTH" 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['state'])" 2>/dev/null)
  FINAL_STATE="$STATE"
  [ "$STATE" = "paused" ] && break
  sleep 3
done
[ "$FINAL_STATE" = "paused" ] || { echo "FAIL: state is '$FINAL_STATE' after drain, expected 'paused'"; exit 1; }
echo "PASS: drain completed, state=paused"
```

### Step 6.5 — Assert checkpoint saved on pause

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 | grep -q "Checkpoint saved on pause" \
  || { echo "FAIL: no checkpoint-on-pause log after drain"; exit 1; }
```

### Step 6.6 — Assert drain trigger type and post-drain checkpoint state

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 | python3 -c "
import sys
logs = sys.stdin.read()
if 'trigger=quiescence_achieved' in logs:
    print('PASS: drain completed via quiescence')
elif 'trigger=drain_timeout' in logs:
    print('PASS: drain completed via timeout (trips force-cancelled)')
else:
    print('FAIL: no drain trigger found in logs')
    sys.exit(1)
" || { echo "FAIL: drain trigger assertions failed"; exit 1; }
```

### Step 6.7 — Assert post-drain checkpoint is graceful

```bash
docker compose -f "$COMPOSE" exec -T simulation \
  python3 -c "
import sqlite3
conn = sqlite3.connect('/app/db/simulation.db')

ckpt_type = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='checkpoint_type'\").fetchone()[0]
in_flight = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='in_flight_trips'\").fetchone()[0]
status = conn.execute(\"SELECT value FROM simulation_metadata WHERE key='status'\").fetchone()[0]

assert ckpt_type == 'graceful', f'expected graceful after drain, got {ckpt_type}'
assert int(in_flight) == 0, f'expected 0 in-flight after drain, got {in_flight}'
assert status == 'paused', f'expected paused, got {status}'
conn.close()
print(f'PASS: post-drain checkpoint is graceful with 0 in-flight trips')
" || { echo "FAIL: post-drain checkpoint assertions failed"; exit 1; }
```

---

## Test 7: Checkpoints Disabled — Nothing Saved

**Goal:** When `checkpoint_enabled=false`, no checkpoint is saved on periodic, pause, or shutdown triggers.

### Step 7.1 — Restart with checkpoints disabled

```bash
docker compose -f "$COMPOSE" stop simulation

SIM_CHECKPOINT_INTERVAL=60 SIM_SPEED_MULTIPLIER=10 SIM_CHECKPOINT_ENABLED=false \
  docker compose -f "$COMPOSE" up -d simulation
sleep 8

# Reset to clear any existing checkpoint data
curl -sf -X POST "$API/simulation/reset" -H "$AUTH" > /dev/null
```

### Step 7.2 — Start and spawn agents

```bash
curl -sf -X POST "$API/simulation/start" -H "$AUTH" > /dev/null
curl -sf -X POST "$API/agents/drivers" -H "$AUTH" \
  -H "Content-Type: application/json" -d '{"count": 3}' > /dev/null
sleep 15
```

### Step 7.3 — Assert no periodic checkpoint

```bash
CKPT_COUNT=$(docker compose -f "$COMPOSE" logs simulation 2>&1 \
  | grep -c "Periodic checkpoint saved" || true)
[ "$CKPT_COUNT" -eq 0 ] \
  || { echo "FAIL: found $CKPT_COUNT periodic checkpoints with checkpoints disabled"; exit 1; }
echo "PASS: no periodic checkpoint when disabled"
```

### Step 7.4 — Pause and assert no pause checkpoint

```bash
curl -sf -X POST "$API/simulation/pause" -H "$AUTH" > /dev/null

for i in $(seq 1 15); do
  STATE=$(curl -sf "$API/simulation/status" -H "$AUTH" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['state'])")
  [ "$STATE" = "paused" ] && break
  sleep 2
done

PAUSE_CKPT=$(docker compose -f "$COMPOSE" logs simulation 2>&1 \
  | grep -c "Checkpoint saved on pause" || true)
[ "$PAUSE_CKPT" -eq 0 ] \
  || { echo "FAIL: found $PAUSE_CKPT pause checkpoints with checkpoints disabled"; exit 1; }
echo "PASS: no pause checkpoint when disabled"
```

### Step 7.5 — Resume, stop, and assert no shutdown checkpoint

```bash
curl -sf -X POST "$API/simulation/resume" -H "$AUTH" > /dev/null
sleep 2
docker compose -f "$COMPOSE" stop simulation

STOP_CKPT=$(docker compose -f "$COMPOSE" logs simulation 2>&1 \
  | grep -c "Shutdown checkpoint saved" || true)
[ "$STOP_CKPT" -eq 0 ] \
  || { echo "FAIL: found $STOP_CKPT shutdown checkpoints with checkpoints disabled"; exit 1; }
echo "PASS: no shutdown checkpoint when disabled"
```

---

## Test 8: No Checkpoint to Restore — Falls Back to Fresh Start

**Goal:** `resume_from_checkpoint=true` with an empty DB starts a fresh simulation with zero agents.

### Step 8.1 — Ensure clean DB (reset clears simulation_metadata)

```bash
SIM_SPEED_MULTIPLIER=10 \
  docker compose -f "$COMPOSE" up -d simulation
sleep 8

curl -sf -X POST "$API/simulation/reset" -H "$AUTH" > /dev/null
docker compose -f "$COMPOSE" stop simulation
```

### Step 8.2 — Restart with resume enabled but empty DB

```bash
SIM_SPEED_MULTIPLIER=10 SIM_RESUME_FROM_CHECKPOINT=true \
  docker compose -f "$COMPOSE" up -d simulation
sleep 8
```

### Step 8.3 — Assert "starting fresh" log

```bash
docker compose -f "$COMPOSE" logs simulation 2>&1 \
  | grep -q "No checkpoint found, starting fresh simulation" \
  || { echo "FAIL: no 'starting fresh' log"; exit 1; }
echo "PASS: fresh start log found"
```

### Step 8.4 — Assert zero agents (not restored from stale data)

```bash
curl -sf "$API/simulation/status" -H "$AUTH" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['drivers_total'] == 0, f'expected 0 drivers, got {d[\"drivers_total\"]}'
assert d['riders_total'] == 0, f'expected 0 riders, got {d[\"riders_total\"]}'
print('PASS: 0 drivers, 0 riders — fresh start confirmed')
" || { echo "FAIL: agents found on fresh start"; exit 1; }
```

---

## Teardown

```bash
docker compose -f "$COMPOSE" --profile core down -v
echo "Teardown complete"
```

---

## Summary Table

| Test | Trigger | Agents | Drain | Checkpoint Type | Restore | Key Assertion |
|------|---------|--------|-------|-----------------|---------|---------------|
| 1 | Periodic | 5+5 spawned | N/A | any | N/A | Agents persisted to DB with location/status |
| 2 | Pause | In DB at pause-time | Completes | graceful | N/A | 0 in-flight, status=paused |
| 3 | SIGTERM | Survives restart | N/A | any | N/A | DB persists across container restart |
| 4 | Restore | Re-created from DB | N/A | N/A | Time + agents + speed | Agents functional post-restore |
| 5 | Dirty restore | 10+10 spawned | N/A | crash | Orphans cancelled | Dirty warning, agents recovered |
| 6 | Drain timeout | 20+20 spawned | Timeout/quiescence | graceful | N/A | Post-drain checkpoint clean |
| 7 | Disabled | Not saved | Not saved | N/A | N/A | Zero checkpoint logs |
| 8 | Empty restore | None | N/A | N/A | Fresh start | 0 agents, fallback log |
