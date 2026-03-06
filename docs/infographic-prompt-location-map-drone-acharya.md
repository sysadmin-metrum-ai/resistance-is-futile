# Text Prompt: Infographic — Build a Location Map with drone-acharya and Crazyflie Loco Positioning

**Use this prompt to generate a clean, professional infographic.** Minimum 1500 words. The prompt is written so a designer or an AI infographic tool can produce a single, well-structured visual guide.

---

## Infographic Brief

**Title (to appear on the graphic):**  
*How to Build a Location Map for Crazyflie Loco Positioning — From Laser Measurements to Positioning Test*

**Audience:**  
Operators and engineers who deploy Loco Positioning (LPS) anchor nodes at a venue and need to create a 3D “map” of anchor positions for Crazyflie drones with a Loco Positioning deck.

**Tone and style:**  
Clean, professional, technical but accessible. Use a consistent color palette (e.g. neutral background with one or two accent colors for steps and callouts). Typography should be highly legible; support both a quick scan (headings, numbers) and short explanatory text. Avoid decorative clutter. Icons or simple illustrations for equipment, nodes, and flow are encouraged.

**Format:**  
Single infographic (poster or long-scroll). Sections should be clearly numbered or sequenced (e.g. 1 → 2 → 3 …) so the reader can follow the workflow from start to finish.

---

## Section 1: Purpose and Outcome (top of infographic)

**Headline:** Build a 3D Location Map for Your Venue

**Body (use concisely on the graphic):**  
When you deploy a Crazyflie swarm with a Loco Positioning deck at a new venue, the drones need to know where each UWB anchor is in 3D space. This workflow turns simple distance measurements between anchors into a full 3D coordinate map, then loads that map into the anchors and validates it with a positioning test. No manual geometry: you measure distances with a laser meter, enter them into the drone-acharya tool, get coordinates in the correct frame (NED) for Crazyflie, push those coordinates to the Loco Positioning nodes, and run a test flight to verify accuracy.

**Visual suggestion:**  
A simple diagram showing: “Venue with anchors” → “Distance measurements” → “drone-acharya” → “3D coordinates” → “Anchors programmed” → “Drone flying with LPS.” Keep it to one row or a gentle flow.

---

## Section 2: Equipment Needed

**Headline:** Equipment

**List (show as icons + short labels if possible):**

1. **Laser distance meter** — For measuring distances between anchor nodes. Prefer accuracy on the order of ±2 mm. All distances must be in meters.
2. **Loco Positioning nodes (4–8 anchors)** — UWB anchors; recommend at least 6 for redundancy. Each node has an ID (e.g. 0–7).
3. **Crazyradio (USB dongle)** — 2.4 GHz radio for talking to the anchors when programming their positions. Typical range on the order of 100 m.
4. **Laptop or workstation** — To run drone-acharya (Go CLI), push-anchors script (Python), and verify-position script. Must have USB for Crazyradio.
5. **Measuring tape (optional)** — Backup for checking laser readings or vertical (height) measurements.

**Visual suggestion:**  
One small icon or illustration per item, with the name and one-line purpose. Align in a row or a 2×3 grid.

---

## Section 3: Anchor Placement and Node Order

**Headline:** Place Anchors and Choose Node Order

**Body:**  
Place the anchors where they will stay for the flight volume. Each anchor must have clear line of sight to at least 3–4 other anchors. Avoid straight lines: the first three nodes (N0, N1, N2) must form a triangle in 3D; if they are collinear, drone-acharya will fail. Distribute anchors in 3D (different heights) to improve Z-axis accuracy. The flight volume should sit inside the volume spanned by the anchors, with some margin. Record each anchor’s ID; you will assign IDs to rows in the distance table (e.g. N0, N1, …, N5 for six nodes). Node order affects the computed frame; you can later align to North with drone-acharya’s `--rotate-ned` and `--offset-*` if needed.

**Visual suggestion:**  
A simple top-down or isometric sketch of a room or space with 4–6 nodes placed at corners/edges, with “N0”, “N1”, … labels. Optional: a note “N0–N1–N2 form a triangle.”

---

