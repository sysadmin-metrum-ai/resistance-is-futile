package graph

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"sort"
)

type Coord [3]float64

func (c Coord) Dist(o Coord) float64 {
	dx := c[0] - o[0]
	dy := c[1] - o[1]
	dz := c[2] - o[2]
	return math.Sqrt(dx*dx + dy*dy + dz*dz)
}

type Node struct {
	ID       string
	Kind     string // "anchor" or "latent"
	AnchorID int    // only meaningful when Kind == "anchor"
	Index    int    // position in Problem.Nodes slice
}

type Edge struct {
	A, B     string
	Distance float64
	Sigma    float64
}

type SurveyFrame struct {
	XFrom          string
	XTo            string
	PlaneNode      string
	PositiveZNode  string
}

type EdgeResidual struct {
	A, B     string
	Measured float64
	Computed float64
	ErrorM   float64
	Residual float64 // (measured - computed) / sigma
}

type Problem struct {
	Nodes       []Node
	Edges       []Edge
	SurveyFrame *SurveyFrame

	nodeIndex map[string]int
	adj       map[string][]string
}

func (p *Problem) NodeByID(id string) (*Node, bool) {
	idx, ok := p.nodeIndex[id]
	if !ok {
		return nil, false
	}
	return &p.Nodes[idx], true
}

func (p *Problem) Dist(a, b string) (float64, bool) {
	ka := edgeKey(a, b)
	for _, e := range p.Edges {
		if edgeKey(e.A, e.B) == ka {
			return e.Distance, true
		}
	}
	return 0, false
}

func (p *Problem) Neighbors(id string) []string {
	return p.adj[id]
}

func edgeKey(a, b string) [2]string {
	if a > b {
		a, b = b, a
	}
	return [2]string{a, b}
}

func (p *Problem) build() error {
	p.nodeIndex = make(map[string]int, len(p.Nodes))
	for i, n := range p.Nodes {
		if _, dup := p.nodeIndex[n.ID]; dup {
			return fmt.Errorf("duplicate node %q", n.ID)
		}
		p.Nodes[i].Index = i
		p.nodeIndex[n.ID] = i
	}

	seen := make(map[[2]string]bool, len(p.Edges))
	p.adj = make(map[string][]string, len(p.Nodes))
	for _, e := range p.Edges {
		if _, ok := p.nodeIndex[e.A]; !ok {
			return fmt.Errorf("edge references unknown node %q", e.A)
		}
		if _, ok := p.nodeIndex[e.B]; !ok {
			return fmt.Errorf("edge references unknown node %q", e.B)
		}
		k := edgeKey(e.A, e.B)
		if seen[k] {
			return fmt.Errorf("duplicate edge %s-%s", e.A, e.B)
		}
		seen[k] = true
		p.adj[e.A] = append(p.adj[e.A], e.B)
		p.adj[e.B] = append(p.adj[e.B], e.A)
	}

	if p.SurveyFrame != nil {
		sf := p.SurveyFrame
		for _, id := range []string{sf.XFrom, sf.XTo, sf.PlaneNode, sf.PositiveZNode} {
			if _, ok := p.nodeIndex[id]; !ok {
				return fmt.Errorf("survey_frame references unknown node %q", id)
			}
		}
		ids := []string{sf.XFrom, sf.XTo, sf.PlaneNode}
		for i := 0; i < len(ids); i++ {
			for j := i + 1; j < len(ids); j++ {
				if _, ok := p.Dist(ids[i], ids[j]); !ok {
					return fmt.Errorf("survey_frame requires edge between %s and %s", ids[i], ids[j])
				}
			}
		}
		for _, id := range ids {
			if _, ok := p.Dist(sf.PositiveZNode, id); !ok {
				return fmt.Errorf("survey_frame requires edge between %s and %s", sf.PositiveZNode, id)
			}
		}
	}

	return nil
}

// JSONL intermediate types

type jsonlRecord struct {
	Type string `json:"type"`
}

type jsonlNode struct {
	ID       string `json:"id"`
	Kind     string `json:"kind"`
	AnchorID *int   `json:"anchor_id,omitempty"`
}

type jsonlEdge struct {
	A        string   `json:"a"`
	B        string   `json:"b"`
	Distance float64  `json:"distance"`
	Sigma    *float64 `json:"sigma,omitempty"`
}

type jsonlSurveyFrame struct {
	XFrom         string `json:"x_from"`
	XTo           string `json:"x_to"`
	PlaneNode     string `json:"plane_node"`
	PositiveZNode string `json:"positive_z_node"`
}

func ReadProblem(r io.Reader) (*Problem, error) {
	p := &Problem{}
	scanner := bufio.NewScanner(r)
	lineNo := 0

	for scanner.Scan() {
		lineNo++
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		var rec jsonlRecord
		if err := json.Unmarshal(line, &rec); err != nil {
			return nil, fmt.Errorf("line %d: %w", lineNo, err)
		}

		switch rec.Type {
		case "node":
			var n jsonlNode
			if err := json.Unmarshal(line, &n); err != nil {
				return nil, fmt.Errorf("line %d: %w", lineNo, err)
			}
			node := Node{ID: n.ID, Kind: n.Kind, AnchorID: -1}
			if n.AnchorID != nil {
				node.AnchorID = *n.AnchorID
			}
			p.Nodes = append(p.Nodes, node)

		case "edge":
			var e jsonlEdge
			if err := json.Unmarshal(line, &e); err != nil {
				return nil, fmt.Errorf("line %d: %w", lineNo, err)
			}
			if e.Distance <= 0 {
				return nil, fmt.Errorf("line %d: edge %s-%s has non-positive distance %.3f", lineNo, e.A, e.B, e.Distance)
			}
			sigma := 1.0
			if e.Sigma != nil && *e.Sigma > 0 {
				sigma = *e.Sigma
			}
			p.Edges = append(p.Edges, Edge{A: e.A, B: e.B, Distance: e.Distance, Sigma: sigma})

		case "survey_frame":
			var sf jsonlSurveyFrame
			if err := json.Unmarshal(line, &sf); err != nil {
				return nil, fmt.Errorf("line %d: %w", lineNo, err)
			}
			p.SurveyFrame = &SurveyFrame{
				XFrom:         sf.XFrom,
				XTo:           sf.XTo,
				PlaneNode:     sf.PlaneNode,
				PositiveZNode: sf.PositiveZNode,
			}

		default:
			return nil, fmt.Errorf("unknown record type %q", rec.Type)
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}

	if len(p.Nodes) < 4 {
		return nil, fmt.Errorf("need at least 4 nodes, got %d", len(p.Nodes))
	}
	if len(p.Edges) == 0 {
		return nil, fmt.Errorf("no edges in graph")
	}

	if err := p.build(); err != nil {
		return nil, err
	}

	return p, nil
}

func (p *Problem) NodeCount() int { return len(p.Nodes) }

func (p *Problem) NodeAt(i int) (name, kind string, anchorID int) {
	n := p.Nodes[i]
	return n.ID, n.Kind, n.AnchorID
}

func (p *Problem) AnchorNodes() []Node {
	var out []Node
	for _, n := range p.Nodes {
		if n.Kind == "anchor" {
			out = append(out, n)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].AnchorID < out[j].AnchorID })
	return out
}
