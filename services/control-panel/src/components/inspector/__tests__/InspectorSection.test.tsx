import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { InspectorSection } from '../InspectorSection';

describe('InspectorSection', () => {
  it('renders section title', () => {
    render(
      <InspectorSection title="Status">
        <p>Content</p>
      </InspectorSection>
    );

    expect(screen.getByRole('heading', { name: 'Status' })).toBeInTheDocument();
  });

  it('renders children content', () => {
    render(
      <InspectorSection title="Details">
        <span data-testid="child-content">Test content</span>
      </InspectorSection>
    );

    expect(screen.getByTestId('child-content')).toBeInTheDocument();
    expect(screen.getByText('Test content')).toBeInTheDocument();
  });

  it('renders multiple children', () => {
    render(
      <InspectorSection title="Multiple">
        <p>First child</p>
        <p>Second child</p>
        <p>Third child</p>
      </InspectorSection>
    );

    expect(screen.getByText('First child')).toBeInTheDocument();
    expect(screen.getByText('Second child')).toBeInTheDocument();
    expect(screen.getByText('Third child')).toBeInTheDocument();
  });

  it('applies section styling', () => {
    const { container } = render(
      <InspectorSection title="Styled">
        <p>Content</p>
      </InspectorSection>
    );

    const section = container.firstChild;
    expect(section).toHaveClass('section');
  });
});
