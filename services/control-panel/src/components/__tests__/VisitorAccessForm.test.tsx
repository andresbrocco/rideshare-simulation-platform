import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import VisitorAccessForm from '../VisitorAccessForm';
import * as lambdaService from '../../services/lambda';

vi.mock('../../services/lambda', async (importOriginal) => {
  const actual = await importOriginal<typeof lambdaService>();
  return {
    ...actual,
    provisionVisitor: vi.fn(),
  };
});

describe('VisitorAccessForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('form validation', () => {
    it('submit button is disabled initially', () => {
      render(<VisitorAccessForm />);
      expect(screen.getByRole('button', { name: /request access/i })).toBeDisabled();
    });

    it('submit button is disabled with an invalid email', async () => {
      const user = userEvent.setup();
      render(<VisitorAccessForm />);

      await user.type(screen.getByRole('textbox', { name: /email address/i }), 'not-an-email');

      expect(screen.getByRole('button', { name: /request access/i })).toBeDisabled();
    });

    it('submit button is enabled with a valid email', async () => {
      const user = userEvent.setup();
      render(<VisitorAccessForm />);

      await user.type(screen.getByRole('textbox', { name: /email address/i }), 'test@example.com');

      expect(screen.getByRole('button', { name: /request access/i })).toBeEnabled();
    });
  });

  describe('submit behaviour', () => {
    it('calls provisionVisitor with the entered email on submit', async () => {
      const user = userEvent.setup();
      vi.mocked(lambdaService.provisionVisitor).mockResolvedValueOnce({
        provisioned: true,
        email_sent: true,
        failures: [],
      });

      render(<VisitorAccessForm />);

      await user.type(
        screen.getByRole('textbox', { name: /email address/i }),
        'visitor@example.com'
      );
      await user.click(screen.getByRole('button', { name: /request access/i }));

      await waitFor(() => {
        expect(lambdaService.provisionVisitor).toHaveBeenCalledWith('visitor@example.com');
      });
    });

    it('shows loading state while submitting', async () => {
      const user = userEvent.setup();
      let resolve: (value: lambdaService.ProvisionVisitorResponse) => void;
      vi.mocked(lambdaService.provisionVisitor).mockReturnValueOnce(
        new Promise((res) => {
          resolve = res;
        })
      );

      render(<VisitorAccessForm />);

      await user.type(
        screen.getByRole('textbox', { name: /email address/i }),
        'visitor@example.com'
      );
      await user.click(screen.getByRole('button', { name: /request access/i }));

      expect(screen.getByRole('button', { name: /sending/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();
      expect(screen.getByRole('textbox', { name: /email address/i })).toBeDisabled();

      resolve!({ provisioned: true, email_sent: true, failures: [] });
    });
  });

  describe('success state (200)', () => {
    it('shows "Check your email" confirmation after full success', async () => {
      const user = userEvent.setup();
      vi.mocked(lambdaService.provisionVisitor).mockResolvedValueOnce({
        provisioned: true,
        email_sent: true,
        failures: [],
      });

      render(<VisitorAccessForm />);

      await user.type(screen.getByRole('textbox', { name: /email address/i }), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /request access/i }));

      await waitFor(() => {
        expect(screen.getByText(/check your email/i)).toBeInTheDocument();
      });
    });

    it('shows visitor email in the confirmation message', async () => {
      const user = userEvent.setup();
      vi.mocked(lambdaService.provisionVisitor).mockResolvedValueOnce({
        provisioned: true,
        email_sent: true,
        failures: [],
      });

      render(<VisitorAccessForm />);

      await user.type(
        screen.getByRole('textbox', { name: /email address/i }),
        'myname@example.com'
      );
      await user.click(screen.getByRole('button', { name: /request access/i }));

      await waitFor(() => {
        expect(screen.getByText(/myname@example\.com/)).toBeInTheDocument();
      });
    });

    it('does not show the partial failure note on full success', async () => {
      const user = userEvent.setup();
      vi.mocked(lambdaService.provisionVisitor).mockResolvedValueOnce({
        provisioned: true,
        email_sent: true,
        failures: [],
      });

      render(<VisitorAccessForm />);

      await user.type(screen.getByRole('textbox', { name: /email address/i }), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /request access/i }));

      await waitFor(() => {
        expect(screen.getByText(/check your email/i)).toBeInTheDocument();
      });

      expect(screen.queryByText(/some services encountered issues/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/email delivery failed/i)).not.toBeInTheDocument();
    });
  });

  describe('success notes', () => {
    it('shows deployment guidance note on success', async () => {
      const user = userEvent.setup();
      vi.mocked(lambdaService.provisionVisitor).mockResolvedValueOnce({
        provisioned: true,
        email_sent: true,
        failures: [],
      });

      render(<VisitorAccessForm />);

      await user.type(screen.getByRole('textbox', { name: /email address/i }), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /request access/i }));

      await waitFor(() => {
        expect(
          screen.getByText(/your credentials will work once the platform is running/i)
        ).toBeInTheDocument();
      });
    });

    it('shows email delivery note when email_sent is false', async () => {
      const user = userEvent.setup();
      vi.mocked(lambdaService.provisionVisitor).mockResolvedValueOnce({
        provisioned: true,
        email_sent: false,
        failures: [],
      });

      render(<VisitorAccessForm />);

      await user.type(screen.getByRole('textbox', { name: /email address/i }), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /request access/i }));

      await waitFor(() => {
        expect(screen.getByText(/email delivery failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('consent disclosure completeness', () => {
    it('renders all required disclosure points in the consent note', () => {
      render(<VisitorAccessForm />);
      const consentNote = screen.getByText(/by submitting/i);
      expect(consentNote).toBeInTheDocument();
      const text = consentNote.textContent ?? '';
      expect(text).toMatch(/credentials via email/i);
      expect(text).toMatch(/usage tracking/i);
      expect(text).toMatch(/never shared/i);
      expect(text).toMatch(/deletable on request/i);
    });
  });

  describe('error state (500/network)', () => {
    it('shows error message when provisionVisitor throws a LambdaServiceError', async () => {
      const user = userEvent.setup();
      vi.mocked(lambdaService.provisionVisitor).mockRejectedValueOnce(
        new lambdaService.LambdaServiceError('Lambda returned 500', 'LAMBDA_ERROR')
      );

      render(<VisitorAccessForm />);

      await user.type(screen.getByRole('textbox', { name: /email address/i }), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /request access/i }));

      await waitFor(() => {
        expect(screen.getByText(/lambda returned 500/i)).toBeInTheDocument();
      });
    });

    it('shows fallback error message for generic network errors', async () => {
      const user = userEvent.setup();
      vi.mocked(lambdaService.provisionVisitor).mockRejectedValueOnce(
        new lambdaService.LambdaServiceError(
          'Visitor provisioning service unavailable',
          'NETWORK_ERROR'
        )
      );

      render(<VisitorAccessForm />);

      await user.type(screen.getByRole('textbox', { name: /email address/i }), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /request access/i }));

      await waitFor(() => {
        expect(screen.getByText(/visitor provisioning service unavailable/i)).toBeInTheDocument();
      });
    });

    it('"Try again" button resets the form to idle state', async () => {
      const user = userEvent.setup();
      vi.mocked(lambdaService.provisionVisitor).mockRejectedValueOnce(
        new lambdaService.LambdaServiceError('Lambda returned 500', 'LAMBDA_ERROR')
      );

      render(<VisitorAccessForm />);

      await user.type(screen.getByRole('textbox', { name: /email address/i }), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /request access/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /try again/i }));

      expect(screen.getByRole('button', { name: /request access/i })).toBeInTheDocument();
    });
  });
});
