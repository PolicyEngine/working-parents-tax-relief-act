import { act, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import Home from '../app/(shell)/page';
import { pauseHouseholdCalculations } from '../hooks/useHouseholdImpact';

// The other tabs are not under test here.
vi.mock('@/components/PolicyOverview', () => ({ default: () => null }));
vi.mock('@/components/AggregateImpact', () => ({ default: () => null }));
vi.mock('@/components/CongressionalDistrictImpact', () => ({
  default: () => null,
}));

function renderHouseholdImpactTab(): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Home />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole('tab', { name: 'Household impact' }));
}

afterEach(() => {
  // Real time first, so that ending the pause ends it in real time.
  vi.useRealTimers();
  pauseHouseholdCalculations(0);
});

describe('Household impact tab', () => {
  it('explains a pause under the button and ends it after the minute', () => {
    vi.useFakeTimers();
    // A refusal paused calculations, perhaps for a household no longer on
    // screen, or before the tab was opened again.
    pauseHouseholdCalculations();
    renderHouseholdImpactTab();

    expect(
      screen.getByRole('button', { name: 'Calculate again in 60 s' }),
    ).toBeDisabled();
    expect(
      screen.getByText(/This page can calculate again in 60 s\./),
    ).toHaveTextContent(
      'Everyone on your network, such as a workshop or an office, shares a ' +
        'limit on calculations a minute. This page can calculate again in 60 s.',
    );

    act(() => {
      vi.advanceTimersByTime(60_000);
    });

    expect(screen.getByRole('button', { name: 'Calculate impact' })).toBeEnabled();
    expect(screen.queryByText(/This page can calculate again/)).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('announces the explanation once, keeping the countdown out of the live region', () => {
    vi.useFakeTimers();
    pauseHouseholdCalculations();
    renderHouseholdImpactTab();
    const explanation =
      'Everyone on your network, such as a workshop or an office, shares a ' +
      'limit on calculations a minute.';

    expect(screen.getByRole('status').textContent).toBe(explanation);

    act(() => {
      vi.advanceTimersByTime(1_000);
    });

    // The countdown moved on, but what screen readers announce did not
    // change.
    expect(
      screen.getByText(/This page can calculate again in 59 s\./),
    ).toBeInTheDocument();
    expect(screen.getByRole('status').textContent).toBe(explanation);
  });
});
