package cmd

import "testing"

func TestClassicNodeProvider(t *testing.T) {
	p := classicNodeProvider{n: 7}

	if got := p.NodeCount(); got != 7 {
		t.Fatalf("NodeCount() = %d, want 7", got)
	}

	name, kind, anchorID := p.NodeAt(6)
	if name != "N6" || kind != "anchor" || anchorID != 6 {
		t.Fatalf("NodeAt(6) = (%q, %q, %d), want (%q, %q, %d)", name, kind, anchorID, "N6", "anchor", 6)
	}
}
