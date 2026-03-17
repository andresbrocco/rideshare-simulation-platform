import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDeployNotification, playSuccessChime, playErrorTone } from '../useDeployNotification';

describe('useDeployNotification', () => {
  beforeEach(() => {
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

  describe('cross-reload deploy notification', () => {
    it('markDeployStarted sets the sessionStorage flag', () => {
      const { result } = renderHook(() => useDeployNotification());

      act(() => {
        result.current.markDeployStarted();
      });

      expect(sessionStorage.getItem('deploy-was-in-progress')).toBe('true');
    });

    it('checkPendingNotification fires success when flag and enabled are both set', async () => {
      Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });

      const { result } = renderHook(() => useDeployNotification());

      await act(async () => {
        await result.current.toggle();
      });
      expect(result.current.enabled).toBe(true);

      act(() => {
        result.current.markDeployStarted();
      });

      let returned: boolean = false;
      act(() => {
        returned = result.current.checkPendingNotification('success');
      });

      expect(returned).toBe(true);
      expect(Notification).toHaveBeenCalledWith('Deploy Complete', expect.anything());
      expect(result.current.enabled).toBe(false);
      expect(sessionStorage.getItem('deploy-was-in-progress')).toBeNull();
    });

    it('checkPendingNotification fires error with message', async () => {
      Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });

      const { result } = renderHook(() => useDeployNotification());

      await act(async () => {
        await result.current.toggle();
      });

      act(() => {
        result.current.markDeployStarted();
      });

      let returned: boolean = false;
      act(() => {
        returned = result.current.checkPendingNotification('error', 'Deployment did not complete');
      });

      expect(returned).toBe(true);
      expect(Notification).toHaveBeenCalledWith('Deployment Failed', {
        body: 'Deployment did not complete',
        icon: '/favicon.svg',
        tag: 'deploy-failed',
      });
      expect(result.current.enabled).toBe(false);
    });

    it('checkPendingNotification returns false when flag is absent', async () => {
      Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });

      const { result } = renderHook(() => useDeployNotification());

      await act(async () => {
        await result.current.toggle();
      });
      expect(result.current.enabled).toBe(true);

      let returned: boolean = true;
      act(() => {
        returned = result.current.checkPendingNotification('success');
      });

      expect(returned).toBe(false);
      // Notification should NOT have been called for deploy complete
      expect(Notification).not.toHaveBeenCalledWith('Deploy Complete', expect.anything());
      // enabled should remain true (not consumed)
      expect(result.current.enabled).toBe(true);
    });

    it('checkPendingNotification clears flag but skips notification when disabled', () => {
      // Not enabled, but flag is set
      sessionStorage.setItem('deploy-was-in-progress', 'true');

      const { result: result2 } = renderHook(() => useDeployNotification());

      let returned: boolean = false;
      act(() => {
        returned = result2.current.checkPendingNotification('success');
      });

      expect(returned).toBe(true);
      // Flag should be cleared
      expect(sessionStorage.getItem('deploy-was-in-progress')).toBeNull();
      // But no notification fired
      expect(Notification).not.toHaveBeenCalledWith('Deploy Complete', expect.anything());
      // enabled stays false
      expect(result2.current.enabled).toBe(false);
    });

    it('notifySuccess clears the deploying flag to prevent double-fire', async () => {
      Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });

      const { result } = renderHook(() => useDeployNotification());

      await act(async () => {
        await result.current.toggle();
      });

      act(() => {
        result.current.markDeployStarted();
      });
      expect(sessionStorage.getItem('deploy-was-in-progress')).toBe('true');

      act(() => {
        result.current.notifySuccess();
      });

      expect(sessionStorage.getItem('deploy-was-in-progress')).toBeNull();
    });

    it('toggle off clears the deploying flag', async () => {
      const { result } = renderHook(() => useDeployNotification());

      await act(async () => {
        await result.current.toggle();
      });
      expect(result.current.enabled).toBe(true);

      act(() => {
        result.current.markDeployStarted();
      });
      expect(sessionStorage.getItem('deploy-was-in-progress')).toBe('true');

      await act(async () => {
        await result.current.toggle();
      });
      expect(result.current.enabled).toBe(false);
      expect(sessionStorage.getItem('deploy-was-in-progress')).toBeNull();
    });
  });

  it('notifySuccess fires OS notification even when tab is visible', async () => {
    Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });

    const { result } = renderHook(() => useDeployNotification());

    await act(async () => {
      await result.current.toggle();
    });
    expect(result.current.enabled).toBe(true);

    act(() => {
      result.current.notifySuccess();
    });

    // OS notification should fire regardless of tab visibility
    expect(Notification).toHaveBeenCalledWith('Deploy Complete', expect.anything());
    expect(result.current.enabled).toBe(false);
    expect(sessionStorage.getItem('deploy-notify-enabled')).toBeNull();
    expect(sessionStorage.getItem('deploy-was-in-progress')).toBeNull();

    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  });

  it('permission state updates live when browser settings change', async () => {
    Object.defineProperty(Notification, 'permission', { value: 'granted', configurable: true });

    let changeHandler: (() => void) | null = null;
    const mockStatus = {
      state: 'granted' as PermissionState,
      addEventListener: vi.fn((_event: string, handler: () => void) => {
        changeHandler = handler;
      }),
      removeEventListener: vi.fn(),
    };

    const originalPermissions = navigator.permissions;
    Object.defineProperty(navigator, 'permissions', {
      value: {
        query: vi.fn(() => Promise.resolve(mockStatus)),
      },
      configurable: true,
    });

    const { result } = renderHook(() => useDeployNotification());

    // Let the permissions.query promise resolve
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(result.current.permission).toBe('granted');

    // Simulate browser settings change to denied
    mockStatus.state = 'denied';
    act(() => {
      changeHandler?.();
    });

    expect(result.current.permission).toBe('denied');

    Object.defineProperty(navigator, 'permissions', {
      value: originalPermissions,
      configurable: true,
    });
  });
});

describe('playSuccessChime / playErrorTone', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does nothing when ctx is null', () => {
    // Should not throw
    playSuccessChime(null);
    playErrorTone(null);
  });

  it('skips audio when prefers-reduced-motion is active', () => {
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

    const mockCtx = {
      currentTime: 0,
      state: 'running' as AudioContextState,
      destination: {} as AudioDestinationNode,
      createOscillator: vi.fn(),
      createGain: vi.fn(),
      resume: vi.fn(),
      close: vi.fn(),
    } as unknown as AudioContext;

    playSuccessChime(mockCtx);
    playErrorTone(mockCtx);

    expect(mockCtx.createOscillator).not.toHaveBeenCalled();
  });
});
