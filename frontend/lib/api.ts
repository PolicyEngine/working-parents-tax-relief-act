/**
 * Household impact via www.policyengine.org's dashboard API.
 *
 * The page never calls the PolicyEngine Public API itself: the dashboard
 * API's server adds PolicyEngine's credential and forwards each household
 * to the Public API's /us/calculate.
 */

import {
  createPolicyEngineApiClient,
  PolicyEngineApiError,
} from "@policyengine/api-client";

import {
  HouseholdRequest,
  HouseholdImpactResponse,
} from "./types";
import {
  buildHouseholdSituation,
  buildReformPolicy,
  interpolate,
} from "./household";

const policyengine = createPolicyEngineApiClient();

/** How long a calculation may take before the page gives up on it. */
const CALCULATION_TIMEOUT_MILLISECONDS = 120_000;

/** Brief gateway failures, which are worth retrying. */
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

/** A household calculation failed; `message` is written for the user. */
export class HouseholdCalculationError extends Error {
  override name = "HouseholdCalculationError";

  constructor(
    message: string,
    /** The dashboard API's HTTP status, or null when no answer was read. */
    readonly status: number | null,
    /** Whether trying again at once could succeed. */
    readonly retryable: boolean,
  ) {
    super(message);
  }
}

/** Whether React Query should retry a failed household calculation. */
export function shouldRetryHouseholdCalculation(
  failureCount: number,
  error: unknown,
): boolean {
  return (
    failureCount < 2 &&
    error instanceof HouseholdCalculationError &&
    error.retryable
  );
}

function dashboardApiMessage(body: unknown): string | null {
  if (typeof body === "object" && body !== null) {
    const message = (body as { message?: unknown }).message;
    if (typeof message === "string" && message.length > 0) {
      return message;
    }
  }
  return null;
}

/** Turns a failure of the dashboard API client into a message for the user. */
function calculationError(error: PolicyEngineApiError): HouseholdCalculationError {
  if (error.status === null) {
    // On another origin, such as the dashboard's own host, the firewall's
    // 429 has no CORS headers, so the browser reports a network failure.
    return new HouseholdCalculationError(
      "PolicyEngine's calculation service could not be reached. If many " +
        "calculations have been run from your network in the last minute, " +
        "wait a minute and try again.",
      null,
      false,
    );
  }
  if (error.status === 429) {
    return new HouseholdCalculationError(
      "Too many calculations have been run from your network in the last " +
        "minute. Wait a minute and try again.",
      429,
      false,
    );
  }
  if (error.status === 403) {
    return new HouseholdCalculationError(
      "This page's address is not allowed to run PolicyEngine calculations.",
      403,
      false,
    );
  }
  const detail =
    dashboardApiMessage(error.body) ?? "Try again in a few minutes.";
  return new HouseholdCalculationError(
    `PolicyEngine could not calculate this household (HTTP ${error.status}): ${detail}`,
    error.status,
    RETRYABLE_STATUSES.has(error.status),
  );
}

/** Values over the income axis, keyed by year. */
type ValuesByYear = Record<string, number[]>;

/** The parts of a calculated household this page reads. */
interface CalculatedHousehold {
  people: Record<string, Record<string, ValuesByYear>>;
  households: Record<string, Record<string, ValuesByYear>>;
  tax_units: Record<string, Record<string, ValuesByYear>>;
}

async function calculateHousehold(
  household: Record<string, unknown>,
  policy?: Record<string, unknown>
): Promise<CalculatedHousehold> {
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    CALCULATION_TIMEOUT_MILLISECONDS
  );
  try {
    return await policyengine.calculateHousehold<CalculatedHousehold>(
      { country: "us", household, policy },
      { signal: controller.signal }
    );
  } catch (error) {
    if (controller.signal.aborted) {
      throw new HouseholdCalculationError(
        "The calculation took longer than two minutes. Try again.",
        null,
        false,
      );
    }
    if (error instanceof PolicyEngineApiError) {
      throw calculationError(error);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  async calculateHouseholdImpact(
    request: HouseholdRequest
  ): Promise<HouseholdImpactResponse> {
    const household = buildHouseholdSituation(request);
    const policy = buildReformPolicy();
    const yearStr = String(request.year);

    // Run baseline and reform in parallel. Each resolves with the
    // calculated household (the Public API's `result`).
    const [baselineResult, reformResult] = await Promise.all([
      calculateHousehold(household),
      calculateHousehold(household, policy),
    ]);

    // Extract arrays from the calculated households
    const baselineNetIncome: number[] =
      baselineResult.households["your household"][
        "household_net_income"
      ][yearStr];
    const reformNetIncome: number[] =
      reformResult.households["your household"][
        "household_net_income"
      ][yearStr];
    const incomeRange: number[] =
      baselineResult.people["you"][
        "employment_income"
      ][yearStr];

    // Extract EITC arrays
    const baselineFederalEitc: number[] =
      baselineResult.tax_units["your tax unit"]["eitc"][yearStr];
    const reformFederalEitc: number[] =
      reformResult.tax_units["your tax unit"]["eitc"][yearStr];
    const baselineStateEitc: number[] =
      baselineResult.tax_units["your tax unit"]["state_eitc"][yearStr];
    const reformStateEitc: number[] =
      reformResult.tax_units["your tax unit"]["state_eitc"][yearStr];

    // Compute net income change at each point
    const netIncomeChange = reformNetIncome.map(
      (val, i) => val - baselineNetIncome[i]
    );

    // Interpolate at user's income
    const baselineAtIncome = interpolate(
      incomeRange,
      baselineNetIncome,
      request.income
    );
    const reformAtIncome = interpolate(
      incomeRange,
      reformNetIncome,
      request.income
    );

    // Interpolate EITC values at user's income
    const baselineFederalEitcAtIncome = interpolate(
      incomeRange,
      baselineFederalEitc,
      request.income
    );
    const reformFederalEitcAtIncome = interpolate(
      incomeRange,
      reformFederalEitc,
      request.income
    );
    const baselineStateEitcAtIncome = interpolate(
      incomeRange,
      baselineStateEitc,
      request.income
    );
    const reformStateEitcAtIncome = interpolate(
      incomeRange,
      reformStateEitc,
      request.income
    );

    return {
      income_range: incomeRange,
      net_income_change: netIncomeChange,
      benefit_at_income: {
        baseline: baselineAtIncome,
        reform: reformAtIncome,
        difference: reformAtIncome - baselineAtIncome,
        federal_eitc_change: reformFederalEitcAtIncome - baselineFederalEitcAtIncome,
        state_eitc_change: reformStateEitcAtIncome - baselineStateEitcAtIncome,
      },
      x_axis_max: request.max_earnings,
    };
  },
};
