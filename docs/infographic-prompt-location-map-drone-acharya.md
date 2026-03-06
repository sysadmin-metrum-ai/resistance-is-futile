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
Place the anchors where they will stay for the flight volume. Follow these steps:

1. **Position each anchor** at its final location (corners, walls, or stands). Do not move them after you start measuring.
2. **Check line of sight:** Each anchor must see at least 3–4 other anchors (no large obstructions in between).
3. **Avoid collinearity:** The first three nodes (N0, N1, N2) must form a **triangle** in 3D, not a straight line. If N0, N1, N2 are collinear, drone-acharya will fail. Choose which physical anchor is N0, which is N1, which is N2, so that they are not in a line.
4. **Use 3D spread:** Place some anchors at different heights (e.g. ceiling, table, floor) to improve Z-axis accuracy. The flight volume should sit inside the volume spanned by the anchors, with some margin.
5. **Assign node IDs:** Decide which anchor is N0, N1, N2, … (e.g. N0–N5 for six nodes). Write this down. The distance table rows will use these labels. Node order affects the computed frame; you can later align to North with `--rotate-ned` and `--offset-*` if needed.
6. **Record anchor hardware IDs** if your nodes have printed IDs (0–7); you will need them when programming.

**Visual suggestion:**  
A simple top-down or isometric sketch of a room or space with 4–6 nodes placed at corners/edges, with “N0”, “N1”, … labels. Optional: a note “N0–N1–N2 form a triangle.”

---

## Section 4: Using the Laser Distance Meter to Measure All Pairs

**Headline:** Measure Every Pairwise Distance with the Laser

**Body:**  
You need the distance between every pair of nodes. For N nodes, that is **N×(N−1)/2** measurements (e.g. 4 nodes → 6 pairs, 6 nodes → 15 pairs). Follow these steps:

1. **List the pairs** you need (or generate the template first — Step 1 — and use it as your checklist). Each pair (Ni, Nj) with i < j is measured once.
2. **Set the laser unit to meters.** If your device uses feet, convert (1 ft = 0.3048 m). All values for drone-acharya must be in meters.
3. **For each pair:** Stand at the "from" node (e.g. N0). Hold the laser firmly against that anchor. Aim at the **center** of the "to" anchor (e.g. N1). Record the distance and write it in the template in the correct cell (row = from, column = to; columns are in reverse order N3, N2, N1 for 4 nodes).
4. **Center-to-center:** Measure between the centers of the two nodes, not edge-to-edge.
5. **Re-measure if unsure:** For critical pairs (especially N0–N1, N0–N2, N1–N2), measure twice. If the two readings differ by more than ~2 cm, measure a third time.
6. **Do not move anchors** between measurements. The geometry must stay fixed for all N×(N−1)/2 values.

These distances are the only input drone-acharya needs to compute 3D coordinates.

**Visual suggestion:**  
Illustration of a person with a laser meter at one node, beam pointing to another node, with a callout “distance in meters” and “center to center.” Optional: a small table showing “6 nodes → 15 pairs.”

---

## Section 5: Generate the Measurement Template with drone-acharya

**Headline:** Step 1 — Generate a Template

**Body:**  
Before filling in distances, generate an empty template so you know exactly which cells to fill. Steps: (1) Open a terminal. (2) Run drone-acharya’s template command with the number of nodes (4–8). Example for 6 nodes, CSV format:

```text
drone-acharya template --nodes 6 --format csv -o distances.csv
```
3. **Open the generated file** (e.g. `distances.csv`) and confirm the header row: first column "from/to", then columns in **reverse order** (e.g. N5, N4, N3, N2, N1 for 6 nodes). If you see N1, N2, N3, the order is wrong — use the file as generated.

This creates a file (e.g. `distances.csv`) with a header row and one row per node. **Column order is critical and must be shown on the infographic.**

