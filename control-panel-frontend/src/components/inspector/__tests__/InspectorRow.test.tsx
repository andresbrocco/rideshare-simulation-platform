import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { InspectorRow } from '../InspectorRow';

describe('InspectorRow', () => {
  it('renders label', () => {
    render(<InspectorRow label="Status" value="Online" />);

    expect(screen.getByText('Status:')).toBeInTheDocument();
  });

  it('renders value', () => {
    render(<InspectorRow label="Rating" value="4.8" />);

    expect(screen.getByText('4.8')).toBeInTheDocument();
  });

  it('renders label and value together', () => {
    render(<InspectorRow label="Zone" value="Vila Mariana" />);

    expect(screen.getByText('Zone:')).toBeInTheDocument();
    expect(screen.getByText('Vila Mariana')).toBeInTheDocument();
  });

  it('renders numeric values correctly', () => {
    render(<InspectorRow label="Count" value={42} />);

    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders formatted currency values', () => {
    render(<InspectorRow label="Fare" value="R$ 45.50" />);

    expect(screen.getByText('R$ 45.50')).toBeInTheDocument();
  });

  it('applies row styling', () => {
    const { container } = render(<InspectorRow label="Test" value="Value" />);

    const row = container.firstChild;
    expect(row).toHaveClass('row');
  });

  it('applies label styling', () => {
    render(<InspectorRow label="Label" value="Value" />);

    const label = screen.getByText('Label:');
    expect(label).toHaveClass('label');
  });

  it('applies value styling', () => {
    render(<InspectorRow label="Label" value="TestValue" />);

    const value = screen.getByText('TestValue');
    expect(value).toHaveClass('value');
  });

  it('handles empty value', () => {
    render(<InspectorRow label="Empty" value="" />);

    expect(screen.getByText('Empty:')).toBeInTheDocument();
  });
});
