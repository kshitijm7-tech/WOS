# RocketRide Adapter (Isolated Integration Point)

The exact RocketRide SDK/API was not available in this build environment, so this folder
defines a small, explicit **interface** (`RocketRideClient`) that the rest of the app codes
against — never a vendor SDK directly. That means dropping in the real integration later
is a one-file change, with zero changes needed in `backend/` or `frontend/`.

## What's here

- `pipeline.py` — the 7-stage contract from the problem statement (`ClaimPipelineInput` in,
  `ClaimPipelineResult` out), stage names, and the orchestration order.
- `adapter.py` — the `RocketRideClient` abstract interface, plus `MockRocketRideClient`, a
  realistic stand-in that runs the same 7 stages using deterministic rules + light
  seeded randomness (no invented "official RocketRide" call syntax).

## Where to connect the real RocketRide SDK

Open `adapter.py` and look for:

```python
# ROCKETRIDE: connect real client here
```

Implement `RealRocketRideClient(RocketRideClient)` there, following whatever the official
RocketRide SDK/API documentation specifies for auth and calls, and swap the instantiation in
`backend/app/services/ai_service.py`:

```python
# from rocketrider.adapter import MockRocketRideClient as RocketRideClient
from rocketrider.adapter import RealRocketRideClient as RocketRideClient
```

Nothing else in the codebase needs to change — `ai_service.py` only depends on the
`RocketRideClient` interface's method signatures, not on any particular vendor's request
format.
