import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LayerControls from '../LayerControls';

describe('LayerControls', () => {
  it('renders_all_layer_checkboxes', () => {
    const mockOnChange = vi.fn();
    const visibility = {
      onlineDrivers: true,
      offlineDrivers: false,
      busyDrivers: true,
      waitingRiders: true,
      inTransitRiders: true,
      tripRoutes: true,
      gpsTrails: true,
      zoneBoundaries: true,
      surgeHeatmap: false,
    };

    render(<LayerControls visibility={visibility} onChange={mockOnChange} />);

    expect(screen.getByLabelText(/online drivers/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/offline drivers/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/busy drivers/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/waiting riders/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/in-transit riders/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/trip routes/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/gps trails/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/zone boundaries/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/surge heatmap/i)).toBeInTheDocument();
  });

  it('default_visibility_state', () => {
    const mockOnChange = vi.fn();
    const visibility = {
      onlineDrivers: true,
      offlineDrivers: false,
      busyDrivers: true,
      waitingRiders: true,
      inTransitRiders: true,
      tripRoutes: true,
      gpsTrails: true,
      zoneBoundaries: true,
      surgeHeatmap: false,
    };

    render(<LayerControls visibility={visibility} onChange={mockOnChange} />);

    expect(screen.getByLabelText(/online drivers/i)).toBeChecked();
    expect(screen.getByLabelText(/offline drivers/i)).not.toBeChecked();
    expect(screen.getByLabelText(/busy drivers/i)).toBeChecked();
    expect(screen.getByLabelText(/waiting riders/i)).toBeChecked();
    expect(screen.getByLabelText(/in-transit riders/i)).toBeChecked();
    expect(screen.getByLabelText(/trip routes/i)).toBeChecked();
    expect(screen.getByLabelText(/gps trails/i)).toBeChecked();
    expect(screen.getByLabelText(/zone boundaries/i)).toBeChecked();
    expect(screen.getByLabelText(/surge heatmap/i)).not.toBeChecked();
  });

  it('toggles_layer_visibility', async () => {
    const user = userEvent.setup();
    const mockOnChange = vi.fn();
    const visibility = {
      onlineDrivers: true,
      offlineDrivers: false,
      busyDrivers: true,
      waitingRiders: true,
      inTransitRiders: true,
      tripRoutes: true,
      gpsTrails: true,
      zoneBoundaries: true,
      surgeHeatmap: false,
    };

    render(<LayerControls visibility={visibility} onChange={mockOnChange} />);

    const offlineDriversCheckbox = screen.getByLabelText(/offline drivers/i);
    await user.click(offlineDriversCheckbox);

    expect(mockOnChange).toHaveBeenCalledWith({
      ...visibility,
      offlineDrivers: true,
    });
  });

  it('toggles_all_layers', async () => {
    const user = userEvent.setup();
    const mockOnChange = vi.fn();
    const visibility = {
      onlineDrivers: true,
      offlineDrivers: false,
      busyDrivers: true,
      waitingRiders: true,
      inTransitRiders: true,
      tripRoutes: true,
      gpsTrails: true,
      zoneBoundaries: true,
      surgeHeatmap: false,
    };

    render(<LayerControls visibility={visibility} onChange={mockOnChange} />);

    const toggleAllButton = screen.getByRole('button', { name: /toggle all/i });
    await user.click(toggleAllButton);

    expect(mockOnChange).toHaveBeenCalledWith({
      onlineDrivers: false,
      offlineDrivers: false,
      busyDrivers: false,
      waitingRiders: false,
      inTransitRiders: false,
      tripRoutes: false,
      gpsTrails: false,
      zoneBoundaries: false,
      surgeHeatmap: false,
    });
  });

  it('collapsible_panel', async () => {
    const user = userEvent.setup();
    const mockOnChange = vi.fn();
    const visibility = {
      onlineDrivers: true,
      offlineDrivers: false,
      busyDrivers: true,
      waitingRiders: true,
      inTransitRiders: true,
      tripRoutes: true,
      gpsTrails: true,
      zoneBoundaries: true,
      surgeHeatmap: false,
    };

    render(<LayerControls visibility={visibility} onChange={mockOnChange} />);

    const collapseButton = screen.getByRole('button', { name: /collapse/i });
    await user.click(collapseButton);

    expect(screen.queryByLabelText(/online drivers/i)).not.toBeInTheDocument();
  });
});
