import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ArchitectureDiagram } from '../ArchitectureDiagram';

// jsdom doesn't implement SVG geometry methods.
// @ts-expect-error -- SVGElement doesn't declare getTotalLength, but jsdom elements are SVGElement
SVGElement.prototype.getTotalLength = vi.fn().mockReturnValue(900);
// @ts-expect-error -- same as above
SVGElement.prototype.getPointAtLength = vi.fn().mockReturnValue({ x: 100, y: 40 });

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

describe('ArchitectureDiagram', () => {
  it('test_architecture_diagram_renders_svg_with_role_img', () => {
    render(<ArchitectureDiagram />);

    const svg = screen.getByRole('img', { name: /system architecture/i });
    expect(svg).toBeInTheDocument();
    expect(svg.getAttribute('aria-label')).toBeTruthy();
  });

  it('test_architecture_section_has_correct_id', () => {
    render(<ArchitectureDiagram />);

    const section = document.getElementById('architecture');
    expect(section).not.toBeNull();
  });

  it('test_architecture_section_heading', () => {
    render(<ArchitectureDiagram />);

    const heading = screen.getByRole('heading', { level: 2, name: 'System Architecture' });
    expect(heading).toBeInTheDocument();
  });

  it('test_architecture_diagram_node_labels_present', () => {
    render(<ArchitectureDiagram />);

    expect(screen.getByText('Kafka')).toBeInTheDocument();
    expect(screen.getByText('Bronze Ingestion')).toBeInTheDocument();
    expect(screen.getByText('React Frontend')).toBeInTheDocument();
  });

  it('test_architecture_diagram_reduced_motion_no_animatemotion', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    const { container } = render(<ArchitectureDiagram />);

    expect(container.querySelectorAll('animateMotion').length).toBe(0);
  });

  it('renders all 10 expected node labels', () => {
    render(<ArchitectureDiagram />);

    const expectedLabels = [
      'Simulation Engine',
      'Kafka',
      'Stream Processor',
      'Redis Pub/Sub',
      'WebSocket Server',
      'React Frontend',
      'Bronze Ingestion',
      'Silver',
      'Gold',
      'Trino + Grafana',
    ];

    for (const label of expectedLabels) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('renders animateMotion elements when motion is allowed', () => {
    const { container } = render(<ArchitectureDiagram />);

    const animateMotions = container.querySelectorAll('animateMotion');
    expect(animateMotions.length).toBeGreaterThan(0);
  });

  it('svg has correct viewBox attribute', () => {
    const { container } = render(<ArchitectureDiagram />);

    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute('viewBox')).toBe('0 0 800 560');
  });
});
