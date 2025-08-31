import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MapLegend from '../MapLegend';

describe('MapLegend', () => {
  it('renders_color_swatches', () => {
    render(<MapLegend />);

    const onlineDriverSwatch = screen.getByTestId('swatch-online-drivers');
    const offlineDriverSwatch = screen.getByTestId('swatch-offline-drivers');
    const busyDriverSwatch = screen.getByTestId('swatch-busy-drivers');
    const waitingRiderSwatch = screen.getByTestId('swatch-waiting-riders');
    const inTransitRiderSwatch = screen.getByTestId('swatch-in-transit-riders');
    const tripRouteSwatch = screen.getByTestId('swatch-trip-routes');
    const gpsTrailSwatch = screen.getByTestId('swatch-gps-trails');
    const zoneBoundarySwatch = screen.getByTestId('swatch-zone-boundaries');
    const surgeHeatmapSwatch = screen.getByTestId('swatch-surge-heatmap');

    expect(onlineDriverSwatch).toBeInTheDocument();
    expect(offlineDriverSwatch).toBeInTheDocument();
    expect(busyDriverSwatch).toBeInTheDocument();
    expect(waitingRiderSwatch).toBeInTheDocument();
    expect(inTransitRiderSwatch).toBeInTheDocument();
    expect(tripRouteSwatch).toBeInTheDocument();
    expect(gpsTrailSwatch).toBeInTheDocument();
    expect(zoneBoundarySwatch).toBeInTheDocument();
    expect(surgeHeatmapSwatch).toBeInTheDocument();
  });

  it('legend_items_match_controls', () => {
    render(<MapLegend />);

    const legendItems = screen.getAllByRole('listitem');
    expect(legendItems).toHaveLength(9);

    expect(legendItems[0]).toHaveTextContent(/online drivers/i);
    expect(legendItems[1]).toHaveTextContent(/offline drivers/i);
    expect(legendItems[2]).toHaveTextContent(/busy drivers/i);
    expect(legendItems[3]).toHaveTextContent(/waiting riders/i);
    expect(legendItems[4]).toHaveTextContent(/in-transit riders/i);
    expect(legendItems[5]).toHaveTextContent(/trip routes/i);
    expect(legendItems[6]).toHaveTextContent(/gps trails/i);
    expect(legendItems[7]).toHaveTextContent(/zone boundaries/i);
    expect(legendItems[8]).toHaveTextContent(/surge heatmap/i);
  });

  it('shows_status_labels', () => {
    render(<MapLegend />);

    expect(screen.getByText(/online/i)).toBeInTheDocument();
    expect(screen.getByText(/offline/i)).toBeInTheDocument();
    expect(screen.getByText(/busy/i)).toBeInTheDocument();
    expect(screen.getByText(/waiting/i)).toBeInTheDocument();
    expect(screen.getByText(/in transit/i)).toBeInTheDocument();
  });
});
