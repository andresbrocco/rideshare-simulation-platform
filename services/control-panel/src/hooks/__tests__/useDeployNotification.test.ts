import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDeployNotification } from '../useDeployNotification';

// Mock AudioContext
function createMockAudioContext() {
  const mockOscillator = {
    type: 'sine' as OscillatorType,
    frequency: { value: 0 },
    connect: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
  };

  const mockGain = {
    gain: {
      value: 0,
      setValueAtTime: vi.fn(),
      linearRampToValueAtTime: vi.fn(),
      exponentialRampToValueAtTime: vi.fn(),
    },
    connect: vi.fn(),
  };

  return {
    instance: {
      currentTime: 0,
      state: 'running' as AudioContextState,
      destination: {} as AudioDestinationNode,
      createOscillator: vi.fn(() => mockOscillator),
      createGain: vi.fn(() => mockGain),
      resume: vi.fn(() => Promise.resolve()),
      close: vi.fn(() => Promise.resolve()),
    },
    oscillator: mockOscillator,
    gain: mockGain,
  };
}

describe('useDeployNotification', () => {
  let mockAudioCtx: ReturnType<typeof createMockAudioContext>;

  beforeEach(() => {
    mockAudioCtx = createMockAudioContext();

    // Mock Notification API
    const MockNotification = vi.fn() as unknown as typeof Notification;
    Object.defineProperty(MockNotification, 'permission', {
      value: 'default',
      writable: true,
      configurable: true,
    });
    (
      MockNotification as unknown as { requestPermission: () => Promise<NotificationPermission> }
    ).requestPermission = vi.fn(() => Promise.resolve('granted' as NotificationPermission));
    global.Notification = MockNotification;

    // Mock AudioContext
    global.AudioContext = vi.fn(() => mockAudioCtx.instance) as unknown as typeof AudioContext;

    // Mock matchMedia (no reduced motion by default)
    global.matchMedia = vi.fn((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('starts with enabled: false and reads initial permission', () => {
    const { result } = renderHook(() => useDeployNotification());

    expect(result.current.enabled).toBe(false);
    expect(result.current.permission).toBe('default');
  });

  it('toggle on requests permission and enables', async () => {
    const { result } = renderHook(() => useDeployNotification());

    await act(async () => {
      await result.current.toggle();
    });

    expect(Notification.requestPermission).toHaveBeenCalled();
    expect(result.current.enabled).toBe(true);
    expect(result.current.permission).toBe('granted');
    expect(sessionStorage.getItem('deploy-notify-enabled')).toBe('true');
  });

  it('toggle on with denied permission still enables (sound-only)', async () => {
    (
      Notification as unknown as { requestPermission: () => Promise<NotificationPermission> }
    ).requestPermission = vi.fn(() => Promise.resolve('denied' as NotificationPermission));

    const { result } = renderHook(() => useDeployNotification());

    await act(async () => {
      await result.current.toggle();
    });

    expect(result.current.enabled).toBe(true);
    expect(result.current.permission).toBe('denied');
  });

  it('toggle off clears enabled and sessionStorage', async () => {
    const { result } = renderHook(() => useDeployNotification());

    await act(async () => {
      await result.current.toggle();
    });
    expect(result.current.enabled).toBe(true);

    await act(async () => {
      await result.current.toggle();
    });
    expect(result.current.enabled).toBe(false);
    expect(sessionStorage.getItem('deploy-notify-enabled')).toBeNull();
  });

  it('notifySuccess creates OS notification and resets enabled', async () => {
    Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });

    const { result } = renderHook(() => useDeployNotification());

    await act(async () => {
      await result.current.toggle();
    });
    expect(result.current.enabled).toBe(true);

    act(() => {
      result.current.notifySuccess();
    });

    expect(Notification).toHaveBeenCalledWith('Deploy Complete', {
      body: 'All services are ready. Your platform is live.',
      icon: '/favicon.svg',
      tag: 'deploy-complete',
    });
    expect(result.current.enabled).toBe(false);
    expect(sessionStorage.getItem('deploy-notify-enabled')).toBeNull();
  });

  it('notifySuccess does nothing when disabled', () => {
    const { result } = renderHook(() => useDeployNotification());

    act(() => {
      result.current.notifySuccess();
    });

    expect(Notification).not.toHaveBeenCalledWith('Deploy Complete', expect.anything());
  });

  it('notifyError creates OS notification with error message', async () => {
    Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });

    const { result } = renderHook(() => useDeployNotification());

    await act(async () => {
      await result.current.toggle();
    });

    act(() => {
      result.current.notifyError('Workflow cancelled');
    });

    expect(Notification).toHaveBeenCalledWith('Deployment Failed', {
      body: 'Workflow cancelled',
      icon: '/favicon.svg',
      tag: 'deploy-failed',
    });
    expect(result.current.enabled).toBe(false);
  });

  it('plays sound on notifySuccess via AudioContext', async () => {
    Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });

    const { result } = renderHook(() => useDeployNotification());

    await act(async () => {
      await result.current.toggle();
    });

    act(() => {
      result.current.notifySuccess();
    });

    expect(mockAudioCtx.instance.createOscillator).toHaveBeenCalled();
    expect(mockAudioCtx.oscillator.start).toHaveBeenCalled();
  });

  it('skips sound when prefers-reduced-motion is active', async () => {
    Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });

    global.matchMedia = vi.fn((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    const { result } = renderHook(() => useDeployNotification());

    await act(async () => {
      await result.current.toggle();
    });

    act(() => {
      result.current.notifySuccess();
    });

    // OS notification still fires
    expect(Notification).toHaveBeenCalledWith('Deploy Complete', expect.anything());
    // But no oscillator was created (sound skipped)
    expect(mockAudioCtx.instance.createOscillator).not.toHaveBeenCalled();
  });

  it('restores enabled from sessionStorage on mount', async () => {
    Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });
    sessionStorage.setItem('deploy-notify-enabled', 'true');

    const { result } = renderHook(() => useDeployNotification());

    expect(result.current.enabled).toBe(true);
  });

  it('does not restore enabled when Notification API unsupported', () => {
    // Remove Notification API
    const originalNotification = global.Notification;
    // @ts-expect-error -- deliberately removing Notification to test unsupported path
    delete global.Notification;

    sessionStorage.setItem('deploy-notify-enabled', 'true');

    const { result } = renderHook(() => useDeployNotification());

    expect(result.current.enabled).toBe(false);
    expect(result.current.permission).toBe('unsupported');

    global.Notification = originalNotification;
  });

  it('closes AudioContext on unmount', async () => {
    const { result, unmount } = renderHook(() => useDeployNotification());

    await act(async () => {
      await result.current.toggle();
    });

    unmount();

    expect(mockAudioCtx.instance.close).toHaveBeenCalled();
  });
});
