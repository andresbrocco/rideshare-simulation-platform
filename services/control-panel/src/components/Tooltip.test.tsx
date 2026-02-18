import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Tooltip from './Tooltip';

describe('Tooltip', () => {
  it('test_renders_trigger_content', () => {
    render(
      <Tooltip text="Helper text">
        <button>Click me</button>
      </Tooltip>
    );

    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('test_shows_tooltip_on_hover', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip text="Helper text">
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByRole('button', { name: /hover me/i });
    await user.hover(trigger);

    expect(screen.getByText('Helper text')).toBeInTheDocument();
  });

  it('test_hides_tooltip_on_mouse_leave', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip text="Helper text">
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByRole('button', { name: /hover me/i });
    await user.hover(trigger);
    expect(screen.getByText('Helper text')).toBeInTheDocument();

    await user.unhover(trigger);
    expect(screen.queryByText('Helper text')).not.toBeInTheDocument();
  });

  it('test_applies_custom_position', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip text="Helper text" position="bottom">
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByRole('button', { name: /hover me/i });
    await user.hover(trigger);

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip.className).toContain('bottom');
  });

  it('test_accessibility_attributes', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip text="Helper text">
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByRole('button', { name: /hover me/i });
    await user.hover(trigger);

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toBeInTheDocument();
    expect(trigger).toHaveAttribute('aria-describedby');
  });

  it('test_fade_animation_class', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip text="Helper text">
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByRole('button', { name: /hover me/i });
    await user.hover(trigger);

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip.className).toContain('visible');
  });
});
