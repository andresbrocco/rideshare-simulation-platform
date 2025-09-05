import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ControlPanel from '../ControlPanel';
import type { SimulationStatus } from '../../types/api';

describe('ControlPanel', () => {
  const mockStatus: SimulationStatus = {
    state: 'STOPPED',
    speed_multiplier: 1,
    current_time: '2024-08-25T10:30:00Z',
    drivers_count: 50,
    riders_count: 20,
    active_trips_count: 10,
    uptime_seconds: 3600,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    Storage.prototype.getItem = vi.fn(() => 'test-api-key');
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000');
  });

  it('test_renders_control_buttons', () => {
    render(<ControlPanel status={mockStatus} />);

    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
  });

  it('test_play_button_calls_api', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({ ok: true });

    render(<ControlPanel status={mockStatus} />);

    const playButton = screen.getByRole('button', { name: /play/i });
    await user.click(playButton);

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/simulation/start', {
      method: 'POST',
      headers: { 'X-API-Key': 'test-api-key' },
    });
  });

  it('test_pause_button_calls_api', async () => {
    const user = userEvent.setup();
    const runningStatus = { ...mockStatus, state: 'RUNNING' as const };
    (global.fetch as Mock).mockResolvedValueOnce({ ok: true });

    render(<ControlPanel status={runningStatus} />);

    const pauseButton = screen.getByRole('button', { name: /pause/i });
    await user.click(pauseButton);

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/simulation/pause', {
      method: 'POST',
      headers: { 'X-API-Key': 'test-api-key' },
    });
  });

  it('test_reset_button_calls_api', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({ ok: true });

    render(<ControlPanel status={mockStatus} />);

    const resetButton = screen.getByRole('button', { name: /reset/i });
    await user.click(resetButton);

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/simulation/reset', {
      method: 'POST',
      headers: { 'X-API-Key': 'test-api-key' },
    });
  });

  it('test_speed_selector_changes', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({ ok: true });

    render(<ControlPanel status={mockStatus} />);

    const speedSelect = screen.getByLabelText(/speed/i);
    await user.selectOptions(speedSelect, '2');

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/simulation/speed', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'test-api-key',
      },
      body: JSON.stringify({ multiplier: 2 }),
    });
  });

  it('test_speed_selector_values', () => {
    render(<ControlPanel status={mockStatus} />);

    const speedSelect = screen.getByLabelText(/speed/i) as HTMLSelectElement;
    const options = Array.from(speedSelect.options).map((o) => o.value);

    expect(options).toEqual(['1', '2', '4', '8', '16', '32']);
  });

  it('autonomous_agent_creation_drivers', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({ ok: true });

    render(<ControlPanel status={mockStatus} />);

    const driverInput = screen.getByLabelText(/drivers/i);
    const addDriversButton = screen.getByRole('button', { name: /add drivers/i });

    await user.clear(driverInput);
    await user.type(driverInput, '5');
    await user.click(addDriversButton);

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/agents/drivers', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'test-api-key',
      },
      body: JSON.stringify({ count: 5 }),
    });
  });

  it('autonomous_agent_creation_riders', async () => {
    const user = userEvent.setup();
    (global.fetch as Mock).mockResolvedValueOnce({ ok: true });

    render(<ControlPanel status={mockStatus} />);

    const riderInput = screen.getByLabelText(/riders/i);
    const addRidersButton = screen.getByRole('button', { name: /add riders/i });

    await user.clear(riderInput);
    await user.type(riderInput, '3');
    await user.click(addRidersButton);

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/agents/riders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'test-api-key',
      },
      body: JSON.stringify({ count: 3 }),
    });
  });

  it('test_displays_status_indicator', () => {
    const runningStatus = { ...mockStatus, state: 'RUNNING' as const };
    render(<ControlPanel status={runningStatus} />);

    expect(screen.getByText('RUNNING')).toBeInTheDocument();
  });

  it('test_displays_simulation_time', () => {
    render(<ControlPanel status={mockStatus} />);

    expect(screen.getByText(/8\/25\/2024/)).toBeInTheDocument();
  });

  it('test_displays_statistics', () => {
    render(<ControlPanel status={mockStatus} />);

    const statsSection = screen.getByText('Statistics').closest('div');
    expect(statsSection).toHaveTextContent('50');
    expect(statsSection).toHaveTextContent('20');
    expect(statsSection).toHaveTextContent('10');
  });

  it('test_disables_play_when_running', () => {
    const runningStatus = { ...mockStatus, state: 'RUNNING' as const };
    render(<ControlPanel status={runningStatus} />);

    const playButton = screen.getByRole('button', { name: /play/i });
    expect(playButton).toBeDisabled();
  });

  it('test_disables_pause_when_stopped', () => {
    render(<ControlPanel status={mockStatus} />);

    const pauseButton = screen.getByRole('button', { name: /pause/i });
    expect(pauseButton).toBeDisabled();
  });
});
