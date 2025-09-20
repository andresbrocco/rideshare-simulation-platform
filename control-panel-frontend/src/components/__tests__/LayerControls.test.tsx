import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LayerControls from '../LayerControls';
import type { LayerVisibility } from '../../types/layers';

describe('LayerControls', () => {
  const fullVisibility: LayerVisibility = {
    onlineDrivers: true,
    offlineDrivers: false,
    enRoutePickupDrivers: true,
    withPassengerDrivers: true,
    offlineRiders: true,
    waitingRiders: true,
    matchedRiders: true,
    enRouteRiders: true,
    arrivedRiders: true,
    inTransitRiders: true,
    pendingRoutes: true,
    pickupRoutes: true,
    tripRoutes: true,
    zoneBoundaries: true,
    surgeHeatmap: false,
  };

  it('renders_all_layer_checkboxes', () => {
    const mockOnChange = vi.fn();

    render(<LayerControls visibility={fullVisibility} onChange={mockOnChange} />);

    // Driver layers - unique labels
    expect(screen.getByLabelText(/to pickup/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/with rider/i)).toBeInTheDocument();
    // "Online" and "Offline" appear in both driver and rider sections
    expect(screen.getAllByLabelText(/^online$/i)).toHaveLength(1);
    expect(screen.getAllByLabelText(/^offline$/i)).toHaveLength(2); // Driver + Rider

    // Rider layers
    expect(screen.getByLabelText(/waiting/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/in transit/i)).toBeInTheDocument();
    // Route layers
    expect(screen.getByLabelText(/trip routes/i)).toBeInTheDocument();
    // Zone layers
    expect(screen.getByLabelText(/zones/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/surge/i)).toBeInTheDocument();
  });

  it('default_visibility_state', () => {
    const mockOnChange = vi.fn();

    render(<LayerControls visibility={fullVisibility} onChange={mockOnChange} />);

    // Check checked state based on fullVisibility
    expect(screen.getByLabelText(/^online$/i)).toBeChecked();
    expect(screen.getByLabelText(/to pickup/i)).toBeChecked();
    expect(screen.getByLabelText(/waiting/i)).toBeChecked();
    expect(screen.getByLabelText(/in transit/i)).toBeChecked();
    expect(screen.getByLabelText(/trip routes/i)).toBeChecked();
    expect(screen.getByLabelText(/zones/i)).toBeChecked();
    expect(screen.getByLabelText(/surge/i)).not.toBeChecked();
  });

  it('toggles_layer_visibility', async () => {
    const user = userEvent.setup();
    const mockOnChange = vi.fn();

    render(<LayerControls visibility={fullVisibility} onChange={mockOnChange} />);

    const surgeCheckbox = screen.getByLabelText(/surge/i);
    await user.click(surgeCheckbox);

    expect(mockOnChange).toHaveBeenCalledWith({
      ...fullVisibility,
      surgeHeatmap: true,
    });
  });

  it('toggles_all_layers', async () => {
    const user = userEvent.setup();
    const mockOnChange = vi.fn();

    render(<LayerControls visibility={fullVisibility} onChange={mockOnChange} />);

    const toggleAllButton = screen.getByRole('button', { name: /toggle all/i });
    await user.click(toggleAllButton);

    expect(mockOnChange).toHaveBeenCalledWith({
      onlineDrivers: false,
      offlineDrivers: false,
      enRoutePickupDrivers: false,
      withPassengerDrivers: false,
      offlineRiders: false,
      waitingRiders: false,
      matchedRiders: false,
      enRouteRiders: false,
      arrivedRiders: false,
      inTransitRiders: false,
      pendingRoutes: false,
      pickupRoutes: false,
      tripRoutes: false,
      zoneBoundaries: false,
      surgeHeatmap: false,
    });
  });

  it('collapsible_panel', async () => {
    const user = userEvent.setup();
    const mockOnChange = vi.fn();

    render(<LayerControls visibility={fullVisibility} onChange={mockOnChange} />);

    const collapseButton = screen.getByRole('button', { name: /collapse/i });
    await user.click(collapseButton);

    expect(screen.queryByLabelText(/^online$/i)).not.toBeInTheDocument();
  });
});
