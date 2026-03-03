import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LandingPage } from '../LandingPage';

// jsdom doesn't implement SVG geometry methods.
// jsdom renders <path> as SVGElement (not SVGPathElement), so patch SVGElement.prototype.
// @ts-expect-error -- SVGElement doesn't declare getTotalLength, but jsdom <path> elements are SVGElement
SVGElement.prototype.getTotalLength = vi.fn().mockReturnValue(900);
// @ts-expect-error -- same as above
SVGElement.prototype.getPointAtLength = vi.fn().mockReturnValue({ x: 100, y: 40 });

const mockOnLoginClick = vi.fn();

type IntersectionObserverCallback = (entries: IntersectionObserverEntry[]) => void;
let observerCallbacks: IntersectionObserverCallback[] = [];

beforeEach(() => {
  vi.clearAllMocks();
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

    expect(screen.getByText('Services')).toBeInTheDocument();
    expect(screen.getByText('Kafka Topics')).toBeInTheDocument();
    expect(screen.getByText('Tests')).toBeInTheDocument();
    expect(
      screen.getByText(
        (content) => content.includes('Grafana Dashboard') && content.includes('Categories')
      )
    ).toBeInTheDocument();

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
    expect(values).toContain('8');
    expect(values).toContain('120+');
    expect(values).toContain('4');
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

  it('renders all six tech group titles', () => {
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

  it('renders infrastructure footnote', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);
    expect(screen.getByText(/Also:/i)).toBeInTheDocument();
    // Docker appears in both the footnote and deep-dive content — verify footnote presence
    const footnote = document.querySelector('.tech-infra-footnote');
    expect(footnote).not.toBeNull();
    expect(footnote?.textContent).toMatch(/Docker/i);
  });

  it('shows technology stack section with grouped badges', () => {
    render(<LandingPage onLoginClick={mockOnLoginClick} isLocal={false} />);
    expect(screen.getByRole('heading', { level: 2, name: 'Technology Stack' })).toBeInTheDocument();
    expect(screen.getByText('Python 3.13')).toBeInTheDocument();
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
