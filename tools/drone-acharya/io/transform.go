package io

import (
	"math"
)

// Transform applies rotation, Z-flip, and translation to coordinates.
// This converts from arbitrary/ENU-like coordinates to Crazyflie NED.
func Transform(coords []Coord, rotateNed float64, offsetX, offsetY, offsetZ float64, zDown bool) []Coord {
	if rotateNed == 0 && offsetX == 0 && offsetY == 0 && offsetZ == 0 && !zDown {
		return coords // No transformation needed
	}

	// Build rotation matrix (rotation around Z-axis)
	theta := rotateNed * math.Pi / 180.0 // degrees to radians
	cosTheta := math.Cos(theta)
	sinTheta := math.Sin(theta)

	// Z-flip multiplier: -1 for NED (down), 1 for ENU/up (default)
	zMult := 1.0
	if zDown {
		zMult = -1
	}

	result := make([]Coord, len(coords))
	for i, c := range coords {
		// Apply rotation around Z-axis
		x := c[0]*cosTheta - c[1]*sinTheta
		y := c[0]*sinTheta + c[1]*cosTheta
		z := c[2] * zMult

		// Apply translation
		x += offsetX
		y += offsetY
		z += offsetZ

		result[i] = Coord{x, y, z}
	}
	return result
}
