'use client';

import { useMemo, useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from 'recharts';
import ChartWatermark from './ChartWatermark';

function formatDollar(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}k`;
  return `$${value.toFixed(0)}`;
}

function formatDollarFull(value: number): string {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Chart visualization data for different young children scenarios
// These are illustrative approximations for the policy overview chart
// 2026 EITC baseline parameters per IRS Rev. Proc. 2025-32
// Phase-out start for 1+ children: $23,890
const CHART_SCENARIOS = {
  1: {
    label: '1 young child',
    data: generateChartData(0.34, 4427, 23890, 0.1598, 0.4224, 0.05, 80000),
    xMax: 80000,
    xTicks: [0, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000],
    yMax: 10000,
    yTicks: [0, 5000, 10000],
  },
  2: {
    label: '2 young children',
    data: generateChartData(0.40, 7316, 23890, 0.2106, 0.6014, 0.10, 90000),
    xMax: 90000,
    xTicks: [0, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000],
    yMax: 20000,
    yTicks: [0, 5000, 10000, 15000, 20000],
  },
  3: {
    label: '3 young children',
    data: generateChartData(0.45, 8231, 23890, 0.2106, 0.9021, 0.15, 100000),
    xMax: 100000,
    xTicks: [0, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000, 100000],
    yMax: 25000,
    yTicks: [0, 5000, 10000, 15000, 20000, 25000],
  },
};

function generateChartData(
  basePhaseIn: number, baseMax: number, phaseOutStart: number, basePhaseOut: number,
  reformBoost: number, phaseOutBoost: number, xMax: number
) {
  const points = [];
  for (let income = 0; income <= xMax; income += 500) {
    // Baseline curve
    let baseline;
    if (income <= baseMax / basePhaseIn) {
      baseline = Math.min(income * basePhaseIn, baseMax);
    } else if (income <= phaseOutStart) {
      baseline = baseMax;
    } else {
      baseline = Math.max(0, baseMax - (income - phaseOutStart) * basePhaseOut);
    }

    // Reform curve
    const refPhaseIn = basePhaseIn + reformBoost;
    const refMax = baseMax + (reformBoost * (baseMax / basePhaseIn));
    const refPhaseOut = basePhaseOut + phaseOutBoost;

    let reform;
    if (income <= refMax / refPhaseIn) {
      reform = Math.min(income * refPhaseIn, refMax);
    } else if (income <= phaseOutStart) {
      reform = refMax;
    } else {
      reform = Math.max(0, refMax - (income - phaseOutStart) * refPhaseOut);
    }

    points.push({ income, baseline, reform });
  }
  return points;
}

export default function PolicyOverview() {
  const [youngChildren, setYoungChildren] = useState<1 | 2 | 3>(1);
  const scenario = CHART_SCENARIOS[youngChildren];
  const eitcComparisonData = scenario.data;

  return (
    <div className="space-y-10">
      {/* Summary */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          Working Parents Tax Relief Act
        </h2>
        <p className="text-gray-700 mb-4">
          The Working Parents Tax Relief Act of 2026, introduced by Rep. McDonald Rivet,
          enhances the Earned Income Tax Credit (EITC) for parents of young children
          (under age 4). The bill increases credit percentages and phaseout percentages,
          providing qualifying households with a higher benefit amount.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-gray-800 mb-2">Credit boost (1 child)</h3>
            <p className="text-sm text-gray-600">
              If a qualifying child has not attained age 4, the credit percentage
              increases by 42.24 percentage points (from 34% to 76.24%).
            </p>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-gray-800 mb-2">Credit boost (2+ children)</h3>
            <p className="text-sm text-gray-600">
              For families with 2+ children, increase credit percentage by 30.07
              percentage points for each of the youngest 3 qualifying children
              under age 4.
            </p>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-gray-800 mb-2">Phaseout adjustment</h3>
            <p className="text-sm text-gray-600">
              The phaseout percentage increases by 5 percentage points for each
              of the youngest 3 qualifying children under age 4 (maximum +15pp).
            </p>
          </div>
        </div>
      </div>

      {/* EITC comparison chart */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-3">
          EITC by income (2026)
        </h3>
        <p className="text-sm text-gray-600 mb-4">
          Comparison of baseline vs. reform EITC by employment income
        </p>
        {/* Scenario tabs */}
        <div className="flex space-x-2 mb-4">
          {([1, 2, 3] as const).map((num) => (
            <button
              key={num}
              onClick={() => setYoungChildren(num)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                youngChildren === num
                  ? 'bg-primary-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {CHART_SCENARIOS[num].label}
            </button>
          ))}
        </div>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={eitcComparisonData} margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="income"
                tickFormatter={formatDollar}
                tick={{ fontSize: 12 }}
                domain={[0, scenario.xMax]}
                ticks={scenario.xTicks}
              />
              <YAxis
                tickFormatter={formatDollar}
                tick={{ fontSize: 12 }}
                domain={[0, scenario.yMax]}
                ticks={scenario.yTicks}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null;
                  const baseline = payload.find(p => p.dataKey === 'baseline')?.value as number;
                  const reform = payload.find(p => p.dataKey === 'reform')?.value as number;
                  const difference = reform - baseline;
                  return (
                    <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-lg">
                      <p className="font-semibold text-gray-900 mb-2">Income: {formatDollarFull(label as number)}</p>
                      <p className="text-sm text-gray-600">Current law: {formatDollarFull(baseline)}</p>
                      <p className="text-sm text-gray-600">Working Parents Tax Relief Act: {formatDollarFull(reform)}</p>
                      <p className="text-sm font-semibold text-primary-700 mt-1">Increase: +{formatDollarFull(difference)}</p>
                    </div>
                  );
                }}
              />
              <Legend />
              <ReferenceLine y={0} stroke="var(--chart-reference)" strokeWidth={1} />
              <Line
                type="monotone"
                dataKey="baseline"
                stroke="var(--chart-baseline)"
                strokeWidth={2}
                strokeDasharray="5 5"
                name="Current law"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="reform"
                stroke="var(--chart-positive)"
                strokeWidth={3}
                name="Working Parents Tax Relief Act"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <ChartWatermark />
      </div>

      {/* EITC parameters table */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-3">
          EITC parameter changes for parents of young children (2026)
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-semibold text-gray-900">Scenario</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-900">Baseline maximum</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-900">Reform maximum</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-900">Increase</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-100">
                <td className="py-3 px-4 text-gray-700">One young child</td>
                <td className="py-3 px-4 text-right text-gray-700">$4,427</td>
                <td className="py-3 px-4 text-right text-gray-700">$9,927</td>
                <td className="py-3 px-4 text-right font-semibold text-primary-600">$5,500</td>
              </tr>
              <tr className="border-b border-gray-100">
                <td className="py-3 px-4 text-gray-700">Two young children</td>
                <td className="py-3 px-4 text-right text-gray-700">$7,316</td>
                <td className="py-3 px-4 text-right text-gray-700">$18,316</td>
                <td className="py-3 px-4 text-right font-semibold text-primary-600">$11,000</td>
              </tr>
              <tr className="border-b border-gray-100">
                <td className="py-3 px-4 text-gray-700">Three young children</td>
                <td className="py-3 px-4 text-right text-gray-700">$8,231</td>
                <td className="py-3 px-4 text-right text-gray-700">$24,731</td>
                <td className="py-3 px-4 text-right font-semibold text-primary-600">$16,500</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
