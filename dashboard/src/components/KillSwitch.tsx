'use client';

import { useState } from 'react';
import { AlertTriangle, Loader2, CheckCircle, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { triggerKillSwitch } from '@/lib/api';

type KillSwitchState = 'idle' | 'confirming' | 'loading' | 'success' | 'error';

/**
 * KillSwitch - Emergency stop button with confirmation step.
 * Destructive red button that triggers emergency landing for all drones.
 */
interface KillSwitchProps {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}

/**
 * Human-readable status messages.
 */
const STATE_MESSAGES: Record<KillSwitchState, string> = {
  idle: 'Emergency Land All',
  confirming: 'Confirm Emergency Landing?',
  loading: 'Triggering Kill Switch...',
  success: 'Kill Switch Triggered',
  error: 'Failed - Try Again',
};

export function KillSwitch({ onSuccess, onError }: KillSwitchProps) {
  const [state, setState] = useState<KillSwitchState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleClick = () => {
    if (state === 'idle') {
      setState('confirming');
    } else if (state === 'confirming') {
      triggerKillSwitchHandler();
    } else if (state === 'error') {
      setState('idle');
      setErrorMessage(null);
    } else if (state === 'success') {
      setState('idle');
    }
  };

  const handleCancel = () => {
    setState('idle');
    setErrorMessage(null);
  };

  const triggerKillSwitchHandler = async () => {
    setState('loading');
    setErrorMessage(null);

    try {
      await triggerKillSwitch();
      setState('success');
      onSuccess?.();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setErrorMessage(message);
      setState('error');
      onError?.(error instanceof Error ? error : new Error(message));
    }
  };

  const getButtonVariant = () => {
    switch (state) {
      case 'idle':
      case 'confirming':
        return 'destructive';
      case 'loading':
        return 'destructive';
      case 'success':
        return 'default';
      case 'error':
        return 'destructive';
      default:
        return 'destructive';
    }
  };

  const isDisabled = state === 'loading';

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        {state === 'idle' && <AlertTriangle className="h-5 w-5 text-destructive" />}
        {state === 'confirming' && <AlertTriangle className="h-5 w-5 animate-pulse text-destructive" />}
        {state === 'loading' && <Loader2 className="h-5 w-5 animate-spin" />}
        {state === 'success' && <CheckCircle className="h-5 w-5 text-green-500" />}
        {state === 'error' && <XCircle className="h-5 w-5 text-destructive" />}
        <span className="text-sm font-medium">
          {STATE_MESSAGES[state]}
        </span>
      </div>

      {state === 'confirming' ? (
        <div className="flex gap-2">
          <Button
            variant="destructive"
            size="sm"
            onClick={handleClick}
            disabled={isDisabled}
            className="flex-1"
          >
            Confirm
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCancel}
            disabled={isDisabled}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <Button
          variant={getButtonVariant()}
          size="sm"
          onClick={handleClick}
          disabled={isDisabled}
          className="w-full"
        >
          {state === 'loading' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {state === 'idle' && 'Trigger Emergency Landing'}
          {state === 'success' && 'Done'}
          {state === 'error' && 'Retry'}
        </Button>
      )}

      {errorMessage && (
        <p className="text-xs text-destructive">{errorMessage}</p>
      )}
    </div>
  );
}
