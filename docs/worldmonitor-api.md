# WorldMonitor developer API (for corridor map live layers — option 3)

Reference for wiring **live** layers (flights, military, cable health, ship
traffic, conflict, etc.) into FORSYT later. Option 1 (static pipelines +
undersea cables) is already shipped on the SVG map and needs none of this.

## Access

- **Base URL:** `https://api.worldmonitor.app/api/{domain}/v1/{rpc}`
- **Auth:** none. Public endpoints need **no API key** and have **no usage fees**.
- **License:** WorldMonitor is AGPL-3.0 open source — you can also self-host the
  whole stack instead of hitting the public API.
- **Source:** https://github.com/aadij1905/worldmonitor (mirror of koala73/worldmonitor)
- **Specs:** auto-generated OpenAPI per service in the repo under `docs/api/`
  (`AviationService.openapi.json`, `MilitaryService…`, `Infrastructure…`, etc.)

Example:

```bash
curl https://api.worldmonitor.app/api/conflict/v1/events
curl https://api.worldmonitor.app/api/market/v1/quotes
```

## Endpoints relevant to the corridor map

| Layer we'd add | Domain / RPC |
|---|---|
| Undersea cable **health** (vs our static geometry) | `infrastructure/v1/get-cable-health` |
| Internet outages | `infrastructure/v1/list-internet-outages` |
| Civil flights (airport ops / delays) | `aviation/v1/list-airport-flights`, `aviation/v1/list-airport-delays` |
| Track a specific aircraft | `aviation/v1/track-aircraft` |
| Military flights (ADS-B / Wingbits) | `military/v1/list-military-flights`, `military/v1/get-wingbits-live-flight` |
| Military bases | `military/v1/list-military-bases` |
| Naval / fleet posture | `military/v1/get-theater-posture`, `military/v1/get-usni-fleet-report` |
| Ship traffic / vessel snapshot | `maritime/v1/get-vessel-snapshot` |
| Navigational warnings (chokepoints) | `maritime/v1/list-navigational-warnings` |
| Conflict events (corridor risk context) | `conflict/v1/events` |

## How we'd plug it in (when/if we move to option 3)

1. **Proxy through our backend**, don't call it from the browser — one server
   route per layer that fetches, trims to the map's bbox, and caches (these feeds
   are large and update on their own cadence). Mirrors how `page_bundles.py`
   already wraps upstreams.
2. **Switch the engine.** Live ADS-B/AIS = thousands of moving features; the
   current SVG/d3 map can't animate that. That's the trigger to adopt
   `maplibre-gl` + `deck.gl` (WorldMonitor's stack) for an "Explore" map mode.
3. Feed each proxied layer into a deck.gl layer; keep the toggle panel we already
   built ([MapLayerPanel.tsx](../frontend/src/components/MapLayerPanel.tsx)).

Rule of thumb: **static geometry → SVG is fine** (what we did). **Live, dense,
moving → deck.gl.**
