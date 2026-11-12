import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ImpactAnalysis from '../components/ImpactAnalysis';
import { pauseHouseholdCalculations } from '../hooks/useHouseholdImpact';
import { api, HouseholdCalculationError } from '../lib/api';
import type { HouseholdImpactResponse, HouseholdRequest } from '../lib/types';

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

// A household calculated earlier, and the one submitted after it.
const earlierRequest: HouseholdRequest = {
  age_head: 35,
  age_spouse: null,
  dependent_ages: [5],
  income: 50000,
  year: 2026,
  max_earnings: 100000,
  state_code: 'CA',
};
const submittedRequest: HouseholdRequest = { ...earlierRequest, income: 75000 };

const earlierAnswer: HouseholdImpactResponse = {
  income_range: [0, 50000, 100000],
  net_income_change: [0, 200, 0],
  benefit_at_income: {
    baseline: 50000,
    reform: 50200,
    difference: 200,
    federal_eitc_change: 0,
    state_eitc_change: 200,
  },
  x_axis_max: 100000,
};

afterEach(() => {
  vi.restoreAllMocks();
  pauseHouseholdCalculations(0);
});

describe('ImpactAnalysis', () => {
  it('shows the last answer and the notice after a rate-limit refusal', async () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(['householdImpact', earlierRequest], earlierAnswer);
    vi.spyOn(api, 'calculateHouseholdImpact').mockRejectedValue(
      new HouseholdCalculationError(
        'Everyone on your network, such as a workshop or an office, shares a ' +
          'limit on calculations a minute, and it has been reached.',
        429,
        false,
        true,
      ),
    );

    render(
      <QueryClientProvider client={queryClient}>
        <ImpactAnalysis request={submittedRequest} triggered maxEarnings={100000} />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      /shares a limit on calculations a minute/,
    );
    expect(screen.getByText(/last household calculated/)).toBeInTheDocument();
    // The earlier household's income and answer, not the refused one's.
    expect(screen.getByText('$50,000')).toBeInTheDocument();
    expect(screen.queryByText('$75,000')).not.toBeInTheDocument();
    expect(screen.getAllByText('+$200/year')).toHaveLength(2);
    expect(
      screen.queryByText('Household calculator temporarily unavailable'),
    ).not.toBeInTheDocument();
  });
});
