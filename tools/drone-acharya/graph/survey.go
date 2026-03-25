package graph

import (
	"fmt"
	"math"
)

// ApplySurveyFrame reorients all coordinates so that:
//   - x_from is at the origin
//   - x_to is on the +X axis
//   - plane_node is in the XY plane (Z=0)
//   - positive_z_node is on the +Z side of that plane
//
// This is a rigid transform (rotation + translation) that preserves all
// distances, so validation residuals are unchanged.
func ApplySurveyFrame(p *Problem, coords []Coord) ([]Coord, error) {
	if p.SurveyFrame == nil {
		return coords, nil
	}
	sf := p.SurveyFrame

	iFrom := p.nodeIndex[sf.XFrom]
	iTo := p.nodeIndex[sf.XTo]
	iPlane := p.nodeIndex[sf.PlaneNode]
	iPosZ := p.nodeIndex[sf.PositiveZNode]

	origin := coords[iFrom]
	pTo := coords[iTo]
	pPlane := coords[iPlane]
	pPosZ := coords[iPosZ]

	// Translate so x_from is at origin
	translated := make([]Coord, len(coords))
	for i, c := range coords {
		translated[i] = sub(c, origin)
	}
	pTo = sub(pTo, origin)
	pPlane = sub(pPlane, origin)
	pPosZ = sub(pPosZ, origin)

	// Build orthonormal basis: ex along x_from->x_to, ey in plane, ez = ex x ey
	ex := normalize(pTo)
	if norm(ex) < 1e-12 {
		return nil, fmt.Errorf("survey_frame: x_from and x_to are coincident")
	}

	// Project plane_node onto the plane perpendicular to ex
	projPlane := sub(pPlane, scale(ex, dot(ex, pPlane)))
	ey := normalize(projPlane)
	if norm(ey) < 1e-12 {
		return nil, fmt.Errorf("survey_frame: x_from, x_to, and plane_node are collinear")
	}

	ez := cross(ex, ey)

	// Rotation matrix R maps world coords to survey frame:
	// new_x = dot(ex, old), new_y = dot(ey, old), new_z = dot(ez, old)
	result := make([]Coord, len(translated))
	for i, c := range translated {
		result[i] = Coord{
			dot(ex, c),
			dot(ey, c),
			dot(ez, c),
		}
	}

	// Check if positive_z_node is on the +Z side
	pzTransformed := Coord{dot(ex, pPosZ), dot(ey, pPosZ), dot(ez, pPosZ)}
	if pzTransformed[2] < 0 {
		// Flip Z for all coordinates
		for i := range result {
			result[i][2] = -result[i][2]
		}
	} else if math.Abs(pzTransformed[2]) < 1e-9 {
		return nil, fmt.Errorf("survey_frame: positive_z_node %s lies in the survey plane (Z~=0); cannot determine +Z direction", sf.PositiveZNode)
	}

	return result, nil
}

func norm(v Coord) float64 {
	return math.Sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
}
