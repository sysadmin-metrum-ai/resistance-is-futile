'use client';

import { useEffect, useRef, useCallback } from 'react';
import { Terminal } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';

/**
 * LLMTerminal - Terminal display component using xterm.js.
 * Handles token streaming for AI agent output display.
 */
interface LLMTerminalProps {
  /** Callback to receive streamed tokens */
  onToken?: (token: string) => void;
  /** Initial content to display */
  initialContent?: string;
  /** Whether terminal is disabled/readonly */
  readOnly?: boolean;
  /** Maximum lines to keep in scrollback */
  scrollback?: number;
}

/**
 * Dark theme inspired by Claude Code terminal.
 */
const CLAUDE_THEME = {
  background: '#1a1a1a',
  foreground: '#d4d4d4',
  cursor: '#d4d4d4',
  cursorAccent: '#1a1a1a',
  selectionBackground: '#264f78',
  black: '#1a1a1a',
  red: '#cd3131',
  green: '#0dbc79',
  yellow: '#e5e510',
  blue: '#2472c8',
  magenta: '#bc3fbc',
  cyan: '#11a8cd',
  white: '#d4d4d4',
  brightBlack: '#666666',
  brightRed: '#f14c4c',
  brightGreen: '#23d18b',
  brightYellow: '#f5f543',
  brightBlue: '#3b8eea',
  brightMagenta: '#d670d6',
  brightCyan: '#29b8db',
  brightWhite: '#ffffff',
};

export function LLMTerminal({
  onToken,
  initialContent = '',
  readOnly = false,
  scrollback = 1000,
}: LLMTerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminalInstance = useRef<Terminal | null>(null);

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current) return;

    const terminal = new Terminal({
      theme: CLAUDE_THEME,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      fontSize: 13,
      lineHeight: 1.4,
      cursorBlink: true,
      cursorStyle: 'block',
      scrollback: scrollback,
      readOnly: readOnly,
      convertEol: true, // Handle newlines correctly
    });

    terminal.open(terminalRef.current);
    terminalInstance.current = terminal;

    // Write initial content if provided
    if (initialContent) {
      terminal.writeln(initialContent);
    }

    return () => {
      terminal.dispose();
      terminalInstance.current = null;
    };
  }, [readOnly, scrollback]);

  /**
   * Write text to terminal - exposed via ref for external use.
   */
  const write = useCallback((text: string) => {
    if (terminalInstance.current) {
      terminalInstance.current.write(text);
    }
  }, []);

  /**
   * Write line to terminal.
   */
  const writeln = useCallback((text: string) => {
    if (terminalInstance.current) {
      terminalInstance.current.writeln(text);
    }
  }, []);

  /**
   * Clear terminal.
   */
  const clear = useCallback(() => {
    if (terminalInstance.current) {
      terminalInstance.current.clear();
    }
  }, []);

  // Expose methods via effect (for parent to call)
  useEffect(() => {
    const container = terminalRef.current;
    if (container) {
      (container as any)._terminal = {
        write,
        writeln,
        clear,
      };
    }
  }, [write, writeln, clear]);

  return (
    <div className="h-full w-full overflow-hidden rounded-lg border bg-[#1a1a1a] p-2">
      <div ref={terminalRef} className="h-full w-full" />
    </div>
  );
}
