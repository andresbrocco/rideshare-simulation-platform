import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LandingPage } from '../LandingPage';

// jsdom doesn't implement SVG geometry methods.
// jsdom renders <path> as SVGElement (not SVGPathElement), so patch SVGElement.prototype.
// @ts-expect-error -- SVGElement doesn't declare getTotalLength, but jsdom <path> elements are SVGElement
SVGElement.prototype.getTotalLength = vi.fn().mockReturnValue(900);
// @ts-expect-error -- same as above
SVGElement.prototype.getPointAtLength = vi.fn().mockReturnValue({ x: 100, y: 40 });

// Mock useActiveSection so tests can control which section appears active
const mockUseActiveSectionValue = vi.fn<[], string | null>(() => null);
vi.mock('../../hooks/useActiveSection', () => ({
  useActiveSection: () => mockUseActiveSectionValue(),
}));

const mockOnLoginClick = vi.fn();

type IntersectionObserverCallback = (entries: IntersectionObserverEntry[]) => void;
let observerCallbacks: IntersectionObserverCallback[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  mockUseActiveSectionValue.mockReturnValue(null);
  observerCallbacks = [];

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

  vi.stubGlobal(
    'IntersectionObserver',
    vi.fn().mockImplementation((callback: IntersectionObserverCallback) => {
      observerCallbacks.push(callback);
      return {
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: vi.fn(),
      };
    })
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('LandingPage', () => {
  it('renders project title and subtitle', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    expect(
      screen.getByRole('heading', { level: 1, name: 'Rideshare Simulation Platform' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Real-time Event-Driven Data Engineering \u2014 Portfolio Project')
    ).toBeInTheDocument();
  });

  it('displays GitHub link with correct attributes', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const link = screen.getByRole('link', { name: /View on GitHub/i });
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/andresbrocco/rideshare-simulation-platform'
    );
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders the trip lifecycle animation', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    expect(
      screen.getByRole('img', {
        name: 'Animated trip lifecycle: a driver picks up a rider and drives to the destination',
      })
    ).toBeInTheDocument();
  });

  it('renders Control Panel button in services grid', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const controlPanelButton = screen.getByRole('button', { name: /control panel/i });
    expect(controlPanelButton).toBeInTheDocument();
  });

  it('calls onLoginClick when Control Panel button clicked', async () => {
    const user = userEvent.setup();
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const controlPanelButton = screen.getByRole('button', { name: /control panel/i });
    await user.click(controlPanelButton);

    expect(mockOnLoginClick).toHaveBeenCalledOnce();
  });

  it('renders Explore the Platform heading', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    expect(
      screen.getByRole('heading', { level: 2, name: 'Explore the Platform' })
    ).toBeInTheDocument();
  });

  it('renders production URLs when isLocal is false', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

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

  it('renders local URLs when isLocal is true', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={true} />);

    const expectedServices = [
      { name: 'Grafana', url: 'http://localhost:3001' },
      { name: 'Airflow', url: 'http://localhost:8082' },
      { name: 'Trino', url: 'http://localhost:8084' },
      { name: 'Prometheus', url: 'http://localhost:9090' },
      { name: 'Simulation API', url: 'http://localhost:8000/docs' },
    ];

    for (const service of expectedServices) {
      const link = screen.getByRole('link', { name: new RegExp(service.name) });
      expect(link).toHaveAttribute('href', service.url);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }
  });

  it('does not show Demo Offline badge', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    expect(screen.queryByText(/demo offline/i)).not.toBeInTheDocument();
  });

  it('renders four stat cards with correct labels', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    expect(screen.getByText('Technologies')).toBeInTheDocument();
    expect(screen.getByText('Tests')).toBeInTheDocument();
    expect(screen.getByText('Grafana Dashboards')).toBeInTheDocument();
    expect(screen.getByText('Terraform Layers')).toBeInTheDocument();

    expect(document.querySelectorAll('.stat-card')).toHaveLength(4);
  });

  it('shows final target values immediately when prefers-reduced-motion is set', () => {
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

    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const statNumbers = document.querySelectorAll('.stat-number');
    const values = Array.from(statNumbers).map((el) => el.textContent);
    expect(values).toContain('30+');
    expect(values).toContain('2000+');
    expect(values).toContain('10');
    expect(values).toContain('3');
  });

  it('hero section has id attribute for scroll targeting', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const hero = document.getElementById('hero');
    expect(hero).not.toBeNull();
    expect(hero).toContainElement(screen.getByRole('heading', { level: 1 }));
  });

  it('landing-inner CSS class is present in the DOM', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    expect(document.querySelector('.landing-inner')).not.toBeNull();
  });

  it('tech stack section has id for sticky nav targeting', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);
    expect(document.getElementById('tech-stack')).not.toBeNull();
  });

  it('renders all eight tech group titles', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);
    // Use getAllByText because some labels also appear in deep-dive content
    expect(screen.getAllByText('Simulation').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Streaming').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Storage').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Transformation').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Frontend').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Observability').length).toBeGreaterThan(0);
    // Verify at least one match is actually a tech-group-title
    const groupTitles = document.querySelectorAll('.tech-group-title');
    const groupLabels = Array.from(groupTitles).map((el) => el.textContent);
    expect(groupLabels).toContain('Simulation');
    expect(groupLabels).toContain('Observability');
  });

  it('renders representative badges from each group', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);
    // Use getAllByText for labels that may also appear in SVG <title> elements
    const badgeLabels = ['Python 3.13', 'Apache Kafka', 'Delta Lake', 'dbt', 'React', 'Prometheus'];
    for (const label of badgeLabels) {
      const matches = screen.getAllByText(label);
      expect(matches.length).toBeGreaterThan(0);
    }
  });

  it('all tech badges have tooltip attributes', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);
    const badges = document.querySelectorAll('.tech-badge');
    expect(badges.length).toBeGreaterThan(0);
    for (const badge of badges) {
      const tooltip = badge.getAttribute('data-tooltip');
      expect(tooltip).toBeTruthy();
    }
  });

  it('renders DevOps and Cloud tech groups', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);
    const groupTitles = document.querySelectorAll('.tech-group-title');
    const groupLabels = Array.from(groupTitles).map((el) => el.textContent);
    expect(groupLabels).toContain('DevOps');
    expect(groupLabels).toContain('Cloud (AWS)');
  });

  it('shows technology stack section with grouped badges', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);
    expect(screen.getByRole('heading', { level: 2, name: 'Technology Stack' })).toBeInTheDocument();
    expect(screen.getByText('Python 3.13')).toBeInTheDocument();
    expect(screen.getAllByText('Apache Kafka').length).toBeGreaterThan(0);
  });
});