## Section 4: Using the Laser Distance Meter to Measure All Pairs

**Headline:** Measure Every Pairwise Distance with the Laser

**Body:**  
You need the distance between every pair of nodes. For N nodes, that is N×(N−1)/2 measurements (e.g. 6 nodes → 15 distances). Use the laser distance meter: hold it firmly against one anchor (or a fixed reference point on it), aim at the center of the other anchor, and record the reading in **meters**. If your device uses feet, convert (1 ft = 0.3048 m). Measure center-to-center, not edge-to-edge. For critical pairs, measure twice; if the difference is larger than about 2 cm, measure again. Do not move anchors between measurements; the geometry must stay fixed. These distances are the only input drone-acharya needs to compute 3D coordinates.

**Visual suggestion:**  
Illustration of a person with a laser meter at one node, beam pointing to another node, with a callout “distance in meters” and “center to center.” Optional: a small table showing “6 nodes → 15 pairs.”

---

## Section 5: Generate the Measurement Template with drone-acharya

**Headline:** Step 1 — Generate a Template

**Body:**  
Before filling in distances, generate an empty template so you know exactly which cells to fill. Run drone-acharya’s template command with the number of nodes (4–8). Example for 6 nodes, CSV format:

```text
drone-acharya template --nodes 6 --format csv -o distances.csv
```

This creates a file (e.g. `distances.csv`) with a header row and one row per node. Columns are “from/to” and then the other nodes (e.g. N5, N4, N3, N2, N1). Each cell is the distance from the row node to the column node. You only fill the upper triangle (each pair once). The template avoids duplicate entries and reduces mistakes.

**Visual suggestion:**  
A small schematic table: rows N0…N5, columns “from/to”, N5, N4, …, with some cells shaded “fill here” and a snippet of the command in a code block or monospace font.

---

## Section 6: Enter the Measured Distances into the Template

**Headline:** Step 2 — Enter Distances into the File

**Body:**  
Open the template file (e.g. in a spreadsheet or text editor). For each empty cell, insert the distance you measured between the row node and the column node. Use decimal form in meters (e.g. 4.250, 3.000). Save the file (e.g. as `distances.csv` or `distances.tsv`). Double-check: for N nodes you must have exactly N×(N−1)/2 values. Missing or extra values will cause drone-acharya to report an error. A typical filled row might look like: N0, 3.000, 5.000, 4.000 (distances from N0 to N3, N2, N1).

**Visual suggestion:**  
Same table as in Section 5 but with example numbers in the cells (e.g. 3.000, 5.000, 4.000) and a “Save as distances.csv” note.

---

## Section 7: Run drone-acharya Solve to Get 3D Coordinates

**Headline:** Step 3 — Solve for 3D Coordinates

**Body:**  
Run drone-acharya solve on the filled file. For use with Crazyflie and the Loco Positioning deck, you must output coordinates in **NED** (North-East-Down). The recommended command is:

```text
drone-acharya solve distances.csv --crazyflie --z-down --validate
```

- `--crazyflie` emits a Python dict format suitable for the push-anchors script.
- `--z-down` flips the Z-axis so that positive Z is down (NED), as required by Crazyflie/LPS.
- `--validate` prints a table comparing measured distances to distances recomputed from the solution; use it to catch bad measurements (aim for &lt; 5% error per pair).

If your survey frame is not aligned with North, add `--rotate-ned &lt;degrees&gt;` and/or `--offset-x`, `--offset-y`, `--offset-z` (see drone-acharya COORDINATES.md). The output will look like:

```text
anchor_positions = {
    0: (0.00, 0.00, 0.00),
    1: (4.00, 0.00, 0.00),
    2: (4.00, 3.00, 0.00),
    ...
}
```

Save this to a file (e.g. `anchors.py` or `anchors.json`) for the next step.

**Visual suggestion:**  
Command in a terminal-style box; next to it a small “output” snippet (anchor_positions dict). Optional: a one-line note “NED = North, East, Down (Z positive = down).”

---

## Section 8: Push Coordinates to the Loco Positioning Nodes

**Headline:** Step 4 — Program the Anchors

