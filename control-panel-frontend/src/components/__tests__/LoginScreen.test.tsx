import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoginScreen from '../LoginScreen';

describe('LoginScreen', () => {
  const mockOnLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    Storage.prototype.setItem = vi.fn();
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000');
  });

  it('renders api key input field', () => {
    render(<LoginScreen onLogin={mockOnLogin} />);

    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/enter api key/i)).toBeInTheDocument();
  });

  it('submit button disabled when input empty', () => {
    render(<LoginScreen onLogin={mockOnLogin} />);

    const button = screen.getByRole('button', { name: /connect/i });
    expect(button).toBeDisabled();
  });

  it('submit button enabled with input', async () => {
    const user = userEvent.setup();
    render(<LoginScreen onLogin={mockOnLogin} />);

    const input = screen.getByLabelText(/api key/i);
    const button = screen.getByRole('button', { name: /connect/i });

    await user.type(input, 'test-key');

    expect(button).toBeEnabled();
  });

  it('stores key in sessionStorage on success', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
    });

    render(<LoginScreen onLogin={mockOnLogin} />);

    const input = screen.getByLabelText(/api key/i);
    const button = screen.getByRole('button', { name: /connect/i });

    await user.type(input, 'valid-key');
    await user.click(button);

    await waitFor(() => {
      expect(sessionStorage.setItem).toHaveBeenCalledWith('apiKey', 'valid-key');
    });
  });

  it('displays error on connection failure', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: false,
      status: 401,
    });

    render(<LoginScreen onLogin={mockOnLogin} />);

    const input = screen.getByLabelText(/api key/i);
    const button = screen.getByRole('button', { name: /connect/i });

    await user.type(input, 'invalid-key');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/invalid api key/i)).toBeInTheDocument();
    });
  });

  it('shows loading state during validation', async () => {
    const user = userEvent.setup();
    let resolvePromise: (value: { ok: boolean }) => void;
    (global.fetch as Mock).mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePromise = resolve;
      })
    );

    render(<LoginScreen onLogin={mockOnLogin} />);

    const input = screen.getByLabelText(/api key/i);
    await user.type(input, 'test-key');

    const button = screen.getByRole('button', { name: /connect/i });
    await user.click(button);

    expect(screen.getByText(/connecting/i)).toBeInTheDocument();
    expect(button).toBeDisabled();

    resolvePromise!({ ok: true });
  });

  it('calls health endpoint on submit', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
    });

    render(<LoginScreen onLogin={mockOnLogin} />);

    const input = screen.getByLabelText(/api key/i);
    const button = screen.getByRole('button', { name: /connect/i });

    await user.type(input, 'test-key');
    await user.click(button);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/health', {
        headers: { 'X-API-Key': 'test-key' },
      });
    });
  });

  it('calls onLogin callback on success', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
    });

    render(<LoginScreen onLogin={mockOnLogin} />);

    const input = screen.getByLabelText(/api key/i);
    const button = screen.getByRole('button', { name: /connect/i });

    await user.type(input, 'valid-key');
    await user.click(button);

    await waitFor(() => {
      expect(mockOnLogin).toHaveBeenCalledWith('valid-key');
    });
  });
});
