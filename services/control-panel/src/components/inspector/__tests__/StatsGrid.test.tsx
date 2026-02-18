import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatsGrid } from '../StatsGrid';

describe('StatsGrid', () => {
  const mockStats = [
    { label: 'Completed', value: 100 },
    { label: 'Cancelled', value: 5 },
    { label: 'Offers', value: 120 },
    { label: 'Accept Rate', value: '85%' },
  ];

  it('renders all stat items', () => {
    render(<StatsGrid stats={mockStats} />);

    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Cancelled')).toBeInTheDocument();
    expect(screen.getByText('Offers')).toBeInTheDocument();
    expect(screen.getByText('Accept Rate')).toBeInTheDocument();
  });

  it('renders stat values', () => {
    render(<StatsGrid stats={mockStats} />);

    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('renders empty grid when no stats provided', () => {
    const { container } = render(<StatsGrid stats={[]} />);

    const grid = container.querySelector('.statsGrid');
    expect(grid).toBeInTheDocument();
    expect(grid?.children.length).toBe(0);
  });

  it('applies grid styling', () => {
    const { container } = render(<StatsGrid stats={mockStats} />);

    const grid = container.firstChild;
    expect(grid).toHaveClass('statsGrid');
  });

  it('applies stat item styling', () => {
    const { container } = render(<StatsGrid stats={mockStats} />);

    const statItems = container.querySelectorAll('.statItem');
    expect(statItems.length).toBe(4);
  });

  it('applies stat value styling', () => {
    render(<StatsGrid stats={[{ label: 'Test', value: 42 }]} />);

    const value = screen.getByText('42');
    expect(value).toHaveClass('statValue');
  });

  it('applies stat label styling', () => {
    render(<StatsGrid stats={[{ label: 'Test Label', value: 42 }]} />);

    const label = screen.getByText('Test Label');
    expect(label).toHaveClass('statLabel');
  });

  it('handles single stat', () => {
    render(<StatsGrid stats={[{ label: 'Only One', value: 1 }]} />);

    expect(screen.getByText('Only One')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });
});