**Node order in columns (reverse order):** The header row is **"from/to"** followed by node labels in **reverse numerical order**: N(n−1), N(n−2), …, N1. For 4 nodes that is: **from/to, N3, N2, N1**. For 6 nodes: **from/to, N5, N4, N3, N2, N1**. Not N1, N2, N3 — the order is reversed on purpose. Each data row then has only as many cells as needed: row N0 has distances to N3, N2, N1 (three cells); row N1 has distances to N3, N2 (two cells); row N2 has distance to N3 (one cell); row N3 has no distance cells. So every pair (Ni, Nj) with i < j appears exactly once, in row Ni under column Nj. No duplicate entries, no empty cells in the wrong place — easier and less error-prone to enter.

**Example template for 4 nodes (exact layout to show):**

| from/to | N3 | N2 | N1 |
|---------|----|----|-----|
| N0      |    |    |     |
| N1      |    |    |     |
| N2      |    |     |     |
| N3      |     |     |     |

Row N0: fill distance N0→N3, N0→N2, N0→N1. Row N1: fill N1→N3, N1→N2. Row N2: fill N2→N3. Row N3: no cells (all pairs already covered).

**Example template for 6 nodes (header only; rows N0…N5 with decreasing cells per row):** Header: **from/to, N5, N4, N3, N2, N1**. Row N0 has 5 cells (to N5…N1), row N1 has 4 cells, …, row N5 has 0 cells.

**Visual suggestion (must appear on infographic):**  
Show the **exact header row** for the chosen node count. For 4 nodes: **from/to | N3 | N2 | N1**. For 6 nodes: **from/to | N5 | N4 | N3 | N2 | N1**. Do not show N1, N2, N3 or N1…N5 — the reverse order is the whole point. Draw a small table with these column headers and row labels N0, N1, … with empty cells (or "fill" placeholders) in the upper triangle only. Add a callout: "Columns in reverse order → one cell per pair, no duplicates." Include the template command in monospace.

---

## Section 6: Enter the Measured Distances into the Template

**Headline:** Step 2 — Enter Distances into the File

**Body:**  
Open the template file (e.g. in a spreadsheet or text editor). Steps:

1. **Leave the header and column order unchanged.** First column "from/to", then **N3, N2, N1** (4 nodes) or **N5, N4, N3, N2, N1** (6 nodes). Do not sort columns.
2. **Fill each empty cell:** row label = "from" node, column header = "to" node. Enter the distance you measured between that pair in meters (e.g. 4.250).
3. **Save the file** as `distances.csv` (or `distances.tsv` if you used TSV format).
4. **Verify count:** for N nodes you must have exactly N×(N−1)/2 numeric values (e.g. 6 nodes → 15 values). Missing or extra cells will cause drone-acharya to report an error.

**Keep the column order exactly as generated:** first column "from/to", then **N3, N2, N1** (for 4 nodes) or **N5, N4, N3, N2, N1** (for 6 nodes). Do not reorder columns to N1, N2, N3 — the reverse order is required. For each empty cell, the row label is the "from" node and the column header is the "to" node: enter the distance you measured between that pair. Use decimal form in meters (e.g. 4.250, 3.000). Save the file (e.g. as `distances.csv` or `distances.tsv`). Double-check: for N nodes you must have exactly N×(N−1)/2 values. Missing or extra values will cause drone-acharya to report an error.

**Example filled table for 4 nodes (exact layout to show):** Row N0: under N3 put d(N0,N3), under N2 put d(N0,N2), under N1 put d(N0,N1). So a filled row N0 might read: N0, 3.000, 5.000, 4.000 (distances from N0 to N3, N2, N1 in that column order). Row N1: N1, 5.000, 3.000 (N1→N3, N1→N2). Row N2: N2, 4.000 (N2→N3). Row N3: no data cells.

**Visual suggestion (must appear on infographic):**  
Show the same table as Section 5 but **with the column headers clearly visible**: from/to, N3, N2, N1 (or N5…N1 for 6 nodes). Fill in example numbers in the upper-triangle cells (e.g. 3.000, 5.000, 4.000 in the first row). Add a short note: "Column order = reverse (N3, N2, N1). Row = from, column = to. Save as distances.csv".

