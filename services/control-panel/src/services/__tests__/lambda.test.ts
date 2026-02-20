import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';
import { validateApiKey, triggerDeploy, checkDeployStatus, LambdaServiceError } from '../lambda';

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
          body: JSON.stringify({ action: 'deploy', api_key: 'admin-key' }),
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
});
