import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useRole } from './useRole';

describe('useRole', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it('returns null when no session exists', () => {
    const { result } = renderHook(() => useRole());
    expect(result.current).toBeNull();
  });

  it('returns "admin" when sessionStorage role is admin', () => {
    sessionStorage.setItem('role', 'admin');
    const { result } = renderHook(() => useRole());
    expect(result.current).toBe('admin');
  });

  it('returns "viewer" when sessionStorage role is viewer', () => {
    sessionStorage.setItem('role', 'viewer');
    const { result } = renderHook(() => useRole());
    expect(result.current).toBe('viewer');
  });

  it('returns null for an unrecognised role string', () => {
    sessionStorage.setItem('role', 'superuser');
    const { result } = renderHook(() => useRole());
    expect(result.current).toBeNull();
  });

  it('returns null when role key is present but empty', () => {
    sessionStorage.setItem('role', '');
    const { result } = renderHook(() => useRole());
    expect(result.current).toBeNull();
  });
});
