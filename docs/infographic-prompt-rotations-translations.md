# Text Prompt: Infographic — Why, When, and How to Use Rotations and Translations (drone-acharya → Crazyflie NED)

**Use this prompt to generate a detailed, standalone infographic** on coordinate-frame rotations and translations when building a location map with drone-acharya for Crazyflie Loco Positioning. The infographic should answer: **Why** does this matter? **When** do I need to rotate or translate? **How** do I do it?

---

## Infographic Brief

**Title (to appear on the graphic):**  
*Coordinate Frame: Rotations and Translations — From Survey to Crazyflie NED*

**Audience:**  
Operators and engineers who use drone-acharya to compute anchor coordinates and need to align the output with Crazyflie’s expected frame (NED). Some familiarity with “survey frame” vs “world frame” is helpful but not required.

**Tone and style:**  
Technical but clear. Use diagrams to show two frames (survey vs NED), the effect of rotation (one arrow twisting to North), and the effect of translation (origin shifting). Minimal text on the graphic; detailed text here is for the designer to distill into labels and short bullets.

**Format:**  
Single infographic (poster or long-scroll). Structure: **Why** → **When** → **How** (with **Z-flip** and **order of operations** as part of How). Optionally end with a quick-reference box of flags and one example command.

---

## Section 1: Why Rotations and Translations Matter

**Headline:** Why Can’t I Use the Raw drone-acharya Output?

**Body:**  
Crazyflie and the Loco Positioning system expect all positions in a single, consistent frame: **NED (North-East-Down)**. In NED, X = North, Y = East, Z = Down (positive Z is down; “up” is negative Z). The drone’s reported position and the anchor positions you program are all in this world frame. Waypoints, behaviors, and logs assume “forward” is North and “up” is negative Z.

drone-acharya does **not** know North or your venue origin. It only knows the distances you measured. It builds a coordinate frame from those measurements: it puts N0 at the origin, N1 on the X-axis, and N2 in the XY-plane. So the **X-axis of the acharya output is simply the direction from N0 to N1** — whatever that was in your room (e.g. along a wall, at 45° to the window). The **Z-axis** is “up” from the plane of the first three nodes (positive = above that plane), which is the opposite of NED’s Z (where positive = down).

If you use the raw acharya output without transformation:

- **Wrong orientation:** The drone’s “North” and the room’s North don’t match. A command like “fly 1 m North” will move the drone in the direction of your survey X-axis, not geographic North. The map is “twisted” relative to the world.
- **Wrong Z sign:** In acharya, positive Z is up; in NED, positive Z is down. Using raw Z as anchor height would invert altitude for Crazyflie.

So you **must** transform the acharya output into NED (and optionally move the origin) so that the coordinates you push to the anchors and the frame Crazyflie uses are the same. Rotations align the horizontal axes with North/East; translations move the origin; the Z-flip converts “Z up” to “Z down.”

**Visual suggestion:**  
Side-by-side or overlay: (1) “Survey frame” — a 2D or 3D sketch with X along a wall and Z up; (2) “Crazyflie NED” — same space with X = North, Z down. Label: “Without transform: map twisted; drone North ≠ room North.” Then: “With transform: X→North, Z→Down, origin optional.”

---

## Section 2: When to Use Rotation (`--rotate-ned`)

**Headline:** When Do I Need to Rotate?

**Body:**  
Use **rotation** when the **survey frame is not aligned with North**. That means: the direction you used as “X” when measuring (the line from N0 to N1) is not geographic North (magnetic or true).

- **You need rotation if:** You measured with the room in an arbitrary orientation (e.g. N0–N1 along a wall that doesn’t face North), and you want the final map to have X = North so that Crazyflie’s “forward” and “North” match the real world.
- **You can skip rotation if:** You measured with NED in mind (e.g. you aligned N0–N1 with a compass so it points North). Then the acharya X-axis is already North; use `--rotate-ned 0` or omit it.

**How much to rotate:** The angle is the **clockwise** rotation from the acharya X-axis to North (in degrees). Measure with a compass at N0: how many degrees clockwise from N0→N1 to North?

**Concrete examples (rotation only):**

| When | Survey X (N0→N1) points… | Clockwise from X to North | Command |
|------|---------------------------|----------------------------|---------|
| East wall | East (90° from North) | 270° | `--rotate-ned 270` |
| North-east diagonal | 45° east of North | 315° | `--rotate-ned 315` |
| North wall | Already North | 0° | omit or `--rotate-ned 0` |
| South wall | South (180° from North) | 180° | `--rotate-ned 180` |

