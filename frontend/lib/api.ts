/**
 * Household impact via the PolicyEngine API.
 *
 * Calls https://api.policyengine.org/us/calculate directly -
 * no backend server required.
 */

import {
  HouseholdRequest,
  HouseholdImpactResponse,
} from "./types";
import {
  buildHouseholdSituation,
  buildReformPolicy,
  interpolate,
} from "./household";

const PE_API_URL = "https://api.policyengine.org";

class ApiError extends Error {
  status: number;
  response: unknown;
  constructor(message: string, status: number, response?: unknown) {
    super(message);
    this.status = status;
    this.response = response;
  }
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeout = 120000
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(id);
  }
}

interface PEApiResponse {
  result: {
    households: Record<string, Record<string, Record<string, number[]>>>;
    people: Record<string, Record<string, Record<string, number[]>>>;
    tax_units: Record<string, Record<string, Record<string, number[]>>>;
  };
}

async function peCalculate(body: Record<string, unknown>): Promise<PEApiResponse> {
  const response = await fetchWithTimeout(
    `${PE_API_URL}/us/calculate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  if (!response.ok) {
    let errorBody;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = await response.text();
    }
    const errorMessage = typeof errorBody === 'object' && errorBody?.message
      ? errorBody.message
      : typeof errorBody === 'string'
        ? errorBody
        : JSON.stringify(errorBody);
    throw new ApiError(
      `PolicyEngine API error: ${response.status} - ${errorMessage}`,
      response.status,
      errorBody
    );
  }
  return response.json();
}

export const api = {
  async calculateHouseholdImpact(
    request: HouseholdRequest
  ): Promise<HouseholdImpactResponse> {
    const household = buildHouseholdSituation(request);
    const policy = buildReformPolicy();
    const yearStr = String(request.year);

    // Run baseline and reform in parallel
    const [baselineResult, reformResult] = await Promise.all([
      peCalculate({ household }),
      peCalculate({ household, policy }),
    ]);

    // Extract arrays from PE API response
    const baselineNetIncome: number[] =
      baselineResult.result.households["your household"][
        "household_net_income"
      ][yearStr];
    const reformNetIncome: number[] =
      reformResult.result.households["your household"][
        "household_net_income"
      ][yearStr];
    const incomeRange: number[] =
      baselineResult.result.people["you"][
        "employment_income"
      ][yearStr];

    // Extract EITC arrays
    const baselineFederalEitc: number[] =
      baselineResult.result.tax_units["your tax unit"]["eitc"][yearStr];
    const reformFederalEitc: number[] =
      reformResult.result.tax_units["your tax unit"]["eitc"][yearStr];
    const baselineStateEitc: number[] =
      baselineResult.result.tax_units["your tax unit"]["state_eitc"][yearStr];
    const reformStateEitc: number[] =
      reformResult.result.tax_units["your tax unit"]["state_eitc"][yearStr];

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
