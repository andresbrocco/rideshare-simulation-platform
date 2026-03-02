import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LandingPage } from '../LandingPage';

// jsdom doesn't implement SVG geometry methods.
// jsdom renders <path> as SVGElement (not SVGPathElement), so patch SVGElement.prototype.
// @ts-expect-error -- SVGElement doesn't declare getTotalLength, but jsdom <path> elements are SVGElement
SVGElement.prototype.getTotalLength = vi.fn().mockReturnValue(900);
// @ts-expect-error -- same as above
SVGElement.prototype.getPointAtLength = vi.fn().mockReturnValue({ x: 100, y: 40 });

const mockOnLoginClick = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
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

describe('LandingPage', () => {
  it('renders project title and subtitle', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    expect(
      screen.getByRole('heading', { level: 1, name: 'Rideshare Simulation Platform' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Real-time Event-Driven Data Engineering \u2014 Portfolio Project')
    ).toBeInTheDocument();
  });

  it('renders project overview description', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    expect(screen.getByText(/event-driven data engineering platform/i)).toBeInTheDocument();
  });

  it('shows architecture highlights', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

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
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

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
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    const link = screen.getByRole('link', { name: /View on GitHub/i });
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/andresbrocco/rideshare-simulation-platform'
    );
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('shows data pipeline section', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    expect(screen.getByRole('heading', { level: 2, name: 'Data Pipeline' })).toBeInTheDocument();
    expect(screen.getByText('Bronze')).toBeInTheDocument();
    expect(screen.getByText('Silver')).toBeInTheDocument();
    expect(screen.getByText('Gold')).toBeInTheDocument();
  });

  it('renders the trip lifecycle animation', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    expect(
      screen.getByRole('img', {
        name: 'Animated trip lifecycle: a driver picks up a rider and drives to the destination',
      })
    ).toBeInTheDocument();
  });

  it('renders Control Panel button in services grid', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    const controlPanelButton = screen.getByRole('button', { name: /control panel/i });
    expect(controlPanelButton).toBeInTheDocument();
  });

  it('calls onLoginClick when Control Panel button clicked', async () => {
    const user = userEvent.setup();
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    const controlPanelButton = screen.getByRole('button', { name: /control panel/i });
    await user.click(controlPanelButton);

    expect(mockOnLoginClick).toHaveBeenCalledOnce();
  });

  it('renders Explore the Platform heading', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    expect(
      screen.getByRole('heading', { level: 2, name: 'Explore the Platform' })
    ).toBeInTheDocument();
  });

  it('renders all external service links with correct attributes', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    const expectedServices = [
      { name: 'Grafana', url: 'https://grafana.ridesharing.portfolio.andresbrocco.com' },
      { name: 'Airflow', url: 'https://airflow.ridesharing.portfolio.andresbrocco.com' },
      { name: 'Trino', url: 'https://trino.ridesharing.portfolio.andresbrocco.com' },
      { name: 'Prometheus', url: 'https://prometheus.ridesharing.portfolio.andresbrocco.com' },
      { name: 'Simulation API', url: 'https://api.ridesharing.portfolio.andresbrocco.com/docs' },
    ];

    for (const service of expectedServices) {
      const link = screen.getByRole('link', { name: new RegExp(service.name) });
      expect(link).toHaveAttribute('href', service.url);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }
  });

  it('does not show Demo Offline badge', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} />);

    expect(screen.queryByText(/demo offline/i)).not.toBeInTheDocument();
  });
});
