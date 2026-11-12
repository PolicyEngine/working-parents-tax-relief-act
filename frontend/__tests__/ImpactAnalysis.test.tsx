import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ImpactAnalysis from '../components/ImpactAnalysis';
import { pauseHouseholdCalculations } from '../hooks/useHouseholdImpact';
import { api, HouseholdCalculationError } from '../lib/api';
import type { HouseholdImpactResponse, HouseholdRequest } from '../lib/types';

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks. It
// is replaced by one that gives the chart a fixed size, so that the chart
// and its axis labels render.
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  const { cloneElement } = await vi.importActual<typeof import('react')>('react');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) => (
      <div data-testid="responsive-container">
        {cloneElement(children as React.ReactElement<{ width: number; height: number }>, {
          width: 800,
          height: 400,
        })}
      </div>
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

const REFUSAL_MESSAGE =
  'Everyone on your network, such as a workshop or an office, shares a ' +
  'limit on calculations a minute, and it has been reached.';

function rateLimitRefusal(): HouseholdCalculationError {
  return new HouseholdCalculationError(REFUSAL_MESSAGE, 429, false, true);
}

function refuseEveryCalculation(): void {
  vi.spyOn(api, 'calculateHouseholdImpact').mockRejectedValue(rateLimitRefusal());
}

/**
 * Calculates each household through the hook: answers or fails each one by
 * its income, and refuses every other household for the rate limit.
 */
function calculateByIncome(
  outcomesByIncome: Map<number, HouseholdImpactResponse | Error>,
): void {
  vi.spyOn(api, 'calculateHouseholdImpact').mockImplementation(async (request) => {
    const outcome = outcomesByIncome.get(request.income);
    if (outcome === undefined) {
      throw rateLimitRefusal();
    }
    if (outcome instanceof Error) {
      throw outcome;
    }
    return outcome;
  });
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

    expect(await screen.findByRole('status')).toHaveTextContent(REFUSAL_MESSAGE);
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

  it('shows the household calculated last after a refusal, not the first one', async () => {
    const queryClient = new QueryClient();
    const laterRequest: HouseholdRequest = { ...earlierRequest, income: 60000 };
    // Both households are calculated through the hook, not set in the
    // cache beforehand; the submitted one is refused.
    calculateByIncome(
      new Map([
        [earlierRequest.income, earlierAnswer],
        [laterRequest.income, impactAnswer(300)],
      ]),
    );

    const { rerender } = render(resultsFor(queryClient, earlierRequest));
    expect(await screen.findByText('$50,000')).toBeInTheDocument();
    rerender(resultsFor(queryClient, laterRequest));
    expect(await screen.findByText('$60,000')).toBeInTheDocument();
    rerender(resultsFor(queryClient, submittedRequest));

    expect(await screen.findByRole('status')).toHaveTextContent(REFUSAL_MESSAGE);
    expect(screen.getByText('$60,000')).toBeInTheDocument();
    expect(screen.queryByText('$50,000')).not.toBeInTheDocument();
    expect(screen.queryByText('$75,000')).not.toBeInTheDocument();
    expect(screen.getAllByText('+$300/year')).toHaveLength(2);
  });

  it('shows the refusal itself after an error box, not an older answer', async () => {
    const queryClient = new QueryClient();
    const failedRequest: HouseholdRequest = { ...earlierRequest, income: 60000 };
    calculateByIncome(
      new Map<number, HouseholdImpactResponse | Error>([
        [earlierRequest.income, earlierAnswer],
        [
          failedRequest.income,
          new HouseholdCalculationError(
            'PolicyEngine could not calculate this household (HTTP 500): ' +
              'Try again in a few minutes.',
            500,
            false,
          ),
        ],
      ]),
    );

    // The earlier household's answer is shown, then an error box replaces
    // it, then the submitted household is refused.
    const { rerender } = render(resultsFor(queryClient, earlierRequest));
    expect(await screen.findByText('$50,000')).toBeInTheDocument();
    rerender(resultsFor(queryClient, failedRequest));
    expect(
      await screen.findByText('Household calculator temporarily unavailable'),
    ).toBeInTheDocument();
    rerender(resultsFor(queryClient, submittedRequest));

    expect(await screen.findByText(REFUSAL_MESSAGE)).toBeInTheDocument();
    expect(
      screen.getByText('Household calculator temporarily unavailable'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText('The results below are for the household shown before.'),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('$50,000')).not.toBeInTheDocument();
  });

  it("keeps the chart's range of the household on screen after a refusal", async () => {
    const queryClient = new QueryClient();
    // The household on screen was calculated up to $60,000 of earnings; the
    // refused one, like the page's own setting, goes up to $100,000.
    const narrowerRequest: HouseholdRequest = { ...earlierRequest, max_earnings: 60000 };
    queryClient.setQueryData(['householdImpact', narrowerRequest], earlierAnswer);
    refuseEveryCalculation();

    const { rerender } = render(resultsFor(queryClient, narrowerRequest));
    rerender(resultsFor(queryClient, submittedRequest));

    expect(await screen.findByRole('status')).toBeInTheDocument();
    // The income axis ends at the shown household's maximum.
    expect(screen.getByText('$60k')).toBeInTheDocument();
    expect(screen.queryByText('$100k')).not.toBeInTheDocument();
  });
});
