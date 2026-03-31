# AI-Deck Streaming Plan

This repo now uses a production-shaped camera abstraction instead of a single placeholder call site.

## Goals

- Support up to 3 simultaneous drone video feeds for the demo.
- Keep flight control on Crazyradio and image/video transport on AI-deck WiFi.
- Expose mission-facing APIs for:
  - registering a drone feed
  - starting/stopping a stream session
  - capturing stills during a mission
  - listing active sessions and captured artifacts

## Current backend model

- `placeholder`
  - safe fallback when hardware transport is unavailable
  - creates deterministic placeholder capture artifacts
  - exposes a placeholder stream URL so the rest of the mission stack can still exercise the flow
- `aideck-wifi`
  - shaped for real AI-deck usage
  - accepts per-drone `snapshot_url` and `stream_url`
  - can fetch snapshots over HTTP when available
  - does not pretend to proxy unvalidated live video transport in-process

## Why this split exists

Live AI-deck transport is hardware-dependent and must be validated on the actual network and drone firmware. The software stack should still:

- know which drones have camera feeds
- enforce a max concurrent stream count
- attach stream sessions to missions
- degrade gracefully when a feed is missing

## API flow

1. Register each drone feed via `/api/images/feeds/register`
2. Start one session per participating drone via `/api/images/sessions/start`
3. Use the session during mission execution for still captures via `/api/images/capture`
4. Surface session state to the UI via `/api/images/sessions` or `/api/images/streams/{drone_id}`
5. Stop sessions at mission end via `/api/images/sessions/{session_id}/stop`

## Demo recommendation

- Configure 3 AI-decks to connect to the venue AP
- Register one `aideck-wifi` feed per demo drone
- Keep stream frame rate and resolution conservative
- Treat still capture as required and live video as best-effort
- If one feed fails, continue the mission with the remaining feeds and record the failure in operator logs
