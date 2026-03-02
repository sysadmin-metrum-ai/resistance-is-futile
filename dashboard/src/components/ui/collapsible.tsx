'use client';

import * as React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface CollapsibleProps {
  children: React.ReactNode;
  defaultOpen?: boolean;
}

interface CollapsibleContentProps {
  children: React.ReactNode;
  className?: string;
}

const CollapsibleContext = React.createContext<{
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}>({
  isOpen: false,
  setIsOpen: () => {},
});

function CollapsibleRoot({ children, defaultOpen = false }: CollapsibleProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);
  return (
    <CollapsibleContext.Provider value={{ isOpen, setIsOpen }}>
      <div className="flex flex-col">{children}</div>
    </CollapsibleContext.Provider>
  );
}

function CollapsibleTrigger({ children }: { children: React.ReactNode }) {
  const { isOpen, setIsOpen } = React.useContext(CollapsibleContext);
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setIsOpen(!isOpen)}
      className="flex w-full items-center justify-between"
    >
      {children}
      {isOpen ? (
        <ChevronUp className="h-4 w-4" />
      ) : (
        <ChevronDown className="h-4 w-4" />
      )}
    </Button>
  );
}

function CollapsibleContent({
  children,
  className = '',
}: CollapsibleContentProps) {
  const { isOpen } = React.useContext(CollapsibleContext);
  if (!isOpen) return null;
  return <div className={className}>{children}</div>;
}

export { CollapsibleRoot, CollapsibleTrigger, CollapsibleContent };
