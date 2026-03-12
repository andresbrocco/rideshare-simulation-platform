import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatWidget } from '../ChatWidget';
import * as chatService from '../../../services/chat';
import { ChatServiceError } from '../../../services/chat';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../../services/chat', () => ({
  createChatSession: vi.fn(),
  sendChatMessage: vi.fn(),
  listProviders: vi.fn().mockResolvedValue({ providers: [] }),
  ChatServiceError: class ChatServiceError extends Error {
    code: string;
    constructor(message: string, code: string) {
      super(message);
      this.name = 'ChatServiceError';
      this.code = code;
    }
  },
}));

const mockCreateChatSession = vi.mocked(chatService.createChatSession);
const mockSendChatMessage = vi.mocked(chatService.sendChatMessage);
const mockListProviders = vi.mocked(chatService.listProviders);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setupSuccessfulChat(sessionId = 'session-123', responseText = 'Hello from assistant') {
  mockCreateChatSession.mockResolvedValue({ session_id: sessionId });
  mockSendChatMessage.mockResolvedValue({ response: responseText, turn_number: 1 });
}

/**
 * Arrange the widget at a specific turn count without UI interaction.
 * Sends `turnsToSend` messages, each returning turn_number = its index + 1.
 * Returns the userEvent instance so the caller can continue interacting.
 */