---

## Section 7: Run drone-acharya Solve to Get 3D Coordinates

**Headline:** Step 3 — Solve for 3D Coordinates

**Body:**  
Run drone-acharya solve on the filled file. For use with Crazyflie and the Loco Positioning deck, you must output coordinates in **NED** (North-East-Down). Steps:

1. **Run the solve command** (see below). Use `--crazyflie --z-down --validate` so output is NED and you get a validation table.
2. **Check the validation table** in the output: recomputed vs measured distances. Aim for &lt; 5% error per pair; if any pair has large error, re-measure that distance.
3. **Copy or save the output** to a file named e.g. `anchors.py` or `anchors.json` for the push-anchors script. The output is a Python dict mapping node ID to (x, y, z).

The recommended command is:

```text
drone-acharya solve distances.csv --crazyflie --z-down --validate
```

- `--crazyflie` emits a Python dict format suitable for the push-anchors script.
- `--z-down` flips the Z-axis so that positive Z is down (NED), as required by Crazyflie/LPS.
- `--validate` prints a table comparing measured distances to distances recomputed from the solution; use it to catch bad measurements (aim for &lt; 5% error per pair).

The output will look like:

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

## Section 7a: Coordinate Frame — Rotations and Translations

**Headline:** When to Rotate or Translate the Coordinate Frame

**Body:**  
Crazyflie and the Loco Positioning system expect all positions in **NED** (North-East-Down): X = North, Y = East, Z = Down. Anchor positions and drone position are in this same world frame. drone-acharya does not know North — it builds a frame from your measurements (X = N0→N1, etc.), so that frame can be rotated relative to the world. If you don't rotate, the map is twisted: the drone's "North" and the room's North don't match. **`--rotate-ned`** aligns the computed frame with NED so the output matches what Crazyflie expects.

Use rotation/translation when the survey frame is not aligned with North (e.g. room X-axis is not North) or when the origin of your survey is not the venue origin.

- **`--rotate-ned <degrees>`** — Clockwise rotation from acharya X-axis to North (degrees).
- **`--offset-x`**, **`--offset-y`**, **`--offset-z`** — Translation in meters (e.g. move origin). Use with `--z-down` for NED output.

**Example combined command:**

```text
drone-acharya solve distances.csv --crazyflie --z-down --rotate-ned 45 --offset-x 10 --offset-z 1.5 --validate
```

(rotate 45° to align with North, shift origin by 10 m in X and 1.5 m in Z; see tools/drone-acharya/COORDINATES.md.)

**Visual suggestion:**  
A small callout or diagram: "Survey frame → rotate (--rotate-ned) → translate (--offset-*) → NED (--z-down)" or a box listing the four flags with the example command.

---

## Section 8: Push Coordinates to the Loco Positioning Nodes

**Headline:** Step 4 — Program the Anchors

**Body:**  
The anchors must be told their 3D positions. Steps:

1. **Plug in the Crazyradio** (USB dongle) to the laptop.
2. **Power on all anchors** and ensure they are in range (typically within tens of meters of the Crazyradio for programming).
3. **Run the push-anchors script** with the coordinate file you saved (e.g. `anchors.py`). The script sends each anchor's (x, y, z) to the corresponding Loco Positioning node via LPP.
4. **Check the script output:** it should report success per anchor. If some fail, check USB, radio address (e.g. `0/80/2M`), and that anchors are on and not too far.

Command to run:

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
With the map loaded into the anchors, verify that the Crazyflie (with Loco Positioning deck) reports positions that match the intended geometry. Steps:

1. **Ensure the Drone API is running** (e.g. the backend that serves the mission/position endpoints). The verify-position script calls this API to command the drone and read position.
2. **Run the verify-position script** with a pattern (e.g. square) and a size and error threshold. The drone will fly the pattern; the script records reported positions and compares them to the expected path.
3. **Check the result:** the script computes RMS error. If RMS error ≤ threshold (e.g. 0.2 m), the test **passes**. If it fails, re-check anchor positions, coverage (drone should see 3–4+ anchors), and for interference (metal, obstacles). Other patterns (circle, figure-8) are available; see script help.

