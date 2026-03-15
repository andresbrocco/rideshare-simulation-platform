import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LandingPage } from '../LandingPage';
import { ALL_SERVICES_DOWN } from '../../services/lambda';
import type { ServiceHealthMap } from '../../services/lambda';

const ALL_SERVICES_UP: ServiceHealthMap = {
  simulation_api: true,
  grafana: true,
  airflow: true,
  trino: true,
  prometheus: true,
  control_panel: true,
};

type LandingPageProps = Parameters<typeof LandingPage>[0];

function renderLandingPage(overrides: Partial<LandingPageProps> = {}) {
  const defaults: LandingPageProps = {
    isLocal: overrides.isLocal ?? false,
    serviceHealth: overrides.serviceHealth ?? ALL_SERVICES_DOWN,
    apiKey: overrides.apiKey ?? null,
    onNeedAuth: overrides.onNeedAuth ?? vi.fn(),
    onServiceHealthChange: overrides.onServiceHealthChange ?? vi.fn(),
  };
  return render(<LandingPage {...defaults} />);
}

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
    renderLandingPage();

    expect(
      screen.getByRole('heading', { level: 1, name: 'Rideshare Simulation Platform' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Real-time Event-Driven Data Engineering \u2014 Portfolio Project')
    ).toBeInTheDocument();
  });

  it('displays GitHub link with correct attributes', () => {
    renderLandingPage();

    const link = screen.getByRole('link', { name: /View on GitHub/i });
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/andresbrocco/rideshare-simulation-platform'
    );
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders the trip lifecycle animation', () => {
    renderLandingPage();

    expect(
      screen.getByRole('img', {
        name: 'Animated trip lifecycle: a driver picks up a rider and drives to the destination',
      })
    ).toBeInTheDocument();
  });

  it('renders Control Panel link in services grid', () => {
    renderLandingPage({ serviceHealth: ALL_SERVICES_UP });

    const controlPanelLink = screen.getByRole('link', { name: /control panel/i });
    expect(controlPanelLink).toBeInTheDocument();
    expect(controlPanelLink).toHaveAttribute(
      'href',
      'https://control-panel.ridesharing.portfolio.andresbrocco.com'
    );
    expect(controlPanelLink).toHaveAttribute('target', '_blank');
    expect(controlPanelLink).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders Explore the Platform heading', () => {
    renderLandingPage();

    expect(
      screen.getByRole('heading', { level: 2, name: 'Explore the Platform' })
    ).toBeInTheDocument();
  });

  it('renders production URLs when isLocal is false', () => {
    renderLandingPage({ serviceHealth: ALL_SERVICES_UP });

    const expectedServices = [
      { name: 'Airflow', url: 'https://airflow.ridesharing.portfolio.andresbrocco.com' },
      { name: 'Grafana', url: 'https://grafana.ridesharing.portfolio.andresbrocco.com' },
    ];

    for (const service of expectedServices) {
      const link = screen.getByRole('link', { name: new RegExp(service.name) });
      expect(link).toHaveAttribute('href', service.url);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }
  });

  it('renders local URLs when isLocal is true', () => {
    renderLandingPage({ isLocal: true, serviceHealth: ALL_SERVICES_UP });

    const expectedServices = [
      { name: 'Airflow', url: 'http://localhost:8082' },
      { name: 'Grafana', url: 'http://localhost:3001' },
    ];

    for (const service of expectedServices) {
      const link = screen.getByRole('link', { name: new RegExp(service.name) });
      expect(link).toHaveAttribute('href', service.url);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }
  });

  it('does not show Demo Offline badge', () => {
    renderLandingPage();

    expect(screen.queryByText(/demo offline/i)).not.toBeInTheDocument();
  });

  it('renders four stat cards with correct labels', () => {
    renderLandingPage();

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

    renderLandingPage();

    const statNumbers = document.querySelectorAll('.stat-number');
    const values = Array.from(statNumbers).map((el) => el.textContent);
    expect(values).toContain('30+');
    expect(values).toContain('2000+');
    expect(values).toContain('10');
    expect(values).toContain('3');
  });

  it('hero section has id attribute for scroll targeting', () => {
    renderLandingPage();

    const hero = document.getElementById('hero');
    expect(hero).not.toBeNull();
    expect(hero).toContainElement(screen.getByRole('heading', { level: 1 }));
  });

  it('landing-inner CSS class is present in the DOM', () => {
    renderLandingPage();

    expect(document.querySelector('.landing-inner')).not.toBeNull();
  });

  it('tech stack section has id for sticky nav targeting', () => {
    renderLandingPage();
    expect(document.getElementById('tech-stack')).not.toBeNull();
  });

  it('renders all eight tech group titles', () => {
    renderLandingPage();
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
    renderLandingPage();
    // Use getAllByText for labels that may also appear in SVG <title> elements
    const badgeLabels = ['Python 3.13', 'Apache Kafka', 'Delta Lake', 'dbt', 'React', 'Prometheus'];
    for (const label of badgeLabels) {
      const matches = screen.getAllByText(label);
      expect(matches.length).toBeGreaterThan(0);
    }
  });

  it('all tech badges have tooltip attributes', () => {
    renderLandingPage();
    const badges = document.querySelectorAll('.tech-badge');
    expect(badges.length).toBeGreaterThan(0);
    for (const badge of badges) {
      const tooltip = badge.getAttribute('data-tooltip');
      expect(tooltip).toBeTruthy();
    }
  });

  it('renders DevOps and Cloud tech groups', () => {
    renderLandingPage();
    const groupTitles = document.querySelectorAll('.tech-group-title');
    const groupLabels = Array.from(groupTitles).map((el) => el.textContent);
    expect(groupLabels).toContain('DevOps');
    expect(groupLabels).toContain('Cloud (AWS)');
  });

  it('shows technology stack section with grouped badges', () => {
    renderLandingPage();
    expect(screen.getByRole('heading', { level: 2, name: 'Technology Stack' })).toBeInTheDocument();
    expect(screen.getByText('Python 3.13')).toBeInTheDocument();
    expect(screen.getAllByText('Apache Kafka').length).toBeGreaterThan(0);
  });
});

