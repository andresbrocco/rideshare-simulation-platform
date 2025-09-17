import '@testing-library/jest-dom';
import { configure } from '@testing-library/react';
import { vi } from 'vitest';

configure({
  asyncUtilTimeout: 5000,
});

// Configure fake timers to automatically advance, needed for React async testing
vi.setConfig({
  fakeTimers: {
    shouldAdvanceTime: true,
  },
});
