import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ZoneInspector } from '../ZoneInspector';
import type { ZoneData, ZoneFeature } from '../../../types/api';

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

const mockZoneData: ZoneData = {
  feature: mockZoneFeature,
  surge: 1.5,
  driver_count: 12,
};

describe('ZoneInspector', () => {
  it('renders zone name', () => {
    render(<ZoneInspector zone={mockZoneData} />);

    expect(screen.getByText('Vila Mariana')).toBeInTheDocument();
  });

  it('renders surge multiplier', () => {
    render(<ZoneInspector zone={mockZoneData} />);

    expect(screen.getByText('1.5x')).toBeInTheDocument();
  });

  it('renders driver count', () => {
    render(<ZoneInspector zone={mockZoneData} />);

    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('renders zone heading', () => {
    render(<ZoneInspector zone={mockZoneData} />);

    expect(screen.getByRole('heading', { name: 'Zone' })).toBeInTheDocument();
  });

  it('renders surge label', () => {
    render(<ZoneInspector zone={mockZoneData} />);

    expect(screen.getByText(/surge multiplier/i)).toBeInTheDocument();
  });

  it('renders drivers label', () => {
    render(<ZoneInspector zone={mockZoneData} />);

    expect(screen.getByText(/drivers/i)).toBeInTheDocument();
  });

  it('handles high surge values', () => {
    const highSurgeData: ZoneData = {
      ...mockZoneData,
      surge: 2.5,
    };

    render(<ZoneInspector zone={highSurgeData} />);

    expect(screen.getByText('2.5x')).toBeInTheDocument();
  });

  it('handles zero drivers', () => {
    const noDriversData: ZoneData = {
      ...mockZoneData,
      driver_count: 0,
    };

    render(<ZoneInspector zone={noDriversData} />);

    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('handles base surge (1.0x)', () => {
    const baseSurgeData: ZoneData = {
      ...mockZoneData,
      surge: 1.0,
    };

    render(<ZoneInspector zone={baseSurgeData} />);

    expect(screen.getByText('1x')).toBeInTheDocument();
  });
});
