package graph

import (
	"fmt"
	"math"
)

// PickBasis selects three nodes that form a well-conditioned non-collinear
// triangle. If a SurveyFrame is set, uses those nodes as the basis.
func PickBasis(p *Problem) (a, b, c string, err error) {
	if p.SurveyFrame != nil {
		return p.SurveyFrame.XFrom, p.SurveyFrame.XTo, p.SurveyFrame.PlaneNode, nil
	}
	// Find the triple with the largest minimum angle (most equilateral).
	bestScore := -1.0
	for i := 0; i < len(p.Nodes); i++ {
		for j := i + 1; j < len(p.Nodes); j++ {
			dij, ok := p.Dist(p.Nodes[i].ID, p.Nodes[j].ID)
			if !ok || dij < 1e-9 {
				continue
			}
			for k := j + 1; k < len(p.Nodes); k++ {
				dik, ok1 := p.Dist(p.Nodes[i].ID, p.Nodes[k].ID)
				djk, ok2 := p.Dist(p.Nodes[j].ID, p.Nodes[k].ID)
				if !ok1 || !ok2 || dik < 1e-9 || djk < 1e-9 {
					continue
				}
				area := triangleArea(dij, dik, djk)
				if area < 1e-9 {
					continue
				}
				// Score: area / perimeter^2 (maximized for equilateral)
				perim := dij + dik + djk
				score := area / (perim * perim)
				if score > bestScore {
					bestScore = score
					a = p.Nodes[i].ID
					b = p.Nodes[j].ID
					c = p.Nodes[k].ID
				}
			}
		}
	}
	if bestScore < 0 {
		return "", "", "", fmt.Errorf("no valid basis triple found (need 3 mutually connected non-collinear nodes)")
	}
	return a, b, c, nil
}

// InitCoords places the basis triple and BFS-trilaterates the rest.
func InitCoords(p *Problem, basisA, basisB, basisC string) ([]Coord, error) {
	coords := make([]Coord, len(p.Nodes))
	placed := make([]bool, len(p.Nodes))

	idxA := p.nodeIndex[basisA]
	idxB := p.nodeIndex[basisB]
	idxC := p.nodeIndex[basisC]

	dab, _ := p.Dist(basisA, basisB)
	dac, _ := p.Dist(basisA, basisC)
	dbc, _ := p.Dist(basisB, basisC)

	// A at origin
	coords[idxA] = Coord{0, 0, 0}
	placed[idxA] = true

	// B on +X
	coords[idxB] = Coord{dab, 0, 0}
	placed[idxB] = true

	// C in XY plane
	xc := (dab*dab + dac*dac - dbc*dbc) / (2 * dab)
	ycSq := dac*dac - xc*xc
	if ycSq < 0 {
		ycSq = 0
	}
	yc := math.Sqrt(ycSq)
	if yc < 1e-9 {
		return nil, fmt.Errorf("basis nodes %s, %s, %s are collinear", basisA, basisB, basisC)
	}
	coords[idxC] = Coord{xc, yc, 0}
	placed[idxC] = true

	// BFS trilateration for remaining nodes
	queue := []string{basisA, basisB, basisC}
	for len(queue) > 0 {
		cur := queue[0]
		queue = queue[1:]

		for _, nbr := range p.Neighbors(cur) {
			nbrIdx := p.nodeIndex[nbr]
			if placed[nbrIdx] {
				continue
			}
			coord, ok := trilaterate(p, coords, placed, nbr)
			if ok {
				coords[nbrIdx] = coord
				placed[nbrIdx] = true
				queue = append(queue, nbr)
			}
		}
	}

	for i, ok := range placed {
		if !ok {
			return nil, fmt.Errorf("node %d could not be initialized (graph may be disconnected)", i)
		}
	}

	return coords, nil
}

// trilaterate tries to find the position of node id using distances to 3+
// already-placed neighbors. Uses the first 3 placed neighbors with known
// distances, solving the standard 3-sphere intersection.
func trilaterate(p *Problem, coords []Coord, placed []bool, id string) (Coord, bool) {
	type anchor struct {
		coord Coord
		dist  float64
	}
	var anchors []anchor

	for _, nbr := range p.Neighbors(id) {
		nbrIdx := p.nodeIndex[nbr]
		if !placed[nbrIdx] {
			continue
		}
		d, ok := p.Dist(id, nbr)
		if !ok {
			continue
		}
		anchors = append(anchors, anchor{coords[nbrIdx], d})
		if len(anchors) >= 3 {
			break
		}
	}
	if len(anchors) < 3 {
		return Coord{}, false
	}

	return trilaterate3(anchors[0].coord, anchors[0].dist,
		anchors[1].coord, anchors[1].dist,
		anchors[2].coord, anchors[2].dist), true
}

// trilaterate3 computes the intersection of 3 spheres. Returns the solution
// with positive Z component (above the plane of the 3 centers).
func trilaterate3(p1 Coord, r1 float64, p2 Coord, r2 float64, p3 Coord, r3 float64) Coord {
	// Translate so p1 is at origin
	ex := normalize(sub(p2, p1))
	i := dot(ex, sub(p3, p1))
	ey_raw := sub(sub(p3, p1), scale(ex, i))
	ey := normalize(ey_raw)
	ez := cross(ex, ey)
	d := dist(p1, p2)
	j := dot(ey, sub(p3, p1))

	if math.Abs(d) < 1e-12 {
		return p1
	}

	x := (r1*r1 - r2*r2 + d*d) / (2 * d)
	y := (r1*r1 - r3*r3 + i*i + j*j - 2*i*x) / (2 * j)
	zSq := r1*r1 - x*x - y*y
	z := 0.0
	if zSq > 0 {
		z = math.Sqrt(zSq)
	}

	result := add(add(add(p1, scale(ex, x)), scale(ey, y)), scale(ez, z))
	return result
}

func triangleArea(a, b, c float64) float64 {
	s := (a + b + c) / 2
	sq := s * (s - a) * (s - b) * (s - c)
	if sq < 0 {
		return 0
	}
	return math.Sqrt(sq)
}

func sub(a, b Coord) Coord      { return Coord{a[0] - b[0], a[1] - b[1], a[2] - b[2]} }
func add(a, b Coord) Coord      { return Coord{a[0] + b[0], a[1] + b[1], a[2] + b[2]} }
func scale(a Coord, s float64) Coord { return Coord{a[0] * s, a[1] * s, a[2] * s} }
func dot(a, b Coord) float64    { return a[0]*b[0] + a[1]*b[1] + a[2]*b[2] }
func dist(a, b Coord) float64   { return a.Dist(b) }

func cross(a, b Coord) Coord {
	return Coord{
		a[1]*b[2] - a[2]*b[1],
		a[2]*b[0] - a[0]*b[2],
		a[0]*b[1] - a[1]*b[0],
	}
}

func normalize(v Coord) Coord {
	n := math.Sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
	if n < 1e-12 {
		return Coord{}
	}
	return Coord{v[0] / n, v[1] / n, v[2] / n}
}
