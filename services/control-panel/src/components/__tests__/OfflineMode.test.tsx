import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { OfflineMode } from '../OfflineMode';

describe('OfflineMode', () => {
  it('renders project title and subtitle', () => {
    render(<OfflineMode />);

    expect(
      screen.getByRole('heading', { level: 1, name: 'Rideshare Simulation Platform' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Real-time Event-Driven Data Engineering Portfolio Project')
    ).toBeInTheDocument();
  });

  it('displays project description in About section', () => {
    render(<OfflineMode />);

    const aboutHeading = screen.getByRole('heading', {
      level: 2,
      name: 'About This Project',
    });
    const aboutSection = aboutHeading.closest('section');
    expect(aboutSection).not.toBeNull();

    const sectionScope = within(aboutSection!);
    expect(sectionScope.getByText(/event-driven data engineering platform/i)).toBeInTheDocument();
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

  it('shows offline notice with contact CTA', () => {
    render(<OfflineMode />);

    expect(
      screen.getByRole('heading', { level: 3, name: 'Demo Currently Offline' })
    ).toBeInTheDocument();
    expect(screen.getByText(/Contact me to schedule a live demo/i)).toBeInTheDocument();
  });

  it('includes screenshots placeholder', () => {
    render(<OfflineMode />);

    expect(
      screen.getByRole('heading', { level: 2, name: 'Live Simulation Preview' })
    ).toBeInTheDocument();
    expect(screen.getByText(/Screenshots and screen recordings/i)).toBeInTheDocument();
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
    expect(sectionScope.getByText(/Kafka \+ Schema Registry/)).toBeInTheDocument();
  });
});
