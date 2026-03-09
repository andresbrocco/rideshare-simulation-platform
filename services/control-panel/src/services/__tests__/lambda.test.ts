import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';
import {
  validateApiKey,
  triggerDeploy,
  checkDeployStatus,
  getSessionStatus,
  getTeardownStatus,
  extendSession,
  shrinkSession,
  provisionVisitor,
  LambdaServiceError,
} from '../lambda';

describe('Lambda Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    vi.stubEnv('VITE_LAMBDA_URL', 'https://lambda.example.com');
  });

  describe('validateApiKey', () => {
    it('returns valid=true for correct key', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ valid: true }),
      });

      const result = await validateApiKey('correct-key');

      expect(result).toEqual({ valid: true });
      expect(global.fetch).toHaveBeenCalledWith(
        'https://lambda.example.com',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ action: 'validate', api_key: 'correct-key' }),
        })
      );
    });

    it('returns valid=false with error for incorrect key', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ valid: false, error: 'Invalid API key' }),
      });

      const result = await validateApiKey('wrong-key');

      expect(result).toEqual({ valid: false, error: 'Invalid API key' });
    });

    it('throws NETWORK_ERROR for fetch failures', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Connection refused'));

      try {
        await validateApiKey('test-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('NETWORK_ERROR');
        expect((error as LambdaServiceError).message).toBe('Authentication service unavailable');
      }
    });

    it('throws LAMBDA_ERROR for non-200 responses', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      try {
        await validateApiKey('test-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('LAMBDA_ERROR');
      }
    });

    it('throws INVALID_RESPONSE for malformed response', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ invalid: 'structure' }),
      });

      try {
        await validateApiKey('test-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('INVALID_RESPONSE');
      }
    });

    it('throws INVALID_RESPONSE when Lambda URL not configured', async () => {
      vi.stubEnv('VITE_LAMBDA_URL', '');

      try {
        await validateApiKey('test-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('INVALID_RESPONSE');
        expect((error as LambdaServiceError).message).toBe('Lambda URL not configured');
      }
    });
  });

  describe('triggerDeploy', () => {
    it('returns triggered=true on success', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ triggered: true, workflow_run_id: '12345' }),
      });

      const result = await triggerDeploy('admin-key');

      expect(result).toEqual({ triggered: true, workflow_run_id: '12345' });
      expect(global.fetch).toHaveBeenCalledWith(
        'https://lambda.example.com',
        expect.objectContaining({
          body: JSON.stringify({ action: 'deploy', api_key: 'admin-key', dbt_runner: 'duckdb' }),
        })
      );
    });

    it('throws NETWORK_ERROR for fetch failures', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Network error'));

      try {
        await triggerDeploy('admin-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('NETWORK_ERROR');
        expect((error as LambdaServiceError).message).toBe('Deployment service unavailable');
      }
    });
  });

  describe('checkDeployStatus', () => {
    it('returns status information', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'completed', conclusion: 'success' }),
      });

      const result = await checkDeployStatus('admin-key');

      expect(result).toEqual({ status: 'completed', conclusion: 'success' });
      expect(global.fetch).toHaveBeenCalledWith(
        'https://lambda.example.com',
        expect.objectContaining({
          body: JSON.stringify({ action: 'status', api_key: 'admin-key' }),
        })
      );
    });

    it('throws NETWORK_ERROR for fetch failures', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Network error'));

      try {
        await checkDeployStatus('admin-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('NETWORK_ERROR');
        expect((error as LambdaServiceError).message).toBe('Status service unavailable');
      }
    });
  });

  describe('getSessionStatus', () => {
    it('returns session status with active session', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          active: true,
          remaining_seconds: 600,
          deployed_at: 1700000000,
          deadline: 1700000600,
          cost_so_far: 0.05,
        }),
      });

      const result = await getSessionStatus();

      expect(result).toEqual({
        active: true,
        remaining_seconds: 600,
        deployed_at: 1700000000,
        deadline: 1700000600,
        cost_so_far: 0.05,
      });
      expect(global.fetch).toHaveBeenCalledWith(
        'https://lambda.example.com',
        expect.objectContaining({
          body: JSON.stringify({ action: 'session-status' }),
        })
      );
    });

    it('returns inactive when no session exists', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ active: false }),
      });

      const result = await getSessionStatus();

      expect(result).toEqual({ active: false });
    });

    it('does not send api_key in payload', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ active: false }),
      });

      await getSessionStatus();

      const callBody = JSON.parse((global.fetch as Mock).mock.calls[0][1].body as string);
      expect(callBody).not.toHaveProperty('api_key');
    });

    it('throws NETWORK_ERROR for fetch failures', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Network error'));

      try {
        await getSessionStatus();
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('NETWORK_ERROR');
        expect((error as LambdaServiceError).message).toBe('Session status service unavailable');
      }
    });
  });

  describe('getTeardownStatus', () => {
    it('returns teardown progress with step data', async () => {
      const mockResponse = {
        tearing_down: true,
        run_id: 12345,
        workflow_status: 'in_progress',
        workflow_conclusion: null,
        current_step: 2,
        total_steps: 5,
        steps: [
          { name: 'Saving simulation checkpoint...', status: 'completed' },
          { name: 'Cleaning up DNS records...', status: 'completed' },
          { name: 'Destroying infrastructure...', status: 'in_progress' },
          { name: 'Verifying cleanup...', status: 'pending' },
          { name: 'Finalizing...', status: 'pending' },
        ],
      };

      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await getTeardownStatus();

      expect(result).toEqual(mockResponse);
    });

    it('does not send api_key in payload', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tearing_down: false,
          run_id: null,
          workflow_status: 'queued',
          workflow_conclusion: null,
          current_step: -1,
          total_steps: 5,
          steps: [],
        }),
      });

      await getTeardownStatus();

      const callBody = JSON.parse((global.fetch as Mock).mock.calls[0][1].body as string);
      expect(callBody).not.toHaveProperty('api_key');
    });

    it('throws NETWORK_ERROR for fetch failures', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Network error'));

      try {
        await getTeardownStatus();
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('NETWORK_ERROR');
        expect((error as LambdaServiceError).message).toBe('Teardown status service unavailable');
      }
    });

    it('throws INVALID_RESPONSE for malformed response', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ invalid: 'structure' }),
      });

      try {
        await getTeardownStatus();
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('INVALID_RESPONSE');
      }
    });
  });

  describe('extendSession', () => {
    it('returns updated session on success', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          remaining_seconds: 1500,
          deadline: 1700001500,
        }),
      });

      const result = await extendSession('admin-key');

      expect(result).toEqual({
        success: true,
        remaining_seconds: 1500,
        deadline: 1700001500,
      });
      expect(global.fetch).toHaveBeenCalledWith(
        'https://lambda.example.com',
        expect.objectContaining({
          body: JSON.stringify({ action: 'extend-session', api_key: 'admin-key' }),
        })
      );
    });

    it('throws NETWORK_ERROR for fetch failures', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Network error'));

      try {
        await extendSession('admin-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('NETWORK_ERROR');
        expect((error as LambdaServiceError).message).toBe('Session extend service unavailable');
      }
    });

    it('throws LAMBDA_ERROR for non-200 responses', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
      });

      try {
        await extendSession('admin-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('LAMBDA_ERROR');
      }
    });
  });

  describe('provisionVisitor', () => {
    it('sends correct payload with action and email', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ provisioned: true, email_sent: true, failures: [] }),
      });

      await provisionVisitor('visitor@example.com');

      expect(global.fetch).toHaveBeenCalledWith(
        'https://lambda.example.com',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ action: 'provision-visitor', email: 'visitor@example.com' }),
        })
      );
    });

    it('returns a typed ProvisionVisitorResponse on success', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ provisioned: true, email_sent: true, failures: [] }),
      });

      const result = await provisionVisitor('visitor@example.com');

      expect(result).toEqual({ provisioned: true, email_sent: true, failures: [] });
    });

    it('throws LAMBDA_ERROR on HTTP 500', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      try {
        await provisionVisitor('visitor@example.com');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('LAMBDA_ERROR');
      }
    });

    it('throws NETWORK_ERROR on fetch failure', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Connection refused'));

      try {
        await provisionVisitor('visitor@example.com');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('NETWORK_ERROR');
      }
    });

    it('resolves successfully on HTTP 207 (partial failure)', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: false,
        status: 207,
        json: async () => ({
          provisioned: true,
          email_sent: true,
          failures: ['grafana_user'],
        }),
      });

      const result = await provisionVisitor('visitor@example.com');

      expect(result).toEqual({
        provisioned: true,
        email_sent: true,
        failures: ['grafana_user'],
      });
    });

    it('does not send a name field in the payload', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ provisioned: true, email_sent: true, failures: [] }),
      });

      await provisionVisitor('visitor@example.com');

      const callBody = JSON.parse((global.fetch as Mock).mock.calls[0][1].body as string);
      expect(callBody).not.toHaveProperty('name');
    });
  });

  describe('shrinkSession', () => {
    it('returns updated session on success', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          remaining_seconds: 300,
          deadline: 1700000300,
        }),
      });

      const result = await shrinkSession('admin-key');

      expect(result).toEqual({
        success: true,
        remaining_seconds: 300,
        deadline: 1700000300,
      });
      expect(global.fetch).toHaveBeenCalledWith(
        'https://lambda.example.com',
        expect.objectContaining({
          body: JSON.stringify({ action: 'shrink-session', api_key: 'admin-key' }),
        })
      );
    });

    it('throws NETWORK_ERROR for fetch failures', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Network error'));

      try {
        await shrinkSession('admin-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('NETWORK_ERROR');
        expect((error as LambdaServiceError).message).toBe('Session shrink service unavailable');
      }
    });

    it('throws LAMBDA_ERROR for non-200 responses', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
      });

      try {
        await shrinkSession('admin-key');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(LambdaServiceError);
        expect((error as LambdaServiceError).code).toBe('LAMBDA_ERROR');
      }
    });
  });
});
