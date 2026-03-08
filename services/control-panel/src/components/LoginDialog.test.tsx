import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoginDialog from './LoginDialog';

const VALID_EMAIL = 'operator@rideshare.com';
const VALID_PASSWORD = 'secret123';

const SUCCESS_RESPONSE = {
  api_key: 'session-abc-123',
  role: 'operator',
  email: VALID_EMAIL,
};

describe('LoginDialog', () => {
  const mockOnClose = vi.fn();
  const mockOnLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    Storage.prototype.setItem = vi.fn();
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000');
  });

  it('does not render when closed', () => {
    render(<LoginDialog open={false} onClose={mockOnClose} onLogin={mockOnLogin} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('test_renders_email_and_password_fields — renders both inputs when open', () => {
    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('test_submit_disabled_without_email — submit button disabled when email is empty', () => {
    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);
    const button = screen.getByRole('button', { name: /sign in/i });
    expect(button).toBeDisabled();
  });

  it('test_submit_disabled_with_invalid_email — submit disabled when email has no @', async () => {
    const user = userEvent.setup();
    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), 'notanemail');
    await user.type(screen.getByLabelText('Password'), VALID_PASSWORD);

    expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled();
  });

  it('test_submit_disabled_without_password — submit disabled when password is empty', async () => {
    const user = userEvent.setup();
    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);

    expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled();
  });

  it('submit button enabled when both email and password are valid', async () => {
    const user = userEvent.setup();
    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);
    await user.type(screen.getByLabelText('Password'), VALID_PASSWORD);

    expect(screen.getByRole('button', { name: /sign in/i })).toBeEnabled();
  });

  it('test_successful_login_stores_session — stores api_key in sessionStorage and calls onLogin', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SUCCESS_RESPONSE),
    });

    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);
    await user.type(screen.getByLabelText('Password'), VALID_PASSWORD);
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(Storage.prototype.setItem).toHaveBeenCalledWith('apiKey', SUCCESS_RESPONSE.api_key);
      expect(mockOnLogin).toHaveBeenCalledWith(SUCCESS_RESPONSE.api_key);
    });
  });

  it('test_successful_login_stores_session — also stores role and email in sessionStorage', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SUCCESS_RESPONSE),
    });

    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);
    await user.type(screen.getByLabelText('Password'), VALID_PASSWORD);
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(Storage.prototype.setItem).toHaveBeenCalledWith('role', SUCCESS_RESPONSE.role);
      expect(Storage.prototype.setItem).toHaveBeenCalledWith('email', SUCCESS_RESPONSE.email);
    });
  });

  it('calls POST /auth/login with JSON body containing email and password', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SUCCESS_RESPONSE),
    });

    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);
    await user.type(screen.getByLabelText('Password'), VALID_PASSWORD);
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/auth/login',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: VALID_EMAIL, password: VALID_PASSWORD }),
        })
      );
    });
  });

  it('test_login_401_shows_error — shows "Invalid email or password" on 401', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'Unauthorized' }),
    });

    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);
    await user.type(screen.getByLabelText('Password'), 'wrongpassword');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password')).toBeInTheDocument();
    });
    expect(mockOnLogin).not.toHaveBeenCalled();
  });

  it('test_login_network_error_shows_error — shows "Unable to connect" on fetch throw', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockRejectedValueOnce(new Error('Network error'));

    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);
    await user.type(screen.getByLabelText('Password'), VALID_PASSWORD);
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/unable to connect/i)).toBeInTheDocument();
    });
    expect(mockOnLogin).not.toHaveBeenCalled();
  });

  it('test_loading_state_during_request — shows "Connecting..." while request is in-flight', async () => {
    const user = userEvent.setup();
    let resolveResponse: (value: {
      ok: boolean;
      status: number;
      json: () => Promise<unknown>;
    }) => void;
    (global.fetch as Mock).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveResponse = resolve;
      })
    );

    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);
    await user.type(screen.getByLabelText('Password'), VALID_PASSWORD);

    const submitBtn = screen.getByRole('button', { name: /sign in/i });
    await user.click(submitBtn);

    expect(screen.getByText(/connecting/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /connecting/i })).toBeDisabled();

    // Resolve to avoid warnings about unhandled promise
    resolveResponse!({ ok: true, status: 200, json: () => Promise.resolve(SUCCESS_RESPONSE) });
  });

  it('test_escape_closes_dialog — Escape key calls onClose', async () => {
    const user = userEvent.setup();
    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.keyboard('{Escape}');

    expect(mockOnClose).toHaveBeenCalledOnce();
  });

  it('test_backdrop_click_closes_dialog — clicking the overlay calls onClose', async () => {
    const user = userEvent.setup();
    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    const overlay = screen.getByRole('dialog').parentElement;
    await user.click(overlay!);

    expect(mockOnClose).toHaveBeenCalledOnce();
  });

  it('clears fields and error when dialog is closed and reopened', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
    });

    const { rerender } = render(
      <LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />
    );

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);
    await user.type(screen.getByLabelText('Password'), 'bad-password');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password')).toBeInTheDocument();
    });

    rerender(<LoginDialog open={false} onClose={mockOnClose} onLogin={mockOnLogin} />);
    rerender(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    expect(screen.queryByText('Invalid email or password')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveValue('');
    expect(screen.getByLabelText('Password')).toHaveValue('');
  });

  it('calls onClose after successful login', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SUCCESS_RESPONSE),
    });

    render(<LoginDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    await user.type(screen.getByLabelText('Email'), VALID_EMAIL);
    await user.type(screen.getByLabelText('Password'), VALID_PASSWORD);
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalledOnce();
    });
  });
});
