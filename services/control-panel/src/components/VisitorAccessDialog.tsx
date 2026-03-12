import { useEffect, useRef, useCallback } from 'react';
import VisitorAccessForm from './VisitorAccessForm';

interface VisitorAccessDialogProps {
  open: boolean;
  onClose: () => void;
}

export default function VisitorAccessDialog({ open, onClose }: VisitorAccessDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Escape key closes the dialog
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  // Focus trap
  const handleDialogKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== 'Tab' || !dialogRef.current) return;

    const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
      'input, button:not(:disabled), [tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }, []);

  if (!open) return null;

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div
        className="dialog-content"
        ref={dialogRef}
        role="dialog"
        aria-label="Get visitor access"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleDialogKeyDown}
      >
        <VisitorAccessForm />
      </div>
    </div>
  );
}
