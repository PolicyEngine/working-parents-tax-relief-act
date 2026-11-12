import { act, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import Home from '../app/(shell)/page';
import { pauseHouseholdCalculations } from '../hooks/useHouseholdImpact';
import { api, HouseholdCalculationError } from '../lib/api';
import type { HouseholdImpactResponse } from '../lib/types';

// The other tabs are not under test here.
vi.mock('@/components/PolicyOverview', () => ({ default: () => null }));
vi.mock('@/components/AggregateImpact', () => ({ default: () => null }));
vi.mock('@/components/CongressionalDistrictImpact', () => ({
  default: () => null,
}));

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks, so
// the chart draws nothing here; these tests read the page's text.
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return { ...actual, ResponsiveContainer: () => null };
});

const REFUSAL_MESSAGE =
  'Everyone on your network, such as a workshop or an office, shares a ' +
  'limit on calculations a minute, and it has been reached.';

/** An answer whose change in net income is `difference` a year. */
function impactAnswer(difference: number): HouseholdImpactResponse {
  return {
    income_range: [0, 25000, 100000],
    net_income_change: [0, difference, 0],
    benefit_at_income: {
      baseline: 25000,
      reform: 25000 + difference,
      difference,
      federal_eitc_change: difference,
      state_eitc_change: 0,
    },
    x_axis_max: 100000,
  };
}

function renderHouseholdImpactTab(): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Home />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole('tab', { name: 'Household impact' }));
}

afterEach(() => {
  vi.restoreAllMocks();
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

  it('shows a refusal itself after the household tab is opened again', async () => {
    // Leaving the tab and coming back empties the results area, so a later
    // refusal must not bring the earlier answer back.
    let refuseCalculations = false;
    vi.spyOn(api, 'calculateHouseholdImpact').mockImplementation(async () => {
      if (refuseCalculations) {
        throw new HouseholdCalculationError(REFUSAL_MESSAGE, 429, false, true);
      }
      return impactAnswer(250);
    });
    renderHouseholdImpactTab();
    fireEvent.click(screen.getByRole('button', { name: 'Calculate impact' }));
    expect(await screen.findByText('$25,000')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: 'Policy overview' }));
    fireEvent.click(screen.getByRole('tab', { name: 'Household impact' }));
    expect(screen.queryByText('$25,000')).not.toBeInTheDocument();

    refuseCalculations = true;
    fireEvent.change(screen.getByDisplayValue('25,000'), {
      target: { value: '40,000' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Calculate impact' }));

    expect(await screen.findByText(REFUSAL_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByText('$25,000')).not.toBeInTheDocument();
    expect(
      screen.queryByText('The results below are for the household shown before.'),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText('Household calculator temporarily unavailable'),
    ).toBeInTheDocument();
  });
});