describe('Deep Dives section', () => {
  it('renders four deep-dive details elements', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    const deepDives = document.querySelectorAll('.deep-dive');
    expect(deepDives).toHaveLength(4);
  });

  it('renders all four deep dive titles', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    const deepDivesSection = document.getElementById('deep-dives');
    expect(deepDivesSection).not.toBeNull();

    const scoped = within(deepDivesSection!);
    expect(scoped.getByText('Simulation Engine')).toBeInTheDocument();
    expect(scoped.getByText('Medallion Data Pipeline')).toBeInTheDocument();
    expect(scoped.getByText('Infrastructure & Quality')).toBeInTheDocument();
    expect(scoped.getByText('Observability')).toBeInTheDocument();
  });
});

describe('Service cards with icons', () => {
  it('renders six service card icons', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    const icons = document.querySelectorAll('.landing-service-icon');
    expect(icons).toHaveLength(6);
  });
});

describe('Footer', () => {
  it('test_footer_renders_deployment_note', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    expect(screen.getByText(/deployed on-demand for demonstrations/i)).toBeInTheDocument();
  });

  it('test_footer_renders_github_link', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    const link = screen.getByRole('link', { name: /View on GitHub/i });
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/andresbrocco/rideshare-simulation-platform'
    );
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('test_footer_renders_author_line', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    expect(screen.getByText('Built by Andres Brocco')).toBeInTheDocument();
  });

  it('test_footer_linkedin_hidden_when_url_empty', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    expect(screen.queryByRole('link', { name: /LinkedIn/i })).toBeNull();
  });

  it('test_footer_element_is_footer_landmark', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    expect(document.querySelector('footer.landing-footer')).not.toBeNull();
  });
});

