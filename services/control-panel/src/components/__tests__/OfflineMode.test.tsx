import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { OfflineMode } from '../OfflineMode';

// Mock canvas-confetti
vi.mock('canvas-confetti', () => ({
  default: {
    create: () => vi.fn(),
  },
}));

// jsdom doesn't implement SVG geometry methods.
// jsdom renders <path> as SVGElement (not SVGPathElement), so patch SVGElement.prototype.
// @ts-expect-error -- SVGElement doesn't declare getTotalLength, but jsdom <path> elements are SVGElement
SVGElement.prototype.getTotalLength = vi.fn().mockReturnValue(900);
// @ts-expect-error -- same as above
SVGElement.prototype.getPointAtLength = vi.fn().mockReturnValue({ x: 100, y: 40 });

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

describe('OfflineMode', () => {
  it('renders project title and subtitle', () => {
    render(<OfflineMode />);

    expect(
      screen.getByRole('heading', { level: 1, name: 'Rideshare Simulation Platform' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Real-time Event-Driven Data Engineering \u2014 Portfolio Project')
    ).toBeInTheDocument();
  });

  it('renders project overview description', () => {
    render(<OfflineMode />);

    expect(screen.getByText(/event-driven data engineering platform/i)).toBeInTheDocument();
  });

  it('shows architecture highlights', () => {
    render(<OfflineMode />);

    const archHeading = screen.getByRole('heading', {
      level: 2,
      name: 'Architecture Highlights',
    });
    const archSection = archHeading.closest('section');
    expect(archSection).not.toBeNull();

    const sectionScope = within(archSection!);
    expect(sectionScope.getByText(/SimPy discrete-event simulation/i)).toBeInTheDocument();
    expect(sectionScope.getByText(/Kafka event streaming/i)).toBeInTheDocument();
    expect(sectionScope.getByText(/Medallion lakehouse.*Delta Lake/i)).toBeInTheDocument();
    expect(sectionScope.getByText(/React \+ deck\.gl/i)).toBeInTheDocument();
  });

  it('shows technology stack section', () => {
    render(<OfflineMode />);

    const techHeading = screen.getByRole('heading', {
      level: 2,
      name: 'Technology Stack',
    });
    const techSection = techHeading.closest('section');
    expect(techSection).not.toBeNull();

    const sectionScope = within(techSection!);
    expect(sectionScope.getByText(/Python 3\.13/i)).toBeInTheDocument();
    expect(sectionScope.getByText(/TypeScript/)).toBeInTheDocument();
    expect(sectionScope.getByText(/Apache Kafka/)).toBeInTheDocument();
  });

  it('displays GitHub link with correct attributes', () => {
    render(<OfflineMode />);

    const link = screen.getByRole('link', { name: /View on GitHub/i });
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/andresbrocco/rideshare-simulation-platform'
    );
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('shows data pipeline section', () => {
    render(<OfflineMode />);

    expect(screen.getByRole('heading', { level: 2, name: 'Data Pipeline' })).toBeInTheDocument();
    expect(screen.getByText('Bronze')).toBeInTheDocument();
    expect(screen.getByText('Silver')).toBeInTheDocument();
    expect(screen.getByText('Gold')).toBeInTheDocument();
  });

  it('renders the trip lifecycle animation', () => {
    render(<OfflineMode />);

    expect(
      screen.getByRole('img', {
        name: 'Animated trip lifecycle: a driver picks up a rider and drives to the destination',
      })
    ).toBeInTheDocument();
  });
});