async function setupWidgetAtTurn(turnsToSend: number) {
  mockCreateChatSession.mockResolvedValue({ session_id: 'session-cta' });
  for (let t = 1; t <= turnsToSend; t++) {
    mockSendChatMessage.mockResolvedValueOnce({ response: `Response ${t}`, turn_number: t });
  }

  const user = userEvent.setup();
  render(<ChatWidget visitorEmail={null} />);
  await user.click(screen.getByRole('button', { name: /open chat/i }));

  for (let t = 1; t <= turnsToSend; t++) {
    const textarea = screen.getByRole('textbox');
    await user.type(textarea, `Message ${t}`);
    await user.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() => {
      expect(screen.getByText(`Response ${t}`)).toBeInTheDocument();
    });
  }

  return user;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ChatWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('test_widget_is_closed_by_default', () => {
    render(<ChatWidget visitorEmail={null} />);

    // Chat panel should not be in the document
    expect(screen.queryByRole('log')).not.toBeInTheDocument();
    // The chat button should be visible
    expect(screen.getByRole('button', { name: /open chat/i })).toBeInTheDocument();
  });

  it('test_open_button_shows_panel', async () => {
    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    const openButton = screen.getByRole('button', { name: /open chat/i });
    await user.click(openButton);

    // Panel should now be visible
    expect(screen.getByRole('log')).toBeInTheDocument();
  });

  it('test_close_button_hides_panel', async () => {
    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    // Open panel
    await user.click(screen.getByRole('button', { name: /open chat/i }));
    expect(screen.getByRole('log')).toBeInTheDocument();

    // Close panel
    await user.click(screen.getByRole('button', { name: /close chat/i }));
    expect(screen.queryByRole('log')).not.toBeInTheDocument();
  });

  it('test_starter_questions_appear_when_no_messages', async () => {
    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    await user.click(screen.getByRole('button', { name: /open chat/i }));

    // All 4 starter questions should be visible
    expect(screen.getByText('What is the architecture of this platform?')).toBeInTheDocument();
    expect(screen.getByText('How does the simulation engine work?')).toBeInTheDocument();
    expect(screen.getByText('What technologies are used?')).toBeInTheDocument();
    expect(screen.getByText('How does data flow through the system?')).toBeInTheDocument();
  });

  it('test_starter_question_click_sends_message', async () => {
    setupSuccessfulChat();
    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    await user.click(screen.getByRole('button', { name: /open chat/i }));

    const starterBtn = screen.getByText('What is the architecture of this platform?');
    await user.click(starterBtn);

    // The user message should appear in the conversation
    await waitFor(() => {
      expect(screen.getByText('What is the architecture of this platform?')).toBeInTheDocument();
    });

    // Starter questions should be gone once messages exist
    await waitFor(() => {
      expect(mockCreateChatSession).toHaveBeenCalledOnce();
      expect(mockSendChatMessage).toHaveBeenCalledWith(
        'session-123',
        'What is the architecture of this platform?',
        undefined
      );
    });
  });

  it('test_loading_indicator_shown_while_request_pending', async () => {
    // Never resolve — keep it pending so we can observe the loading state
    mockCreateChatSession.mockImplementation(() => new Promise<{ session_id: string }>(() => {}));

    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    await user.click(screen.getByRole('button', { name: /open chat/i }));

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'Hello');
    await user.click(screen.getByRole('button', { name: /send/i }));

    // Typing indicator must be visible immediately
    expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();
  });

  it('test_loading_indicator_hidden_after_response', async () => {
    setupSuccessfulChat();
    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    await user.click(screen.getByRole('button', { name: /open chat/i }));

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'Hello');
    await user.click(screen.getByRole('button', { name: /send/i }));

    // Indicator disappears after response
    await waitFor(() => {
      expect(screen.queryByTestId('typing-indicator')).not.toBeInTheDocument();
    });
  });

  it('test_send_button_disabled_while_loading', async () => {
    mockCreateChatSession.mockImplementation(() => new Promise<{ session_id: string }>(() => {}));

    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    await user.click(screen.getByRole('button', { name: /open chat/i }));

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'Hello');

    const sendButton = screen.getByRole('button', { name: /send/i });
    await user.click(sendButton);

    expect(sendButton).toBeDisabled();
  });

  it('test_budget_exceeded_error_shows_user_message', async () => {
    mockCreateChatSession.mockRejectedValue(
      new ChatServiceError('Budget exceeded', 'BUDGET_EXCEEDED')
    );

    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    await user.click(screen.getByRole('button', { name: /open chat/i }));

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'Hello');
    await user.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => {
      expect(
        screen.getByText('The chat has reached its daily limit. Please try again tomorrow.')
      ).toBeInTheDocument();
    });
  });

  it('test_network_error_shows_user_message', async () => {
    mockCreateChatSession.mockRejectedValue(
      new ChatServiceError('Network failure', 'NETWORK_ERROR')
    );

    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    await user.click(screen.getByRole('button', { name: /open chat/i }));

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'Hello');
    await user.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => {
      expect(
        screen.getByText('Unable to connect. Please check your connection.')
      ).toBeInTheDocument();
    });
  });

  it('test_invalid_session_triggers_auto_retry', async () => {
    // First session creation succeeds
    mockCreateChatSession.mockResolvedValueOnce({ session_id: 'stale-session' });
    // First send fails with INVALID_SESSION
    mockSendChatMessage.mockRejectedValueOnce(
      new ChatServiceError('Session invalid', 'INVALID_SESSION')
    );
    // Auto-retry: new session created
    mockCreateChatSession.mockResolvedValueOnce({ session_id: 'fresh-session' });
    // Retry send succeeds
    mockSendChatMessage.mockResolvedValueOnce({ response: 'Retry success', turn_number: 1 });

    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    await user.click(screen.getByRole('button', { name: /open chat/i }));

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'Hello');
    await user.click(screen.getByRole('button', { name: /send/i }));

    // Should not show an error — auto-retry succeeds transparently
    await waitFor(() => {
      expect(screen.getByText('Retry success')).toBeInTheDocument();
    });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    // createChatSession should have been called twice (first + retry)
    expect(mockCreateChatSession).toHaveBeenCalledTimes(2);
  });

  it('test_message_input_cleared_after_send', async () => {
    setupSuccessfulChat();
    const user = userEvent.setup();
    render(<ChatWidget visitorEmail={null} />);

    await user.click(screen.getByRole('button', { name: /open chat/i }));

    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    await user.type(textarea, 'Hello there');
    expect(textarea.value).toBe('Hello there');

    await user.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => {
      expect(textarea.value).toBe('');
    });
  });

  // -------------------------------------------------------------------------
  // CTA tests
  // -------------------------------------------------------------------------

  describe('post-turn-5 engagement CTA', () => {
    const CTA_TEXT =
      "I see you're enjoying this. Do you want to book a video call with my creator, Andre Sbrocco? Drop him an e-mail!";

    it('test_cta_fires_after_turn_5_response', async () => {
      await setupWidgetAtTurn(5);

      await waitFor(() => {
        expect(screen.getByText(CTA_TEXT)).toBeInTheDocument();
      });
      expect(screen.getByTestId('cta-buttons')).toBeInTheDocument();
    });

    it('test_cta_message_appears_as_assistant_bubble', async () => {
      await setupWidgetAtTurn(5);

      await waitFor(() => {
        const ctaBubble = screen.getByText(CTA_TEXT);
        // The message is wrapped in the standard assistant bubble structure
        expect(ctaBubble.closest('.chat-message--assistant')).toBeInTheDocument();
      });
    });

    it('test_cta_does_not_fire_before_turn_5', async () => {
      await setupWidgetAtTurn(4);

      expect(screen.queryByText(CTA_TEXT)).not.toBeInTheDocument();
      expect(screen.queryByTestId('cta-buttons')).not.toBeInTheDocument();
      // Normal input should still be visible
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('test_normal_input_hidden_when_cta_shown', async () => {
      await setupWidgetAtTurn(5);

      await waitFor(() => {
        expect(screen.getByTestId('cta-buttons')).toBeInTheDocument();
      });
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });

    it('test_continue_chatting_restores_input', async () => {
      const user = await setupWidgetAtTurn(5);

      await waitFor(() => {
        expect(screen.getByTestId('cta-buttons')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('cta-continue-btn'));

      await waitFor(() => {
        expect(screen.getByRole('textbox')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('cta-buttons')).not.toBeInTheDocument();
    });

    it('test_email_andre_restores_input', async () => {
      const user = await setupWidgetAtTurn(5);

      await waitFor(() => {
        expect(screen.getByTestId('cta-buttons')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('cta-email-btn'));

      await waitFor(() => {
        expect(screen.getByRole('textbox')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('cta-buttons')).not.toBeInTheDocument();
    });

    it('test_cta_fires_exactly_once_per_session', async () => {
      // Reach turn 5 — CTA fires
      mockCreateChatSession.mockResolvedValue({ session_id: 'session-cta' });
      for (let t = 1; t <= 5; t++) {
        mockSendChatMessage.mockResolvedValueOnce({ response: `Response ${t}`, turn_number: t });
      }
      // Turn 6 response
      mockSendChatMessage.mockResolvedValueOnce({ response: 'Response 6', turn_number: 6 });

      const user = userEvent.setup();
      render(<ChatWidget visitorEmail={null} />);
      await user.click(screen.getByRole('button', { name: /open chat/i }));

      // Send 5 messages to trigger CTA
      for (let t = 1; t <= 5; t++) {
        const textarea = screen.getByRole('textbox');
        await user.type(textarea, `Message ${t}`);
        await user.click(screen.getByRole('button', { name: /send/i }));
        await waitFor(() => {
          expect(screen.getByText(`Response ${t}`)).toBeInTheDocument();
        });
      }

      await waitFor(() => {
        expect(screen.getByTestId('cta-buttons')).toBeInTheDocument();
      });

      // Dismiss CTA via "Continue chatting"
      await user.click(screen.getByTestId('cta-continue-btn'));
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toBeInTheDocument();
      });

      // Send a 6th message
      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'Message 6');
      await user.click(screen.getByRole('button', { name: /send/i }));
      await waitFor(() => {
        expect(screen.getByText('Response 6')).toBeInTheDocument();
      });

      // CTA must not reappear
      const ctaMessages = screen.queryAllByText(CTA_TEXT);
      expect(ctaMessages).toHaveLength(1); // original CTA still in message history
      expect(screen.queryByTestId('cta-buttons')).not.toBeInTheDocument();
    });

    it('test_cta_does_not_appear_at_turn_6', async () => {
      // Return turn_number 6 directly (simulate a late join or cached count)
      mockCreateChatSession.mockResolvedValue({ session_id: 'session-cta' });
      mockSendChatMessage.mockResolvedValueOnce({ response: 'Response 6', turn_number: 6 });

      const user = userEvent.setup();
      render(<ChatWidget visitorEmail={null} />);
      await user.click(screen.getByRole('button', { name: /open chat/i }));

      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'Hello');
      await user.click(screen.getByRole('button', { name: /send/i }));

      await waitFor(() => {
        expect(screen.getByText('Response 6')).toBeInTheDocument();
      });

      expect(screen.queryByText(CTA_TEXT)).not.toBeInTheDocument();
      expect(screen.queryByTestId('cta-buttons')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Provider dropdown tests
  // -------------------------------------------------------------------------

  describe('provider dropdown', () => {
    const TWO_PROVIDERS = {
      providers: [
        { name: 'anthropic', default: true },
        { name: 'openai', default: false },
      ],
    };

    it('test_provider_dropdown_appears_after_opening_panel', async () => {
      mockListProviders.mockResolvedValueOnce(TWO_PROVIDERS);

      const user = userEvent.setup();
      render(<ChatWidget visitorEmail={null} />);
      await user.click(screen.getByRole('button', { name: /open chat/i }));

      await waitFor(() => {
        expect(screen.getByRole('combobox', { name: /select llm provider/i })).toBeInTheDocument();
      });

      // Should have 2 options
      const select = screen.getByRole('combobox', { name: /select llm provider/i });
      const options = select.querySelectorAll('option');
      expect(options).toHaveLength(2);
    });

    it('test_dropdown_disabled_while_loading', async () => {
      mockListProviders.mockResolvedValueOnce(TWO_PROVIDERS);
      // Keep createChatSession pending so loading stays true
      mockCreateChatSession.mockImplementation(() => new Promise<{ session_id: string }>(() => {}));

      const user = userEvent.setup();
      render(<ChatWidget visitorEmail={null} />);
      await user.click(screen.getByRole('button', { name: /open chat/i }));

      // Wait for providers to load
      await waitFor(() => {
        expect(screen.getByRole('combobox', { name: /select llm provider/i })).toBeInTheDocument();
      });

      // Send a message to trigger loading state
      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'Hello');
      await user.click(screen.getByRole('button', { name: /send/i }));

      // Dropdown should be disabled while loading
      const select = screen.getByRole('combobox', { name: /select llm provider/i });
      expect(select).toBeDisabled();
    });

    it('test_selected_provider_passed_to_sendChatMessage', async () => {
      mockListProviders.mockResolvedValueOnce(TWO_PROVIDERS);
      mockCreateChatSession.mockResolvedValueOnce({ session_id: 'session-prov' });
      mockSendChatMessage.mockResolvedValueOnce({ response: 'From OpenAI', turn_number: 1 });

      const user = userEvent.setup();
      render(<ChatWidget visitorEmail={null} />);
      await user.click(screen.getByRole('button', { name: /open chat/i }));

      // Wait for providers to load
      await waitFor(() => {
        expect(screen.getByRole('combobox', { name: /select llm provider/i })).toBeInTheDocument();
      });

      // Select the non-default provider
      const select = screen.getByRole('combobox', { name: /select llm provider/i });
      await user.selectOptions(select, 'openai');

      // Send a message
      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'Hello');
      await user.click(screen.getByRole('button', { name: /send/i }));

      await waitFor(() => {
        expect(screen.getByText('From OpenAI')).toBeInTheDocument();
      });

      expect(mockSendChatMessage).toHaveBeenCalledWith('session-prov', 'Hello', 'openai');
    });

    it('test_widget_works_gracefully_when_listProviders_fails', async () => {
      mockListProviders.mockRejectedValueOnce(new Error('Service unavailable'));
      setupSuccessfulChat();

      const user = userEvent.setup();
      render(<ChatWidget visitorEmail={null} />);
      await user.click(screen.getByRole('button', { name: /open chat/i }));

      // No dropdown should appear
      await waitFor(() => {
        expect(screen.getByRole('log')).toBeInTheDocument();
      });
      expect(
        screen.queryByRole('combobox', { name: /select llm provider/i })
      ).not.toBeInTheDocument();

      // Widget should still work for sending messages
      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'Hello');
      await user.click(screen.getByRole('button', { name: /send/i }));

      await waitFor(() => {
        expect(screen.getByText('Hello from assistant')).toBeInTheDocument();
      });
    });
  });
});
