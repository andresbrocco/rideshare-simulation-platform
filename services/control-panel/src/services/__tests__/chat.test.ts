import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';
import { createChatSession, sendChatMessage, ChatServiceError } from '../chat';

describe('Chat Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    vi.stubEnv('VITE_CHAT_LAMBDA_URL', 'https://chat-lambda.example.com');
  });

  describe('createChatSession', () => {
    it('returns session_id on success', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ session_id: 'uuid-1234' }),
      });

      const result = await createChatSession();

      expect(result).toEqual({ session_id: 'uuid-1234' });
      expect(global.fetch).toHaveBeenCalledWith(
        'https://chat-lambda.example.com',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ action: 'create-chat-session' }),
        })
      );
    });

    it('passes visitor_email in body when provided', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ session_id: 'uuid-5678' }),
      });

      const result = await createChatSession('visitor@example.com');

      expect(result).toEqual({ session_id: 'uuid-5678' });
      expect(global.fetch).toHaveBeenCalledWith(
        'https://chat-lambda.example.com',
        expect.objectContaining({
          body: JSON.stringify({
            action: 'create-chat-session',
            visitor_email: 'visitor@example.com',
          }),
        })
      );
    });
  });

  describe('sendChatMessage', () => {
    it('returns response and turn_number on success', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ response: 'Hello! How can I help?', turn_number: 1 }),
      });

      const result = await sendChatMessage('session-abc', 'Tell me about the architecture');

      expect(result).toEqual({ response: 'Hello! How can I help?', turn_number: 1 });
      expect(global.fetch).toHaveBeenCalledWith(
        'https://chat-lambda.example.com',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            action: 'send-chat-message',
            session_id: 'session-abc',
            message: 'Tell me about the architecture',
          }),
        })
      );
    });

    it('throws with BUDGET_EXCEEDED code on 429', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => ({
          error: 'BUDGET_EXCEEDED',
          message: 'The chat assistant has reached its daily limit. Please try again tomorrow.',
        }),
      });

      try {
        await sendChatMessage('session-abc', 'Hello');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ChatServiceError);
        expect((error as ChatServiceError).code).toBe('BUDGET_EXCEEDED');
        expect((error as ChatServiceError).message).toBe(
          'The chat assistant has reached its daily limit. Please try again tomorrow.'
        );
      }
    });

    it('throws with INVALID_SESSION code on 404', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({
          error: 'INVALID_SESSION',
          message: 'Session not found or expired.',
        }),
      });

      try {
        await sendChatMessage('bad-session', 'Hello');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ChatServiceError);
        expect((error as ChatServiceError).code).toBe('INVALID_SESSION');
        expect((error as ChatServiceError).message).toBe('Session not found or expired.');
      }
    });
  });

  describe('error handling', () => {
    it('throws INVALID_RESPONSE when URL not configured', async () => {
      vi.stubEnv('VITE_CHAT_LAMBDA_URL', '');

      try {
        await createChatSession();
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ChatServiceError);
        expect((error as ChatServiceError).code).toBe('INVALID_RESPONSE');
        expect((error as ChatServiceError).message).toBe('Chat Lambda URL not configured');
      }
    });

    it('throws NETWORK_ERROR on fetch failure', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Connection refused'));

      try {
        await createChatSession();
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ChatServiceError);
        expect((error as ChatServiceError).code).toBe('NETWORK_ERROR');
        expect((error as ChatServiceError).message).toBe('Chat session service unavailable');
      }
    });

    it('throws NETWORK_ERROR on sendChatMessage fetch failure', async () => {
      (global.fetch as Mock).mockRejectedValueOnce(new Error('Network error'));

      try {
        await sendChatMessage('session-abc', 'Hello');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ChatServiceError);
        expect((error as ChatServiceError).code).toBe('NETWORK_ERROR');
        expect((error as ChatServiceError).message).toBe('Chat message service unavailable');
      }
    });

    it('throws INVALID_RESPONSE for malformed success response', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ unexpected: 'structure' }),
      });

      try {
        await createChatSession();
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ChatServiceError);
        expect((error as ChatServiceError).code).toBe('INVALID_RESPONSE');
      }
    });

    it('throws INVALID_RESPONSE when error response body is not JSON', async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => {
          throw new SyntaxError('Unexpected token');
        },
      });

      try {
        await sendChatMessage('session-abc', 'Hello');
        expect.fail('should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ChatServiceError);
        expect((error as ChatServiceError).code).toBe('INVALID_RESPONSE');
        expect((error as ChatServiceError).message).toBe('Lambda returned 500');
      }
    });
  });
});