describe('SectionNav', () => {
  it('test_section_nav_renders_four_buttons', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    expect(screen.getByRole('button', { name: 'Architecture' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tech Stack' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deep Dives' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Explore' })).toBeInTheDocument();
  });

  it('test_section_nav_initially_not_visible', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const nav = document.querySelector('.section-nav');
    expect(nav).not.toBeNull();
    expect(nav!.classList.contains('section-nav--visible')).toBe(false);
  });

  it('test_section_nav_becomes_visible_when_hero_not_intersecting', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const heroObserverCallback = observerCallbacks[observerCallbacks.length - 1];
    expect(heroObserverCallback).toBeDefined();

    act(() => {
      heroObserverCallback([
        {
          isIntersecting: false,
          target: document.createElement('div'),
        } as IntersectionObserverEntry,
      ]);
    });

    const nav = document.querySelector('.section-nav');
    expect(nav).not.toBeNull();
    expect(nav!.classList.contains('section-nav--visible')).toBe(true);
  });

  it('test_section_nav_hides_when_hero_intersecting', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const heroObserverCallback = observerCallbacks[observerCallbacks.length - 1];

    act(() => {
      heroObserverCallback([
        {
          isIntersecting: false,
          target: document.createElement('div'),
        } as IntersectionObserverEntry,
      ]);
    });

    act(() => {
      heroObserverCallback([
        {
          isIntersecting: true,
          target: document.createElement('div'),
        } as IntersectionObserverEntry,
      ]);
    });

    const nav = document.querySelector('.section-nav');
    expect(nav).not.toBeNull();
    expect(nav!.classList.contains('section-nav--visible')).toBe(false);
  });

  it('test_section_nav_button_click_calls_scrollIntoView', async () => {
    const user = userEvent.setup();

    const exploreEl = document.createElement('section');
    exploreEl.id = 'explore';
    const scrollIntoViewMock = vi.fn();
    exploreEl.scrollIntoView = scrollIntoViewMock;
    document.body.appendChild(exploreEl);

    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const exploreButton = screen.getByRole('button', { name: 'Explore' });
    await user.click(exploreButton);

    expect(scrollIntoViewMock).toHaveBeenCalledWith(expect.objectContaining({ block: 'start' }));

    document.body.removeChild(exploreEl);
  });

  it('test_section_nav_has_focus_indicators', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);

    const navButtons = screen
      .getAllByRole('button')
      .filter((btn) => btn.classList.contains('section-nav-btn'));

    expect(navButtons.length).toBeGreaterThan(0);
    for (const btn of navButtons) {
      expect(btn).toBeVisible();
      expect(btn.tabIndex).not.toBe(-1);
    }
  });
});

describe('Responsive and Accessibility', () => {
  it('service cards grid container exists for mobile CSS', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    expect(document.querySelector('.landing-services-grid')).not.toBeNull();
  });

  it('tech badges are keyboard-focusable via tabIndex', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    const badges = document.querySelectorAll('.tech-badge');
    expect(badges.length).toBeGreaterThan(0);
    for (const badge of badges) {
      expect((badge as HTMLElement).tabIndex).toBe(0);
    }
  });

  it('active nav button has aria-current', () => {
    mockUseActiveSectionValue.mockReturnValue('architecture');
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);

    const archButton = screen.getByRole('button', { name: /^Architecture$/i });
    expect(archButton).toHaveAttribute('aria-current', 'true');
  });

  it('inactive nav buttons have no aria-current', () => {
    mockUseActiveSectionValue.mockReturnValue('architecture');
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);

    const techStackButton = screen.getByRole('button', { name: /^Tech Stack$/i });
    const deepDivesButton = screen.getByRole('button', { name: /^Deep Dives$/i });
    const exploreButton = screen.getByRole('button', { name: /^Explore$/i });

    expect(techStackButton).not.toHaveAttribute('aria-current');
    expect(deepDivesButton).not.toHaveAttribute('aria-current');
    expect(exploreButton).not.toHaveAttribute('aria-current');
  });

  it('architecture SVG has role="img" and accessible name', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    const svg = screen.getByRole('img', { name: /system architecture/i });
    expect(svg).toBeInTheDocument();
  });

  it('screenshot images use lazy loading', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    const screenshots = document.querySelectorAll('img.deep-dive-screenshot');
    expect(screenshots.length).toBeGreaterThan(0);
    for (const img of screenshots) {
      expect(img).toHaveAttribute('loading', 'lazy');
    }
  });

  it('screenshot images have non-empty alt text', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    const screenshots = document.querySelectorAll('img.deep-dive-screenshot');
    expect(screenshots.length).toBeGreaterThan(0);
    for (const img of screenshots) {
      const alt = img.getAttribute('alt') ?? '';
      expect(alt.length).toBeGreaterThan(0);
    }
  });

  it('all five scroll-target section IDs are present', () => {
    render(<LandingPage onLoginClick={vi.fn()} isLocal={false} />);
    expect(document.getElementById('hero')).not.toBeNull();
    expect(document.getElementById('architecture')).not.toBeNull();
    expect(document.getElementById('tech-stack')).not.toBeNull();
    expect(document.getElementById('deep-dives')).not.toBeNull();
    expect(document.getElementById('explore')).not.toBeNull();
  });
});
