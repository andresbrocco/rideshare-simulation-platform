import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DraggablePopupContainer } from '../DraggablePopupContainer';

describe('DraggablePopupContainer', () => {
  const defaultProps = {
    x: 100,
    y: 200,
    title: 'Test Popup',
    onClose: vi.fn(),
  };

  it('renders children content', () => {
    render(
      <DraggablePopupContainer {...defaultProps}>
        <p data-testid="child">Child content</p>
      </DraggablePopupContainer>
    );

    expect(screen.getByTestId('child')).toBeInTheDocument();
    expect(screen.getByText('Child content')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(
      <DraggablePopupContainer {...defaultProps} onClose={onClose}>
        <p>Content</p>
      </DraggablePopupContainer>
    );

    const closeButton = screen.getByRole('button', { name: /close/i });
    await user.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('toggles minimize state when minimize button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <DraggablePopupContainer {...defaultProps}>
        <p data-testid="content">Content to hide</p>
      </DraggablePopupContainer>
    );

    // Content should be visible initially
    expect(screen.getByTestId('content')).toBeVisible();

    // Click minimize button
    const minimizeButton = screen.getByRole('button', { name: /minimize/i });
    await user.click(minimizeButton);

    // Content should be hidden
    expect(screen.queryByTestId('content')).not.toBeVisible();

    // Click restore button
    const restoreButton = screen.getByRole('button', { name: /restore/i });
    await user.click(restoreButton);

    // Content should be visible again
    expect(screen.getByTestId('content')).toBeVisible();
  });

  it('displays minimized title when minimized', async () => {
    const user = userEvent.setup();

    render(
      <DraggablePopupContainer {...defaultProps} title="Driver: Carlos Silva">
        <p>Content</p>
      </DraggablePopupContainer>
    );

    const minimizeButton = screen.getByRole('button', { name: /minimize/i });
    await user.click(minimizeButton);

    expect(screen.getByText('Driver: Carlos Silva')).toBeInTheDocument();
  });

  it('has a drag handle element', () => {
    const { container } = render(
      <DraggablePopupContainer {...defaultProps}>
        <p>Content</p>
      </DraggablePopupContainer>
    );

    const dragHandle = container.querySelector('.dragHandle');
    expect(dragHandle).toBeInTheDocument();
  });

  it('positions at specified x and y coordinates', () => {
    const { container } = render(
      <DraggablePopupContainer {...defaultProps} x={150} y={250}>
        <p>Content</p>
      </DraggablePopupContainer>
    );

    const popup = container.querySelector('[data-testid="inspector-popup"]');
    expect(popup).toHaveStyle({ left: '150px', top: '250px' });
  });

  it('applies dragging class when being dragged', () => {
    const { container } = render(
      <DraggablePopupContainer {...defaultProps}>
        <p>Content</p>
      </DraggablePopupContainer>
    );

    const popup = container.querySelector('[data-testid="inspector-popup"]');
    // Initially not dragging
    expect(popup).not.toHaveClass('dragging');
  });

  it('applies minimized class when minimized', async () => {
    const user = userEvent.setup();

    const { container } = render(
      <DraggablePopupContainer {...defaultProps}>
        <p>Content</p>
      </DraggablePopupContainer>
    );

    const popup = container.querySelector('[data-testid="inspector-popup"]');
    expect(popup).not.toHaveClass('minimized');

    const minimizeButton = screen.getByRole('button', { name: /minimize/i });
    await user.click(minimizeButton);

    expect(popup).toHaveClass('minimized');
  });
});
