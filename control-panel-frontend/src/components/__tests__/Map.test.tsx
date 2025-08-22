import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Layer } from '@deck.gl/core';
import Map from '../Map';

vi.mock('maplibre-gl/dist/maplibre-gl.css', () => ({}));

vi.mock('./Map.module.css', () => ({
  default: {
    'map-container': 'map-container',
  },
}));

vi.mock('react-map-gl/maplibre', () => ({
  Map: vi.fn(({ mapStyle, attributionControl }) => (
    <div data-testid="mapgl" data-map-style={mapStyle} data-attribution={attributionControl}>
      Map
    </div>
  )),
  MapRef: vi.fn(),
}));

vi.mock('@deck.gl/react', () => ({
  default: vi.fn(({ viewState, onViewStateChange, layers, controller, children }) => (
    <div
      data-testid="deckgl"
      data-view-state={JSON.stringify(viewState)}
      data-controller={controller}
      data-layers-count={layers.length}
      onClick={() => {
        if (onViewStateChange) {
          onViewStateChange({
            viewState: { ...viewState, latitude: -23.56 },
          });
        }
      }}
    >
      {children}
    </div>
  )),
}));

describe('Map', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('test_map_renders', () => {
    render(<Map />);

    expect(screen.getByTestId('deckgl')).toBeInTheDocument();
    expect(screen.getByTestId('mapgl')).toBeInTheDocument();
  });

  it('test_initial_view_state', () => {
    render(<Map />);

    const deckgl = screen.getByTestId('deckgl');
    const viewState = JSON.parse(deckgl.getAttribute('data-view-state') || '{}');

    expect(viewState.latitude).toBe(-23.55);
    expect(viewState.longitude).toBe(-46.63);
  });

  it('test_initial_zoom_level', () => {
    render(<Map />);

    const deckgl = screen.getByTestId('deckgl');
    const viewState = JSON.parse(deckgl.getAttribute('data-view-state') || '{}');

    expect(viewState.zoom).toBe(11);
  });

  it('test_uses_osm_tiles', () => {
    render(<Map />);

    const mapgl = screen.getByTestId('mapgl');
    const mapStyle = mapgl.getAttribute('data-map-style');

    expect(mapStyle).toContain('demotiles.maplibre.org');
  });

  it('test_handles_deck_overlay', () => {
    const mockLayers: Layer[] = [{ id: 'test-layer-1' } as Layer, { id: 'test-layer-2' } as Layer];

    render(<Map layers={mockLayers} />);

    const deckgl = screen.getByTestId('deckgl');
    expect(deckgl.getAttribute('data-layers-count')).toBe('2');
  });

  it('test_map_interactions_enabled', () => {
    render(<Map />);

    const deckgl = screen.getByTestId('deckgl');
    expect(deckgl.getAttribute('data-controller')).toBe('true');
  });

  it('test_map_full_viewport', () => {
    render(<Map />);

    const deckgl = screen.getByTestId('deckgl');
    expect(deckgl.parentElement).toBeInTheDocument();
    expect(deckgl.parentElement?.className).toContain('map-container');
  });
});
