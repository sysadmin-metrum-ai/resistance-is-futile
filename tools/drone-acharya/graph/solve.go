package graph

import (
	"fmt"
	"math"
)

const (
	maxIter    = 500
	convergeTol = 1e-10
	lambdaInit  = 1e-3
	lambdaUp    = 10.0
	lambdaDown  = 0.1
)

type solverEdge struct {
	iA, iB int
	dist   float64
	sigma  float64
}

// Solve refines initial coordinates using weighted nonlinear least-squares
// (Levenberg-Marquardt). The basis nodes (basisA, basisB, basisC) are held
// fixed; all other node coordinates are free parameters.
func Solve(p *Problem, initCoords []Coord, basisA, basisB, basisC string) ([]Coord, error) {
	n := len(p.Nodes)
	coords := make([]Coord, n)
	copy(coords, initCoords)

	fixed := make([]bool, n)
	fixed[p.nodeIndex[basisA]] = true
	fixed[p.nodeIndex[basisB]] = true
	fixed[p.nodeIndex[basisC]] = true

	// Map free node indices to parameter indices (3 params per free node)
	paramIdx := make([]int, n) // node index -> first param index, or -1
	nFree := 0
	for i := 0; i < n; i++ {
		if fixed[i] {
			paramIdx[i] = -1
		} else {
			paramIdx[i] = nFree * 3
			nFree++
		}
	}
	nParams := nFree * 3

	if nParams == 0 {
		return coords, nil
	}

	var edges []solverEdge
	for _, e := range p.Edges {
		edges = append(edges, solverEdge{
			iA:   p.nodeIndex[e.A],
			iB:   p.nodeIndex[e.B],
			dist: e.Distance,
			sigma: e.Sigma,
		})
	}
	nEdges := len(edges)

	state := make([]float64, nParams)
	for i := 0; i < n; i++ {
		if paramIdx[i] >= 0 {
			pi := paramIdx[i]
			state[pi] = coords[i][0]
			state[pi+1] = coords[i][1]
			state[pi+2] = coords[i][2]
		}
	}

	stateToCoords := func(s []float64) []Coord {
		c := make([]Coord, n)
		copy(c, coords)
		for i := 0; i < n; i++ {
			if paramIdx[i] >= 0 {
				pi := paramIdx[i]
				c[i] = Coord{s[pi], s[pi+1], s[pi+2]}
			}
		}
		return c
	}

	computeResiduals := func(c []Coord) []float64 {
		r := make([]float64, nEdges)
		for k, e := range edges {
			computed := c[e.iA].Dist(c[e.iB])
			r[k] = (e.dist - computed) / e.sigma
		}
		return r
	}

	costFromResiduals := func(r []float64) float64 {
		sum := 0.0
		for _, v := range r {
			sum += v * v
		}
		return sum
	}

	lambda := lambdaInit
	curCoords := stateToCoords(state)
	curResiduals := computeResiduals(curCoords)
	curCost := costFromResiduals(curResiduals)
	initCost := curCost

	for iter := 0; iter < maxIter; iter++ {
		// Build Jacobian (nEdges x nParams) and J^T * r, J^T * J
		jtj := make([]float64, nParams*nParams) // dense symmetric
		jtr := make([]float64, nParams)

		for k, e := range edges {
			cA := curCoords[e.iA]
			cB := curCoords[e.iB]
			computed := cA.Dist(cB)
			if computed < 1e-15 {
				continue
			}
			invSigma := 1.0 / e.sigma

			// Partial derivatives of residual k w.r.t. each free param
			dx := (cA[0] - cB[0]) / computed * invSigma
			dy := (cA[1] - cB[1]) / computed * invSigma
			dz := (cA[2] - cB[2]) / computed * invSigma

			var jRow [2][3]float64 // [nodeSlot][xyz], nodeSlot 0=A, 1=B
			jRow[0] = [3]float64{dx, dy, dz}
			jRow[1] = [3]float64{-dx, -dy, -dz}

			rk := curResiduals[k]

			for slot, ni := range []int{e.iA, e.iB} {
				pi := paramIdx[ni]
				if pi < 0 {
					continue
				}
				for d := 0; d < 3; d++ {
					jtr[pi+d] += jRow[slot][d] * rk
					for slot2, nj := range []int{e.iA, e.iB} {
						pj := paramIdx[nj]
						if pj < 0 {
							continue
						}
						for d2 := 0; d2 < 3; d2++ {
							jtj[(pi+d)*nParams+(pj+d2)] += jRow[slot][d] * jRow[slot2][d2]
						}
					}
				}
			}
		}

		// LM step: solve (J^T J + lambda * diag(J^T J)) * delta = J^T * r
		for trial := 0; trial < 10; trial++ {
			a := make([]float64, nParams*nParams)
			copy(a, jtj)
			for i := 0; i < nParams; i++ {
				a[i*nParams+i] += lambda * (jtj[i*nParams+i] + 1e-8)
			}

			delta, err := solveLinear(a, jtr, nParams)
			if err != nil {
				lambda *= lambdaUp
				continue
			}

			newState := make([]float64, nParams)
			for i := range state {
				newState[i] = state[i] + delta[i]
			}
			newCoords := stateToCoords(newState)
			newResiduals := computeResiduals(newCoords)
			newCost := costFromResiduals(newResiduals)

			if newCost < curCost {
				copy(state, newState)
				curCoords = newCoords
				curResiduals = newResiduals
				curCost = newCost
				lambda *= lambdaDown
				break
			}
			lambda *= lambdaUp
		}

		if curCost < convergeTol {
			break
		}
	}

	if curCost > initCost*0.99 && initCost > 1e-6 {
		return stateToCoords(state), fmt.Errorf("solver could not improve from initialization; likely inconsistent or underconstrained measurements")
	}

	return stateToCoords(state), nil
}

// solveLinear solves Ax = b using Cholesky decomposition (A is symmetric positive definite).
func solveLinear(a []float64, b []float64, n int) ([]float64, error) {
	// Cholesky: A = L L^T
	l := make([]float64, n*n)
	for i := 0; i < n; i++ {
		for j := 0; j <= i; j++ {
			sum := a[i*n+j]
			for k := 0; k < j; k++ {
				sum -= l[i*n+k] * l[j*n+k]
			}
			if i == j {
				if sum <= 0 {
					return nil, fmt.Errorf("matrix not positive definite")
				}
				l[i*n+j] = math.Sqrt(sum)
			} else {
				l[i*n+j] = sum / l[j*n+j]
			}
		}
	}

	// Forward substitution: L y = b
	y := make([]float64, n)
	for i := 0; i < n; i++ {
		sum := b[i]
		for k := 0; k < i; k++ {
			sum -= l[i*n+k] * y[k]
		}
		y[i] = sum / l[i*n+i]
	}

	// Back substitution: L^T x = y
	x := make([]float64, n)
	for i := n - 1; i >= 0; i-- {
		sum := y[i]
		for k := i + 1; k < n; k++ {
			sum -= l[k*n+i] * x[k]
		}
		x[i] = sum / l[i*n+i]
	}

	return x, nil
}