**Example (rotation only):** N0 and N1 are along the east wall. Survey X points East. North is 270° clockwise from East. Use: `drone-acharya solve distances.csv --crazyflie --z-down --rotate-ned 270 --validate` (no translation).

**Visual suggestion:**  
Top-down diagram: a rectangle (room) with an arrow “Survey X (N0→N1)” along one wall. A compass rose showing North. Show the angle (e.g. 45°) from Survey X to North with a curved arrow labeled “clockwise rotation to North.” Callout: “--rotate-ned 45” when that angle is 45°.

---

## Section 3: When to Use Translation (`--offset-x`, `--offset-y`, `--offset-z`)

**Headline:** When Do I Need to Translate?

**Body:**  
Use **translation** when the **origin of your survey is not the venue origin** you want for Crazyflie. drone-acharya puts N0 at (0, 0, 0). If you want the world origin to be somewhere else (e.g. a corner of the building, or a point on the floor under a specific marker), you need to shift all coordinates by a constant offset.

- **You need translation if:** You want anchor/drone coordinates relative to a different origin (e.g. “10 m East and 2 m up from N0”). Then apply `--offset-x`, `--offset-y`, `--offset-z` in meters. Positive offset moves the acharya origin in the **positive** direction of each axis; after applying rotation and Z-flip, the same offsets are applied in NED (positive X = North, positive Z = down).
- **You can skip translation if:** N0 is already your desired venue origin.

**Units:** All offsets are in **meters**. Offsets are applied in NED (after rotation and Z-flip): +X = North, +Y = East, +Z = down.

**Concrete examples (translation only; assume already rotated and Z-down):**

| When | Desired origin is… | Offset from N0 (NED) | Command |
|------|--------------------|----------------------|---------|
| Center of room | 2.5 m North, 2 m East of N0 | +2.5 X, +2 Y | `--offset-x 2.5 --offset-y 2` |
| Floor at Z=0 | Floor 1.5 m below N0 (NED +Z = down) | +1.5 Z | `--offset-z 1.5` |
| 10 m North of N0 | 10 m North | +10 X | `--offset-x 10` |
| N0 is origin | Same as N0 | none | omit --offset-* |

**Example (translation only):** N0 at one corner of a 5 m × 4 m room; you want origin at center. Center is 2.5 m North, 2 m East of N0. Use: `drone-acharya solve distances.csv --crazyflie --z-down --offset-x 2.5 --offset-y 2 --validate` (add `--rotate-ned <deg>` if survey X was not North).

**Example (Z offset):** Acharya Z=0 at table height; you want floor at Z=0. Floor is 1.2 m below table. Use: `drone-acharya solve distances.csv --crazyflie --z-down --offset-z 1.2 --validate`.

**Visual suggestion:**  
2D plan: N0 at one corner; desired origin at center. Arrows: "2.5 m North → --offset-x 2.5", "2 m East → --offset-y 2". Include the table or one row.

**When to use both rotation and translation:** Use both when (1) survey X is not North and (2) you want the origin somewhere other than N0. Example: N0 and N1 are along the east wall (use `--rotate-ned 270`), and you want the venue origin at the center of a 5 m × 4 m room (after rotation, center is 2.5 m North and 2 m East of N0: `--offset-x 2.5 --offset-y 2`). Full command: `drone-acharya solve distances.csv --crazyflie --z-down --rotate-ned 270 --offset-x 2.5 --offset-y 2 --validate`. Show this as one combined example on the infographic (e.g. "East wall + center origin → rotate 270° + offset 2.5, 2").

---

## Section 4: When to Use Z-Flip (`--z-down`)

**Headline:** When Do I Need to Flip Z?

**Body:**  
Use **Z-flip** whenever you are producing coordinates for Crazyflie or the Loco Positioning system. In drone-acharya’s raw output, **positive Z is up** (above the measurement plane). In NED, **positive Z is down**. So you must flip the Z-axis so that “up” in the room becomes negative Z in the output (and “down”/ground becomes positive Z if you measure height as positive).

- **Always use `--z-down`** when the output is for Crazyflie/LPS. The only exception would be if you use the output in a pipeline that already applies the flip elsewhere; for the standard workflow (drone-acharya → push-anchors → Crazyflie), use `--z-down`.
- **Effect:** Replaces z by −z (before adding any offset). So a point at height +2 m (acharya) becomes Z = −2 m in NED (2 m above the reference plane).

