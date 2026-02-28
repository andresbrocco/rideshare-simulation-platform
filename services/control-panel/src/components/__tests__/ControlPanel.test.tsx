import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ControlPanel from '../ControlPanel';
import type { SimulationStatus } from '../../types/api';

// Mock all hooks that make API calls
const mockStartSimulation = vi.fn();
const mockPauseSimulation = vi.fn();
const mockResumeSimulation = vi.fn();
const mockResetSimulation = vi.fn();
const mockSetSpeed = vi.fn();
const mockAddDrivers = vi.fn();
const mockAddRiders = vi.fn();

vi.mock('../../hooks/useSimulationControl', () => ({
  useSimulationControl: () => ({
    startSimulation: mockStartSimulation,
    pauseSimulation: mockPauseSimulation,
    resumeSimulation: mockResumeSimulation,
    resetSimulation: mockResetSimulation,
    setSpeed: mockSetSpeed,
    addDrivers: mockAddDrivers,
    addRiders: mockAddRiders,
    loading: false,
    error: null,
  }),
}));

vi.mock('../../hooks/useMetrics', () => ({
  useMetrics: () => ({
    driverMetrics: null,
    tripMetrics: null,
    overviewMetrics: null,
    riderMetrics: null,
    loading: false,
  }),
}));

vi.mock('../../hooks/useInfrastructure', () => ({
  useInfrastructure: () => ({
    data: null,
    loading: false,
    error: null,
    refresh: vi.fn(),
  }),
}));

vi.mock('../../hooks/usePerformanceMetrics', () => ({
  usePerformanceMetrics: () => ({
    metrics: null,
    loading: false,
    error: null,
    refresh: vi.fn(),
  }),
}));

vi.mock('../../hooks/usePerformanceContext', () => ({
  usePerformanceContext: () => ({
    frontendMetrics: {
      ws_messages_per_sec: 0,
      render_fps: 60,
    },
    recordWsMessage: vi.fn(),
  }),
}));

vi.mock('../../hooks/usePerformanceController', () => ({
  usePerformanceController: () => ({
    status: null,
    setMode: vi.fn(),
  }),
}));

describe('ControlPanel', () => {
  const mockStatus: SimulationStatus = {
    state: 'stopped',
    speed_multiplier: 1,
    current_time: '2024-08-25T10:30:00Z',
    drivers_total: 50,
    drivers_offline: 10,
    drivers_available: 30,
    drivers_en_route_pickup: 5,
    drivers_on_trip: 5,
    drivers_driving_closer_to_home: 0,
    riders_total: 20,
    riders_idle: 5,
    riders_requesting: 10,
    riders_awaiting_pickup: 0,
    riders_on_trip: 5,
    active_trips_count: 10,
    uptime_seconds: 3600,
    real_time_ratio: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('test_renders_control_buttons', () => {
    render(<ControlPanel status={mockStatus} />);

    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
  });

  it('test_play_button_calls_api', async () => {
    const user = userEvent.setup();

    render(<ControlPanel status={mockStatus} />);

    const playButton = screen.getByRole('button', { name: /play/i });
    await user.click(playButton);

    expect(mockStartSimulation).toHaveBeenCalled();
  });

  it('test_pause_button_calls_api', async () => {
    const user = userEvent.setup();
    const runningStatus = { ...mockStatus, state: 'running' as const };

    render(<ControlPanel status={runningStatus} />);

    const pauseButton = screen.getByRole('button', { name: /pause/i });
    await user.click(pauseButton);

    expect(mockPauseSimulation).toHaveBeenCalled();
  });

  it('test_reset_button_calls_api', async () => {
    const user = userEvent.setup();

    render(<ControlPanel status={mockStatus} />);

    const resetButton = screen.getByRole('button', { name: /reset/i });
    await user.click(resetButton);

    // Reset button opens a confirmation modal
    const confirmButton = screen.getByRole('button', { name: /reset everything/i });
    await user.click(confirmButton);

    expect(mockResetSimulation).toHaveBeenCalled();
  });

  it('test_speed_selector_changes', async () => {
    const user = userEvent.setup();

    render(<ControlPanel status={mockStatus} />);

    const speedSelect = screen.getByLabelText(/speed/i);
    await user.selectOptions(speedSelect, '2');

    expect(mockSetSpeed).toHaveBeenCalledWith(2);
  });

  it('test_speed_selector_changes_fractional', async () => {
    const user = userEvent.setup();
    render(<ControlPanel status={mockStatus} />);
    const speedSelect = screen.getByLabelText(/speed/i);
    await user.selectOptions(speedSelect, '0.5');
    expect(mockSetSpeed).toHaveBeenCalledWith(0.5);
  });

  it('test_speed_selector_values', () => {
    render(<ControlPanel status={mockStatus} />);

    const speedSelect = screen.getByLabelText(/speed/i) as HTMLSelectElement;
    const options = Array.from(speedSelect.options).map((o) => o.value);

    expect(options).toContain('0.5');
    expect(options).toContain('1');
    expect(options).toContain('2');
    expect(options).toContain('4');
    expect(options).toContain('8');
    expect(options).toContain('16');
    expect(options).toContain('32');
  });

  it('autonomous_agent_creation_drivers', async () => {
    const user = userEvent.setup();

    render(<ControlPanel status={mockStatus} />);

    const driverInput = screen.getByLabelText(/drivers/i);
    // Get the Add button in the drivers section (first Add button after driver input)
    const addButtons = screen.getAllByRole('button', { name: /^add$/i });
    const addDriversButton = addButtons[0];

    await user.clear(driverInput);
    await user.type(driverInput, '5');
    await user.click(addDriversButton);

    expect(mockAddDrivers).toHaveBeenCalledWith(5, 'immediate');
  });

  it('autonomous_agent_creation_riders', async () => {
    const user = userEvent.setup();

    render(<ControlPanel status={mockStatus} />);

    const riderInput = screen.getByLabelText(/riders/i);
    // Get the Add button in the riders section (second Add button after rider input)
    const addButtons = screen.getAllByRole('button', { name: /^add$/i });
    const addRidersButton = addButtons[1];

    await user.clear(riderInput);
    await user.type(riderInput, '3');
    await user.click(addRidersButton);

    expect(mockAddRiders).toHaveBeenCalledWith(3, 'immediate');
  });

  it('test_displays_status_indicator', () => {
    const runningStatus = { ...mockStatus, state: 'running' as const };
    render(<ControlPanel status={runningStatus} />);

    expect(screen.getByText('running')).toBeInTheDocument();
  });

  it('test_displays_simulation_time', () => {
    render(<ControlPanel status={mockStatus} />);

    expect(screen.getByText(/8\/25\/2024/)).toBeInTheDocument();
  });

  it('test_displays_statistics', () => {
    render(<ControlPanel status={mockStatus} />);

    // Check that the Statistics section header exists
    expect(screen.getByText('Statistics')).toBeInTheDocument();
  });

  it('test_disables_play_when_running', () => {
    const runningStatus = { ...mockStatus, state: 'running' as const };
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
