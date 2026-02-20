import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PasswordDialog from '../PasswordDialog';
import * as lambdaService from '../../services/lambda';

describe('PasswordDialog', () => {
  const mockOnClose = vi.fn();
  const mockOnLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    Storage.prototype.setItem = vi.fn();
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_LAMBDA_URL', '');
  });

  it('does not render when closed', () => {
    render(<PasswordDialog open={false} onClose={mockOnClose} onLogin={mockOnLogin} />);
    expect(screen.queryByText(/enter password/i)).not.toBeInTheDocument();
  });

  it('renders password input when open', () => {
    render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    expect(screen.getByText('Enter Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter password')).toBeInTheDocument();
  });

  it('submit button disabled when input empty', () => {
    render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    const button = screen.getByRole('button', { name: /connect/i });
    expect(button).toBeDisabled();
  });

  it('submit button enabled with input', async () => {
    const user = userEvent.setup();
    render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    const input = screen.getByLabelText('Password');
    const button = screen.getByRole('button', { name: /connect/i });

    await user.type(input, 'test-password');
    expect(button).toBeEnabled();
  });

  it('calls onClose when cancel clicked', async () => {
    const user = userEvent.setup();
    render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when overlay clicked', async () => {
    const user = userEvent.setup();
    render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    const overlay = screen.getByRole('dialog').parentElement;
    await user.click(overlay!);

    expect(mockOnClose).toHaveBeenCalledOnce();
  });

  it('shows loading state during validation', async () => {
    const user = userEvent.setup();
    let resolvePromise: (value: { ok: boolean }) => void;
    (global.fetch as Mock).mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePromise = resolve;
      })
    );

    render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    const input = screen.getByLabelText('Password');
    await user.type(input, 'test-password');

    const button = screen.getByRole('button', { name: /connect/i });
    await user.click(button);

    expect(screen.getByText(/connecting/i)).toBeInTheDocument();
    expect(button).toBeDisabled();

    resolvePromise!({ ok: true });
  });

  it('clears input and error when closed and reopened', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({ ok: false });

    const { rerender } = render(
      <PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />
    );

    const input = screen.getByLabelText('Password');
    await user.type(input, 'invalid');
    await user.click(screen.getByRole('button', { name: /connect/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid password/i)).toBeInTheDocument();
    });

    // Close and reopen
    rerender(<PasswordDialog open={false} onClose={mockOnClose} onLogin={mockOnLogin} />);
    rerender(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    expect(screen.queryByText(/invalid password/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toHaveValue('');
  });

  describe('Lambda authentication (VITE_LAMBDA_URL set)', () => {
    beforeEach(() => {
      vi.stubEnv('VITE_LAMBDA_URL', 'https://lambda.example.com');
    });

    it('calls Lambda validateApiKey on submit', async () => {
      const user = userEvent.setup();
      const validateSpy = vi
        .spyOn(lambdaService, 'validateApiKey')
        .mockResolvedValueOnce({ valid: true });

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      const button = screen.getByRole('button', { name: /connect/i });

      await user.type(input, 'test-key');
      await user.click(button);

      await waitFor(() => {
        expect(validateSpy).toHaveBeenCalledWith('test-key');
        expect(mockOnLogin).toHaveBeenCalledWith('test-key');
        expect(sessionStorage.setItem).toHaveBeenCalledWith('apiKey', 'test-key');
      });
    });

    it('shows error for invalid credentials via Lambda', async () => {
      const user = userEvent.setup();
      vi.spyOn(lambdaService, 'validateApiKey').mockResolvedValueOnce({
        valid: false,
        error: 'Invalid key',
      });

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'wrong-key');
      await user.click(screen.getByRole('button', { name: /connect/i }));

      await waitFor(() => {
        expect(screen.getByText('Invalid key')).toBeInTheDocument();
      });
    });

    it('shows default error when Lambda returns valid=false without error message', async () => {
      const user = userEvent.setup();
      vi.spyOn(lambdaService, 'validateApiKey').mockResolvedValueOnce({ valid: false });

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'wrong-key');
      await user.click(screen.getByRole('button', { name: /connect/i }));

      await waitFor(() => {
        expect(screen.getByText(/invalid password/i)).toBeInTheDocument();
      });
    });

    it('shows network error for Lambda NETWORK_ERROR', async () => {
      const user = userEvent.setup();
      vi.spyOn(lambdaService, 'validateApiKey').mockRejectedValueOnce(
        new lambdaService.LambdaServiceError('Connection failed', 'NETWORK_ERROR')
      );

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'test-key');
      await user.click(screen.getByRole('button', { name: /connect/i }));

      await waitFor(() => {
        expect(screen.getByText(/authentication service unavailable/i)).toBeInTheDocument();
      });
    });

    it('shows auth error for Lambda INVALID_RESPONSE', async () => {
      const user = userEvent.setup();
      vi.spyOn(lambdaService, 'validateApiKey').mockRejectedValueOnce(
        new lambdaService.LambdaServiceError('Invalid response', 'INVALID_RESPONSE')
      );

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'test-key');
      await user.click(screen.getByRole('button', { name: /connect/i }));

      await waitFor(() => {
        expect(screen.getByText(/authentication error/i)).toBeInTheDocument();
      });
    });

    it('shows failure message for Lambda LAMBDA_ERROR', async () => {
      const user = userEvent.setup();
      vi.spyOn(lambdaService, 'validateApiKey').mockRejectedValueOnce(
        new lambdaService.LambdaServiceError('Lambda 500', 'LAMBDA_ERROR')
      );

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'test-key');
      await user.click(screen.getByRole('button', { name: /connect/i }));

      await waitFor(() => {
        expect(screen.getByText(/authentication failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Fallback authentication (no Lambda URL)', () => {
    beforeEach(() => {
      vi.stubEnv('VITE_LAMBDA_URL', '');
    });

    it('validates password with simulation API /auth/validate', async () => {
      const user = userEvent.setup();
      (global.fetch as Mock).mockResolvedValueOnce({ ok: true });

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      const button = screen.getByRole('button', { name: /connect/i });

      await user.type(input, 'valid-password');
      await user.click(button);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/auth/validate', {
          headers: { 'X-API-Key': 'valid-password' },
        });
      });
    });

    it('stores password in sessionStorage on success', async () => {
      const user = userEvent.setup();
      (global.fetch as Mock).mockResolvedValueOnce({ ok: true });

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'valid-password');
      await user.click(screen.getByRole('button', { name: /connect/i }));

      await waitFor(() => {
        expect(sessionStorage.setItem).toHaveBeenCalledWith('apiKey', 'valid-password');
      });
    });

    it('calls onLogin and onClose on success', async () => {
      const user = userEvent.setup();
      (global.fetch as Mock).mockResolvedValueOnce({ ok: true });

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'valid-password');
      await user.click(screen.getByRole('button', { name: /connect/i }));

      await waitFor(() => {
        expect(mockOnLogin).toHaveBeenCalledWith('valid-password');
        expect(mockOnClose).toHaveBeenCalledOnce();
      });
    });

    it('displays error on invalid password', async () => {
      const user = userEvent.setup();
      (global.fetch as Mock).mockResolvedValueOnce({ ok: false, status: 401 });

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'invalid-password');
      await user.click(screen.getByRole('button', { name: /connect/i }));

      await waitFor(() => {
        expect(screen.getByText(/invalid password/i)).toBeInTheDocument();
      });
    });

    it('displays error on connection failure', async () => {
      const user = userEvent.setup();
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Network error'));

      render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'test-password');
      await user.click(screen.getByRole('button', { name: /connect/i }));

      await waitFor(() => {
        expect(screen.getByText(/failed to connect/i)).toBeInTheDocument();
      });
    });
  });

  it('does not expose "API Key" terminology to users', () => {
    render(<PasswordDialog open={true} onClose={mockOnClose} onLogin={mockOnLogin} />);

    expect(screen.queryByText(/api key/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });
});