**Visual suggestion:**  
Two small axes: “Acharya: Z up” (arrow up, “+Z”) and “NED: Z down” (arrow down, “+Z”). Between them: “--z-down flips Z.” Optional: “Always for Crazyflie.”

---

## Section 5: How — Order of Operations and Flags

**Headline:** How to Apply Transformations (Order and Flags)

**Body:**  
The transformation is applied in a fixed order in drone-acharya: **(1) Rotate** around the Z-axis by `--rotate-ned` degrees (clockwise from X to North); **(2) Flip Z** if `--z-down`; **(3) Translate** by `--offset-x`, `--offset-y`, `--offset-z**. So the formula is: first rotate and flip the point, then add the offset. All flags can be combined.

**Flags (must appear on infographic):**

| Flag | Meaning | Default |
|------|---------|---------|
| `--rotate-ned <degrees>` | Clockwise rotation from acharya X-axis to North (degrees) | 0 |
| `--offset-x <meters>` | Add this to X (after rotation) | 0 |
| `--offset-y <meters>` | Add this to Y (after rotation) | 0 |
| `--offset-z <meters>` | Add this to Z (after Z-flip) | 0 |
| `--z-down` | Flip Z (positive up → positive down) | false |

**Example commands (must show on infographic with labels):**

- **Rotation only** (survey X not North; origin stays at N0):  
  `drone-acharya solve distances.csv --crazyflie --z-down --rotate-ned 270 --validate`  
  (e.g. east wall → 270°)
- **Translation only** (survey X already North; move origin):  
  `drone-acharya solve distances.csv --crazyflie --z-down --offset-x 2.5 --offset-y 2 --validate`  
  (e.g. center of room 2.5 m North, 2 m East of N0)
- **Both rotation and translation:**  
  `drone-acharya solve distances.csv --crazyflie --z-down --rotate-ned 270 --offset-x 2.5 --offset-y 2 --validate`  
  (e.g. east wall + origin at center)

**Visual suggestion:**  
Flow diagram: “Acharya coords (X along N0→N1, Z up)” → “1. Rotate (--rotate-ned)” → “2. Z-flip (--z-down)” → “3. Translate (--offset-*)” → “NED coords (X=North, Y=East, Z=Down).” Below: a compact table of the five flags and one full example command in a terminal-style box.

---

## Section 6: Quick Reference and Checklist

**Headline:** Quick Reference

**Body (distill to a small checklist on the graphic):**

- **Why:** Crazyflie expects NED; acharya output is in an arbitrary frame (X = N0→N1, Z up). Without transform: wrong orientation and wrong Z sign.
- **When rotate:** Survey X-axis is not North → use `--rotate-ned <degrees>` (clockwise from X to North). Example: east wall → 270°.
- **When translate:** Origin should not be at N0 → use `--offset-x`, `--offset-y`, `--offset-z` (meters). Example: center of 5×4 m room → --offset-x 2.5 --offset-y 2.
- **When both:** Survey X not North and origin not at N0 → combine both flags (e.g. --rotate-ned 270 --offset-x 2.5 --offset-y 2).
- **When Z-flip:** Always when output is for Crazyflie/LPS → use `--z-down`.
- **How:** Run `drone-acharya solve ... --crazyflie --z-down [--rotate-ned <deg>] [--offset-x/y/z <m>] --validate` and save output for push-anchors.

**Visual suggestion:**  
One small “cheat sheet” box: 4 bullet lines (Why / When rotate / When translate / Z-flip) and one example command. Reference: “Details: tools/drone-acharya/COORDINATES.md”.

---

## Design Constraints and Notes for the Designer

- **Clarity over density:** Prefer one clear diagram per idea (survey vs NED; rotation angle; offset; order of operations) rather than crowding everything into one image.
- **Exact terms:** Use “NED”, “North-East-Down”, “survey frame”, “--rotate-ned”, “--z-down”, “--offset-x”, “--offset-y”, “--offset-z”, “clockwise from X to North”, “meters.”
- **No code logic:** Do not implement the math; only show the flow (rotate → flip → translate) and the flags. The actual math is in the tool.
- **Audience:** Someone who has run drone-acharya at least once and is asking “why is my map twisted?” or “how do I point X to North?” — the infographic should answer that in under a minute of reading.

Use this prompt as the full specification for a detailed infographic on why, when, and how to use rotations and translations (and Z-flip) when building a location map with drone-acharya for Crazyflie Loco Positioning.
