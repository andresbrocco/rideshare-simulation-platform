import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import InspectorPopup from '../InspectorPopup';
import type { Driver, Rider, ZoneData, ZoneFeature } from '../../types/api';

type InspectedEntity =
  | { type: 'zone'; data: ZoneData }
  | { type: 'driver'; data: Driver }
  | { type: 'rider'; data: Rider }
  | null;

const mockZoneFeature: ZoneFeature = {
  type: 'Feature',
  properties: {
    name: 'Vila Mariana',
    zone_id: 'zone_001',
    subprefecture: 'Vila Mariana',
    demand_multiplier: 1.2,
    surge_sensitivity: 0.8,
  },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 1],
        [0, 0],
      ],
    ],
  },
};

const mockZone: ZoneData = {
  feature: mockZoneFeature,
  surge: 1.5,
  driver_count: 12,
};

const mockDriver: Driver = {
  id: 'driver_123',
  latitude: -23.5505,
  longitude: -46.6333,
  status: 'available',
  rating: 4.7,
  zone: 'Vila Mariana',
};

const mockRider: Rider = {
  id: 'rider_456',
  latitude: -23.5489,
  longitude: -46.6388,
  status: 'on_trip',
  destination_latitude: -23.56,
  destination_longitude: -46.65,
};

const mockRiderWaiting: Rider = {
  id: 'rider_789',
  latitude: -23.5489,
  longitude: -46.6388,
  status: 'requesting',
};

describe('InspectorPopup', () => {
  const mockOnClose = vi.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    mockOnClose.mockClear();
    // Mock fetch to fail so fallback UI shows
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('test_render_zone_popup', () => {
    const entity: InspectedEntity = { type: 'zone', data: mockZone };
    render(<InspectorPopup entity={entity} x={100} y={100} onClose={mockOnClose} />);

    expect(screen.getByText('Vila Mariana')).toBeInTheDocument();
    expect(screen.getByText(/surge/i)).toBeInTheDocument();
    expect(screen.getByText('1.5x')).toBeInTheDocument();
    expect(screen.getByText(/drivers/i)).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('test_render_driver_popup', async () => {
    const entity: InspectedEntity = { type: 'driver', data: mockDriver };
    render(<InspectorPopup entity={entity} x={100} y={100} onClose={mockOnClose} />);

    // Wait for fallback UI to render after API fails
    await waitFor(() => {
      expect(screen.getByText(/driver_123/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/available/i)).toBeInTheDocument();
    expect(screen.getByText('4.7')).toBeInTheDocument();
  });

  it('test_render_rider_popup', async () => {
    const entity: InspectedEntity = { type: 'rider', data: mockRider };
    render(<InspectorPopup entity={entity} x={100} y={100} onClose={mockOnClose} />);

    // Wait for fallback UI to render after API fails
    await waitFor(() => {
      expect(screen.getByText(/rider_456/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/on_trip/i)).toBeInTheDocument();
    expect(screen.getByText(/-23.5600/)).toBeInTheDocument();
    expect(screen.getByText(/-46.6500/)).toBeInTheDocument();
  });

  it('test_rider_popup_no_destination', async () => {
    const entity: InspectedEntity = { type: 'rider', data: mockRiderWaiting };
    render(<InspectorPopup entity={entity} x={100} y={100} onClose={mockOnClose} />);

    // Wait for fallback UI to render after API fails
    await waitFor(() => {
      expect(screen.getByText(/rider_789/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/requesting/i)).toBeInTheDocument();
    expect(screen.getByText(/not set/i)).toBeInTheDocument();
  });

  it('test_popup_positioning', () => {
    // Set large window dimensions to avoid boundary adjustment
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 1920,
    });
    Object.defineProperty(window, 'innerHeight', {
      writable: true,
      configurable: true,
      value: 1080,
    });

    const entity: InspectedEntity = { type: 'zone', data: mockZone };
    const { container } = render(
      <InspectorPopup entity={entity} x={50} y={50} onClose={mockOnClose} />
    );

    const popup = container.querySelector('[data-testid="inspector-popup"]');
    expect(popup).toHaveStyle({ left: '50px', top: '50px' });
  });

  it('test_boundary_detection_right', () => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 1024,
    });

    const entity: InspectedEntity = { type: 'zone', data: mockZone };
    const { container } = render(
      <InspectorPopup entity={entity} x={974} y={100} onClose={mockOnClose} />
    );

    const popup = container.querySelector('[data-testid="inspector-popup"]');
    const left = parseInt(popup?.getAttribute('style')?.match(/left:\s*(\d+)px/)?.[1] || '0');
    expect(left).toBeLessThan(974);
  });

  it('test_boundary_detection_bottom', () => {
    Object.defineProperty(window, 'innerHeight', {
      writable: true,
      configurable: true,
      value: 768,
    });

    const entity: InspectedEntity = { type: 'zone', data: mockZone };
    const { container } = render(
      <InspectorPopup entity={entity} x={100} y={718} onClose={mockOnClose} />
    );

    const popup = container.querySelector('[data-testid="inspector-popup"]');
    const top = parseInt(popup?.getAttribute('style')?.match(/top:\s*(\d+)px/)?.[1] || '0');
    expect(top).toBeLessThan(718);
  });

  it('test_close_button', async () => {
    const user = userEvent.setup();
    const entity: InspectedEntity = { type: 'zone', data: mockZone };
    render(<InspectorPopup entity={entity} x={100} y={100} onClose={mockOnClose} />);

    const closeButton = screen.getByRole('button', { name: /close/i });
    await user.click(closeButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('test_null_entity', () => {
    const { container } = render(
      <InspectorPopup entity={null} x={100} y={100} onClose={mockOnClose} />
    );

    expect(container.querySelector('[data-testid="inspector-popup"]')).not.toBeInTheDocument();
  });

  it('test_dark_theme_styling', () => {
    const entity: InspectedEntity = { type: 'zone', data: mockZone };
    const { container } = render(
      <InspectorPopup entity={entity} x={100} y={100} onClose={mockOnClose} />
    );

    const popup = container.querySelector('[data-testid="inspector-popup"]');
    expect(popup?.className).toContain('popup');
  });
});
