# Phase 3: Demo Venue Setup - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable rapid venue setup for demo deployment. Document site survey procedure, integrate with drone-acharya for anchor coordinate generation, and push coordinates to Loco Positioning nodes.

</domain>

<decisions>
## Implementation Decisions

### Survey Method
- **Manual measurement** with laser "tape" (distance meter)
- Measure distances between anchor positions manually

### Anchor Generation
- **Interactive input** - user enters measurements, drone-acharya computes coordinates
- CLI-based workflow for entering distance data

### Node Programming
- **cfloader CLI** - push coordinates to Loco Positioning nodes via Crazyradio
- Standard tool workflow

### Verification
- **Test flight pattern** - small square pattern to verify positioning accuracy
- Fly pattern, verify position readout matches expected

</decisions>

<specifics>
## Specific Ideas

- "manual measurement with laser 'tape' (distance meter)"
- Use drone-acharya tool for coordinate generation

</specifics>

<deferred>
## Deferred Ideas

- RTK GPS for survey - future improvement
- Automated verification scripts - future phase

</deferred>

---

*Phase: 03-demo-venue-setup*
*Context gathered: 2026-02-28*
