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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setupSuccessfulChat(sessionId = 'session-123', responseText = 'Hello from assistant') {
  mockCreateChatSession.mockResolvedValue({ session_id: sessionId });
  mockSendChatMessage.mockResolvedValue({ response: responseText, turn_number: 1 });
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
        'What is the architecture of this platform?'
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
});
