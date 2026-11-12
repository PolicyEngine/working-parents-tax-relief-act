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

// A household shown earlier, and the one submitted after it. They differ in
// income, state and year, so each label shows which household it is for.
const earlierRequest: HouseholdRequest = {
  age_head: 35,
  age_spouse: null,
  dependent_ages: [5],
  income: 50000,
  year: 2025,
  max_earnings: 100000,
  state_code: 'NY',
};
const submittedRequest: HouseholdRequest = {
  ...earlierRequest,
  income: 75000,
  year: 2026,
  state_code: 'CA',
};

function impactAnswer(difference: number): HouseholdImpactResponse {
  return {
    income_range: [0, 50000, 100000],
    net_income_change: [0, difference, 0],
    benefit_at_income: {
      baseline: 50000,
      reform: 50000 + difference,
      difference,
      federal_eitc_change: 0,
      state_eitc_change: difference,
    },
    x_axis_max: 100000,
  };
}

const earlierAnswer = impactAnswer(200);

function refuseEveryCalculation(): void {
  vi.spyOn(api, 'calculateHouseholdImpact').mockRejectedValue(
    new HouseholdCalculationError(
      'Everyone on your network, such as a workshop or an office, shares a ' +
        'limit on calculations a minute, and it has been reached.',
      429,
      false,
      true,
    ),
  );
}

/** The results area as the page renders it for `request`. */
function resultsFor(queryClient: QueryClient, request: HouseholdRequest) {
  return (
    <QueryClientProvider client={queryClient}>
      <ImpactAnalysis request={request} triggered maxEarnings={100000} />
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  pauseHouseholdCalculations(0);
});

describe('ImpactAnalysis', () => {
  it('shows the answer on screen and the notice after a rate-limit refusal', async () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(['householdImpact', earlierRequest], earlierAnswer);
    refuseEveryCalculation();

    // The page shows the earlier household, then the reader submits another.
    const { rerender } = render(resultsFor(queryClient, earlierRequest));
    rerender(resultsFor(queryClient, submittedRequest));

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Everyone on your network, such as a workshop or an office, shares a ' +
        'limit on calculations a minute, and it has been reached.',
    );
    expect(
      screen.getByText('The results below are for the household shown before.'),
    ).toBeInTheDocument();
    // The earlier household's income, state, year and answer, not the
    // refused one's.
    expect(screen.getByText('$50,000')).toBeInTheDocument();
    expect(screen.queryByText('$75,000')).not.toBeInTheDocument();
    expect(screen.getByText('NY EITC change')).toBeInTheDocument();
    expect(screen.getByText('Your personal impact (2025)')).toBeInTheDocument();
    expect(screen.getAllByText('+$200/year')).toHaveLength(2);
    expect(
      screen.queryByText('Household calculator temporarily unavailable'),
    ).not.toBeInTheDocument();
  });

  it('shows the answer that was on screen after a refusal, not the one calculated last', async () => {
    const queryClient = new QueryClient();
    const otherRequest: HouseholdRequest = { ...earlierRequest, income: 60000 };
    queryClient.setQueryData(['householdImpact', earlierRequest], earlierAnswer, {
      updatedAt: 1_000,
    });
    queryClient.setQueryData(['householdImpact', otherRequest], impactAnswer(300), {
      updatedAt: 2_000,
    });
    refuseEveryCalculation();

    // The reader calculated the earlier household, then another, then went
    // back to the earlier one, which the page shows from the cache.
    const { rerender } = render(resultsFor(queryClient, earlierRequest));
    rerender(resultsFor(queryClient, otherRequest));
    rerender(resultsFor(queryClient, earlierRequest));
    rerender(resultsFor(queryClient, submittedRequest));

    expect(await screen.findByRole('status')).toBeInTheDocument();
    expect(screen.getByText('$50,000')).toBeInTheDocument();
    expect(screen.queryByText('$60,000')).not.toBeInTheDocument();
    expect(screen.getAllByText('+$200/year')).toHaveLength(2);
  });
});