**Body:**  
The anchors must be told their 3D positions. Use the push-anchors script with the coordinate file you saved. Plug in the Crazyradio, ensure the anchors are powered and in range, then run:

```text
python scripts/push-anchors.py --anchors anchors.py --radio 0/80/2M
```

The script sends each anchor’s (x, y, z) to the corresponding Loco Positioning node via the Loco Positioning Protocol (LPP). Coordinates must be in NED (hence the importance of using `--z-down` when generating the file). After a successful run, all listed anchors are programmed with the map you computed. If the script reports failures, check USB/Crazyradio, radio address, and that anchors are on and not too far.

**Visual suggestion:**  
Laptop with Crazyradio dongle, radio waves or link to anchors, and a short command. Optional: “Anchors now know their (x,y,z) in NED.”

---

## Section 9: Run a Positioning Test with the Crazyflie

**Headline:** Step 5 — Verify with a Positioning Test

**Body:**  
With the map loaded into the anchors, verify that the Crazyflie (with Loco Positioning deck) reports positions that match the intended geometry. Use the verify-position script to fly a predefined pattern and compare reported positions to expected positions. Example:

```text
python scripts/verify-position.py --pattern square --size 1.0 --threshold 0.2
```

The drone flies a square of side 1.0 m while the system records position estimates from LPS. The script computes the RMS error between expected and actual positions. If RMS error is at or below the threshold (e.g. 0.2 m = 20 cm), the test passes. If it fails, re-check anchor positions, coverage (drone should see 3–4+ anchors), and for interference (metal, obstacles). Other patterns (e.g. circle, figure-8) are available; see script help. This step confirms that the location map you built with the laser and drone-acharya is correctly applied in the Crazyflie Loco Positioning system.

**Visual suggestion:**  
A small drone icon flying a square path, with “expected path” vs “reported positions” and a “RMS error ≤ threshold = pass” callout. Optional: “Positioning test = final check.”

---

## Section 10: Summary Flow (bottom of infographic)

**Headline:** End-to-End Flow

**One-line summary for each step (can be a simple vertical or horizontal flow):**

1. Place anchors; assign node IDs (N0, N1, …).
2. Generate template: `drone-acharya template --nodes &lt;N&gt; -o distances.csv`.
3. Measure all pairwise distances with the laser (meters); enter into template.
4. Solve for NED coordinates: `drone-acharya solve distances.csv --crazyflie --z-down --validate`; save output (e.g. `anchors.py`).
5. Program anchors: `python scripts/push-anchors.py --anchors anchors.py --radio 0/80/2M`.
6. Run positioning test: `python scripts/verify-position.py --pattern square --size 1.0 --threshold 0.2`.

**Visual suggestion:**  
Numbered boxes or a simple flowchart (1 → 2 → 3 → 4 → 5 → 6) with the one-line text inside or beside each box.

---

## Design Constraints and Notes for the Designer

- **Length:** The written content above is more than 1500 words; the infographic itself should distill it into headings, short bullets, and key commands. Use the full text as the source; do not put 1500 words on the graphic.
- **Hierarchy:** Clear section numbers (1–5 or 1–6) and bold section titles so the eye can jump. Commands and file names in monospace or a distinct style.
- **Accuracy:** Keep technical terms exact: drone-acharya, Crazyflie, Loco Positioning (LPS), NED, `--z-down`, `--validate`, push-anchors.py, verify-position.py, distances in meters, N×(N−1)/2 pairs.
- **No branding beyond the tools:** No need to invent logos; focus on clarity and correctness.
- **Single page or scroll:** The infographic should work as one poster or one vertically scrollable asset. If space is tight, Section 10 (summary flow) can serve as the minimal “cheat sheet” and Sections 1–9 can be slightly condensed.
- **References:** Optionally add a small “Learn more” line: “drone-acharya: tools/drone-acharya/README.md, COORDINATES.md; Venue survey: docs/venue-survey-procedure.md.”

Use this prompt as the full specification for generating a clean, professional infographic on how to build a location map using a laser distance meter, drone-acharya, and Crazyflie Loco Positioning, from measurement to positioning test.
