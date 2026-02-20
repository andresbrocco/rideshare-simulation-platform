import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MapLegend from '../MapLegend';

describe('MapLegend', () => {
  it('renders_color_swatches', () => {
    render(<MapLegend />);

    const onlineDriverSwatch = screen.getByTestId('swatch-online-drivers');
    const offlineDriverSwatch = screen.getByTestId('swatch-offline-drivers');
    const requestingRiderSwatch = screen.getByTestId('swatch-requesting-riders');
    const inTransitRiderSwatch = screen.getByTestId('swatch-in-transit-riders');
    const tripRouteSwatch = screen.getByTestId('swatch-trip-routes');
    const zoneBoundarySwatch = screen.getByTestId('swatch-zone-boundaries');
    const surgeHeatmapSwatch = screen.getByTestId('swatch-surge-heatmap');

    expect(onlineDriverSwatch).toBeInTheDocument();
    expect(offlineDriverSwatch).toBeInTheDocument();
    expect(requestingRiderSwatch).toBeInTheDocument();
    expect(inTransitRiderSwatch).toBeInTheDocument();
    expect(tripRouteSwatch).toBeInTheDocument();
    expect(zoneBoundarySwatch).toBeInTheDocument();
    expect(surgeHeatmapSwatch).toBeInTheDocument();
  });

  it('legend_items_match_controls', () => {
    render(<MapLegend />);

    const legendItems = screen.getAllByRole('listitem');
    expect(legendItems).toHaveLength(14);

    expect(legendItems[0]).toHaveTextContent(/available/i);
    expect(legendItems[1]).toHaveTextContent(/offline/i);
  });

  it('shows_status_labels', () => {
    render(<MapLegend />);

    expect(screen.getByText(/available/i)).toBeInTheDocument();
    expect(screen.getByText(/offline/i)).toBeInTheDocument();
    expect(screen.getByText(/to pickup/i)).toBeInTheDocument();
    expect(screen.getByText(/requesting/i)).toBeInTheDocument();
    expect(screen.getByText(/in transit/i)).toBeInTheDocument();
  });
});