Example command:

```text
python scripts/verify-position.py --pattern square --size 1.0 --threshold 0.2
```

The drone flies a square of side 1.0 m while the system records position estimates from LPS. The script computes the RMS error between expected and actual positions. If RMS error is at or below the threshold (e.g. 0.2 m = 20 cm), the test passes. If it fails, re-check anchor positions, coverage (drone should see 3–4+ anchors), and for interference (metal, obstacles). Other patterns (e.g. circle, figure-8) are available; see script help. This step confirms that the location map you built with the laser and drone-acharya is correctly applied in the Crazyflie Loco Positioning system.

**Visual suggestion:**  
A small drone icon flying a square path, with “expected path” vs “reported positions” and a “RMS error ≤ threshold = pass” callout. Optional: “Positioning test = final check.”

---

## Section 10: Summary Flow (bottom of infographic)

**Headline:** End-to-End Flow

**Summary (use as numbered flow on the infographic; sub-bullets can be shortened for layout):**

1. **Place anchors; assign node IDs.** Position anchors, ensure N0–N1–N2 form a triangle, assign N0…N(n−1), record hardware IDs.
2. **Generate template.** `drone-acharya template --nodes <N> -o distances.csv`. Open file and confirm header: from/to, then N(n−1)…N1 (reverse order).
3. **Measure and enter distances.** For each pair (Ni, Nj), measure with laser (meters), center-to-center. Fill template: row = from, column = to. Save as distances.csv. Verify N×(N−1)/2 values.
4. **Solve for NED coordinates.** `drone-acharya solve distances.csv --crazyflie --z-down --validate`. Check validation table; save output to anchors.py. Add `--rotate-ned` and/or `--offset-x/y/z` if survey frame not aligned with North or origin.
5. **Program anchors.** Plug Crazyradio; power anchors; `python scripts/push-anchors.py --anchors anchors.py --radio 0/80/2M`; confirm success per anchor.
6. **Run positioning test.** Drone API running; `python scripts/verify-position.py --pattern square --size 1.0 --threshold 0.2`; pass if RMS error ≤ threshold.

**Visual suggestion:**  
Numbered boxes or a simple flowchart (1 → 2 → 3 → 4 → 5 → 6) with the one-line text inside or beside each box.

---

## Design Constraints and Notes for the Designer

- **Length:** The written content above is more than 1500 words; the infographic itself should distill it into headings, short bullets, and key commands. Use the full text as the source; do not put 1500 words on the graphic.
- **Hierarchy:** Clear section numbers (1–5 or 1–6) and bold section titles so the eye can jump. Within each section, use numbered steps (1. 2. 3. …) or bullet sub-steps where the prompt specifies them. Commands and file names in monospace or a distinct style.
- **Accuracy:** Keep technical terms exact: drone-acharya, Crazyflie, Loco Positioning (LPS), NED, `--z-down`, `--validate`, `--rotate-ned`, `--offset-x`, `--offset-y`, `--offset-z`, push-anchors.py, verify-position.py, distances in meters, N×(N−1)/2 pairs, template columns in reverse order.
- **No branding beyond the tools:** No need to invent logos; focus on clarity and correctness.
- **Single page or scroll:** The infographic should work as one poster or one vertically scrollable asset. If space is tight, Section 10 (summary flow) can serve as the minimal “cheat sheet” and Sections 1–9 can be slightly condensed.
- **References:** Optionally add a small “Learn more” line: “drone-acharya: tools/drone-acharya/README.md, COORDINATES.md; Venue survey: docs/venue-survey-procedure.md.”

Use this prompt as the full specification for generating a clean, professional infographic on how to build a location map using a laser distance meter, drone-acharya, and Crazyflie Loco Positioning, from measurement to positioning test.
