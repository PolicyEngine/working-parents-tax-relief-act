'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { useHouseholdImpact } from '@/hooks/useHouseholdImpact';
import type { HouseholdRequest } from '@/lib/types';
import ChartWatermark from './ChartWatermark';

interface Props {
  request: HouseholdRequest | null;
  triggered: boolean;
  maxEarnings?: number;
}

export default function ImpactAnalysis({ request, triggered, maxEarnings }: Props) {
  const { data, isLoading, error } = useHouseholdImpact(request, triggered);

  if (!triggered) return null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
          <p className="mt-4 text-gray-600">Calculating impact...</p>
        </div>
      </div>
    );
  }

  if (error) {
    const errorMessage = (error as Error).message;
    const isApiNotUpdated = errorMessage.includes('500') || errorMessage.includes('too many values');
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <h2 className="text-yellow-800 font-semibold mb-2">Household calculator temporarily unavailable</h2>
        {isApiNotUpdated ? (
          <p className="text-yellow-700">
            The PolicyEngine API is being updated to include the Working Parents Tax Relief Act reform.
            Please check back soon, or view the <strong>National impact</strong> tab for precomputed results.
          </p>
        ) : (
          <p className="text-yellow-700">{errorMessage}</p>
        )}
      </div>
    );
  }

  if (!data) return null;

  const formatCurrency = (value: number) =>
    `$${Math.round(value).toLocaleString('en-US')}`;
  const formatIncome = (value: number) => {
    if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    return `$${(value / 1000).toFixed(0)}k`;
  };

  const benefitData = data.benefit_at_income;

  const xMax = maxEarnings ?? data.x_axis_max;
  const chartData = data.income_range
    .map((inc, i) => ({
      income: inc,
      benefit: data.net_income_change[i],
    }))
    .filter((d) => d.income <= xMax);

  return (
    <div className="space-y-8">
      <h2 className="text-2xl font-bold text-primary">Impact analysis</h2>

      {/* Personal impact */}
      <div>
        <h3 className="text-xl font-bold text-gray-800 mb-4">Your personal impact ({request?.year ?? 2026})</h3>
        <p className="text-gray-600 mb-4">
          Based on your employment income of <strong>{formatCurrency(request?.income ?? 0)}</strong>
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Net income change */}
          <div
            className={`rounded-lg p-6 border ${
              benefitData.difference > 0
                ? 'bg-green-50 border-success'
                : benefitData.difference < 0
                ? 'bg-red-50 border-red-300'
                : 'bg-gray-50 border-gray-300'
            }`}
          >
            <p className="text-sm text-gray-700 mb-2">Change in net income</p>
            <p
              className={`text-3xl font-bold ${
                benefitData.difference > 0
                  ? 'text-green-600'
                  : benefitData.difference < 0
                  ? 'text-red-600'
                  : 'text-gray-600'
              }`}
            >
              {benefitData.difference !== 0
                ? `${benefitData.difference > 0 ? '+' : ''}${formatCurrency(benefitData.difference)}/year`
                : '$0/year'}
            </p>
          </div>

          {/* Federal EITC change */}
          <div
            className={`rounded-lg p-6 border ${
              benefitData.federal_eitc_change > 0
                ? 'bg-green-50 border-success'
                : benefitData.federal_eitc_change < 0
                ? 'bg-red-50 border-red-300'
                : 'bg-gray-50 border-gray-300'
            }`}
          >
            <p className="text-sm text-gray-700 mb-2">Federal EITC change</p>
            <p
              className={`text-3xl font-bold ${
                benefitData.federal_eitc_change > 0
                  ? 'text-green-600'
                  : benefitData.federal_eitc_change < 0
                  ? 'text-red-600'
                  : 'text-gray-600'
              }`}
            >
              {benefitData.federal_eitc_change !== 0
                ? `${benefitData.federal_eitc_change > 0 ? '+' : ''}${formatCurrency(benefitData.federal_eitc_change)}/year`
                : '$0/year'}
            </p>
          </div>

          {/* State EITC change */}
          <div
            className={`rounded-lg p-6 border ${
              benefitData.state_eitc_change > 0
                ? 'bg-green-50 border-success'
                : benefitData.state_eitc_change < 0
                ? 'bg-red-50 border-red-300'
                : 'bg-gray-50 border-gray-300'
            }`}
          >
            <p className="text-sm text-gray-700 mb-2">{request?.state_code} EITC change</p>
            <p
              className={`text-3xl font-bold ${
                benefitData.state_eitc_change > 0
                  ? 'text-green-600'
                  : benefitData.state_eitc_change < 0
                  ? 'text-red-600'
                  : 'text-gray-600'
              }`}
            >
              {benefitData.state_eitc_change !== 0
                ? `${benefitData.state_eitc_change > 0 ? '+' : ''}${formatCurrency(benefitData.state_eitc_change)}/year`
                : '$0/year'}
            </p>
          </div>
        </div>
      </div>

      <hr className="border-gray-200" />

      {/* Chart */}
      <div className="bg-white border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-800">
          Change in net income by employment income ({request?.year ?? 2026})
        </h3>
        <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ left: 20, right: 20, top: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
              <XAxis
                dataKey="income"
                type="number"
                tickFormatter={formatIncome}
                stroke="var(--chart-reference)"
                domain={[0, xMax]}
                allowDataOverflow={false}
              />
              <YAxis tickFormatter={formatCurrency} stroke="var(--chart-reference)" width={80} />
              <Tooltip
                formatter={(value: number) => formatCurrency(value)}
                labelFormatter={(value: number) => `Income: ${formatCurrency(value)}`}
              />
              <Legend />
              <ReferenceLine y={0} stroke="var(--chart-reference)" strokeWidth={2} />
              <Line
                type="monotone"
                dataKey="benefit"
                stroke="var(--chart-positive)"
                strokeWidth={3}
                name="Change in Net Income"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        <ChartWatermark />
      </div>
    </div>
  );
}