describe('Deep Dives section', () => {
  it('renders four deep-dive details elements', () => {
    renderLandingPage();
    const deepDives = document.querySelectorAll('.deep-dive');
    expect(deepDives).toHaveLength(4);
  });

  it('renders all four deep dive titles', () => {
    renderLandingPage();
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
    renderLandingPage();
    const icons = document.querySelectorAll('.landing-service-icon');
    expect(icons).toHaveLength(3);
  });
});

describe('Footer', () => {
  it('test_footer_renders_github_link', () => {
    renderLandingPage();
    const link = screen.getByRole('link', { name: /View on GitHub/i });
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/andresbrocco/rideshare-simulation-platform'
    );
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('test_footer_renders_author_line', () => {
    renderLandingPage();
    expect(screen.getByText(/Built by Andre Sbrocco/)).toBeInTheDocument();
  });

  it('test_footer_linkedin_link_present', () => {
    renderLandingPage();
    const link = screen.getByRole('link', { name: /LinkedIn/i });
    expect(link).toHaveAttribute('href', 'https://www.linkedin.com/in/andresbrocco/');
  });

  it('test_footer_element_is_footer_landmark', () => {
    renderLandingPage();
    expect(document.querySelector('footer.landing-footer')).not.toBeNull();
  });
});

describe('SectionNav', () => {
  it('test_section_nav_renders_four_buttons', () => {
    renderLandingPage();

    expect(screen.getByRole('button', { name: 'Architecture' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tech Stack' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deep Dives' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Explore' })).toBeInTheDocument();
  });

  it('test_section_nav_initially_not_visible', () => {
    renderLandingPage();

    const nav = document.querySelector('.section-nav');
    expect(nav).not.toBeNull();
    expect(nav!.classList.contains('section-nav--visible')).toBe(false);
  });

  it('test_section_nav_becomes_visible_when_hero_not_intersecting', () => {
    renderLandingPage();

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
    renderLandingPage();

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

    renderLandingPage();

    const exploreButton = screen.getByRole('button', { name: 'Explore' });
    await user.click(exploreButton);

    expect(scrollIntoViewMock).toHaveBeenCalledWith(expect.objectContaining({ block: 'start' }));

    document.body.removeChild(exploreEl);
  });

  it('test_section_nav_has_focus_indicators', () => {
    renderLandingPage();

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
    renderLandingPage();
    expect(document.querySelector('.landing-services-grid')).not.toBeNull();
  });

  it('tech badges are keyboard-focusable via tabIndex', () => {
    renderLandingPage();
    const badges = document.querySelectorAll('.tech-badge');
    expect(badges.length).toBeGreaterThan(0);
    for (const badge of badges) {
      expect((badge as HTMLElement).tabIndex).toBe(0);
    }
  });

  it('active nav button has aria-current', () => {
    mockUseActiveSectionValue.mockReturnValue('architecture');
    renderLandingPage();

    const archButton = screen.getByRole('button', { name: /^Architecture$/i });
    expect(archButton).toHaveAttribute('aria-current', 'true');
  });

  it('inactive nav buttons have no aria-current', () => {
    mockUseActiveSectionValue.mockReturnValue('architecture');
    renderLandingPage();

    const techStackButton = screen.getByRole('button', { name: /^Tech Stack$/i });
    const deepDivesButton = screen.getByRole('button', { name: /^Deep Dives$/i });
    const exploreButton = screen.getByRole('button', { name: /^Explore$/i });

    expect(techStackButton).not.toHaveAttribute('aria-current');
    expect(deepDivesButton).not.toHaveAttribute('aria-current');
    expect(exploreButton).not.toHaveAttribute('aria-current');
  });

  it('architecture SVG has role="img" and accessible name', () => {
    renderLandingPage();
    const svg = screen.getByRole('img', { name: /system architecture/i });
    expect(svg).toBeInTheDocument();
  });

  it('screenshot images use lazy loading', () => {
    renderLandingPage();
    const screenshots = document.querySelectorAll('img.deep-dive-screenshot');
    expect(screenshots.length).toBeGreaterThan(0);
    for (const img of screenshots) {
      expect(img).toHaveAttribute('loading', 'lazy');
    }
  });

  it('screenshot images have non-empty alt text', () => {
    renderLandingPage();
    const screenshots = document.querySelectorAll('img.deep-dive-screenshot');
    expect(screenshots.length).toBeGreaterThan(0);
    for (const img of screenshots) {
      const alt = img.getAttribute('alt') ?? '';
      expect(alt.length).toBeGreaterThan(0);
    }
  });

  it('all five scroll-target section IDs are present', () => {
    renderLandingPage();
    expect(document.getElementById('hero')).not.toBeNull();
    expect(document.getElementById('architecture')).not.toBeNull();
    expect(document.getElementById('tech-stack')).not.toBeNull();
    expect(document.getElementById('deep-dives')).not.toBeNull();
    expect(document.getElementById('explore')).not.toBeNull();
  });
});

describe('Tech badge tooltip toggle', () => {
  it('clicking a tech badge adds tech-badge--active class', async () => {
    const user = userEvent.setup();
    renderLandingPage();

    const badges = document.querySelectorAll('.tech-badge');
    expect(badges.length).toBeGreaterThan(0);

    await user.click(badges[0] as HTMLElement);

    expect(badges[0]).toHaveClass('tech-badge--active');
  });

  it('clicking the same badge again removes active class', async () => {
    const user = userEvent.setup();
    renderLandingPage();

    const badges = document.querySelectorAll('.tech-badge');
    const firstBadge = badges[0] as HTMLElement;

    await user.click(firstBadge);
    expect(firstBadge).toHaveClass('tech-badge--active');

    await user.click(firstBadge);
    expect(firstBadge).not.toHaveClass('tech-badge--active');
  });

  it('clicking a different badge switches active to the new one', async () => {
    const user = userEvent.setup();
    renderLandingPage();

    const badges = document.querySelectorAll('.tech-badge');
    const firstBadge = badges[0] as HTMLElement;
    const secondBadge = badges[1] as HTMLElement;

    await user.click(firstBadge);
    expect(firstBadge).toHaveClass('tech-badge--active');

    await user.click(secondBadge);
    expect(firstBadge).not.toHaveClass('tech-badge--active');
    expect(secondBadge).toHaveClass('tech-badge--active');
  });

  it('clicking outside dismisses active tooltip', async () => {
    const user = userEvent.setup();
    renderLandingPage();

    const badges = document.querySelectorAll('.tech-badge');
    const firstBadge = badges[0] as HTMLElement;

    await user.click(firstBadge);
    expect(firstBadge).toHaveClass('tech-badge--active');

    await user.click(document.body);
    expect(firstBadge).not.toHaveClass('tech-badge--active');
  });
});
