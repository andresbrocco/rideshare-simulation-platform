import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import InfrastructurePanel from '../InfrastructurePanel';
import type { InfrastructureResponse } from '../../types/api';

function buildMockData(overrides?: Partial<InfrastructureResponse>): InfrastructureResponse {
  return {
    services: [
      {
        name: 'simulation',
        status: 'healthy',
        latency_ms: 12,
        message: null,
        memory_used_mb: 256,
        memory_limit_mb: 1024,
        memory_percent: 25,
        cpu_percent: 3.1,
      },
      {
        name: 'kafka',
        status: 'healthy',
        latency_ms: 5,
        message: null,
        memory_used_mb: 512,
        memory_limit_mb: 2048,
        memory_percent: 25,
        cpu_percent: 8.5,
      },
    ],
    overall_status: 'healthy',
    cadvisor_available: true,
    timestamp: 1700000000,
    total_cpu_percent: 11.6,
    total_memory_used_mb: 768,
    total_memory_capacity_mb: 16384,
    total_memory_percent: 4.7,
    total_cores: 10,
    ...overrides,
  };
}

describe('InfrastructurePanel', () => {
  const defaultProps = {
    loading: false,
    error: null,
    onRefresh: vi.fn(),
    infrastructureHeadroom: null as number | null,
  };

  it('renders cores format for each service card', () => {
    const data = buildMockData();
    render(<InfrastructurePanel data={data} {...defaultProps} />);

    // simulation: 3.1% of 10 cores = 0.31 cores
    expect(screen.getByText(/0\.31/)).toBeInTheDocument();
    expect(screen.getByText(/0\.31 \/ 10 cores/)).toBeInTheDocument();

    // kafka: 8.5% of 10 cores = 0.85 cores
    expect(screen.getByText(/0\.85 \/ 10 cores/)).toBeInTheDocument();
  });

  it('renders percentage next to progress bar for services', () => {
    const data = buildMockData();
    render(<InfrastructurePanel data={data} {...defaultProps} />);

    expect(screen.getByText('3.1%')).toBeInTheDocument();
    expect(screen.getByText('8.5%')).toBeInTheDocument();
  });

  it('renders system totals with cores format', () => {
    const data = buildMockData();
    render(<InfrastructurePanel data={data} {...defaultProps} />);

    // total: 11.6% of 10 cores = 1.16 cores
    expect(screen.getByText(/1\.16 \/ 10 cores/)).toBeInTheDocument();
    expect(screen.getByText('11.6%')).toBeInTheDocument();
  });

  it('collapse toggle hides content', async () => {
    const user = userEvent.setup();
    const data = buildMockData();
    render(<InfrastructurePanel data={data} {...defaultProps} />);

    // Content visible initially
    expect(screen.getByText('simulation')).toBeInTheDocument();

    // Click collapse button
    const collapseButton = screen.getByRole('button', { name: /collapse/i });
    await user.click(collapseButton);

    // Content hidden
    expect(screen.queryByText('simulation')).not.toBeInTheDocument();
  });

  it('renders latency values without color classes', () => {
    const data = buildMockData({
      services: [
        {
          name: 'Redis',
          status: 'degraded',
          latency_ms: 10,
          message: 'Connected',
          memory_used_mb: 64,
          memory_limit_mb: 256,
          memory_percent: 25,
          cpu_percent: 1.0,
          threshold_degraded: 5,
          threshold_unhealthy: 20,
        },
        {
          name: 'Airflow Web',
          status: 'healthy',
          latency_ms: 200,
          message: 'MetaDB: healthy',
          memory_used_mb: 512,
          memory_limit_mb: 2048,
          memory_percent: 25,
          cpu_percent: 2.0,
          threshold_degraded: 500,
          threshold_unhealthy: 2000,
        },
      ],
    });
    const { container } = render(<InfrastructurePanel data={data} {...defaultProps} />);

    // Latency values render without color classes
    expect(container.querySelector('.latencyOrange')).not.toBeInTheDocument();
    expect(container.querySelector('.latencyGreen')).not.toBeInTheDocument();
    expect(container.querySelector('.latencyRed')).not.toBeInTheDocument();

    // Values still display correctly
    expect(screen.getByText('10 ms')).toBeInTheDocument();
    expect(screen.getByText('200 ms')).toBeInTheDocument();
  });

  it('shows warning when cAdvisor is unavailable', () => {
    const data = buildMockData({ cadvisor_available: false });
    render(<InfrastructurePanel data={data} {...defaultProps} />);

    expect(
      screen.getByText('Resource metrics unavailable (cAdvisor not running)')
    ).toBeInTheDocument();

    // CPU/memory sections should not render
    expect(screen.queryByText(/cores/)).not.toBeInTheDocument();
    expect(screen.queryByText('Total CPU')).not.toBeInTheDocument();
  });
});
