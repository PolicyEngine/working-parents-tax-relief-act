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
  return `$${value.toLocaleString()}`;
}

export default function PolicyOverview() {
  // EITC comparison data for single parent with one child under 4
  const eitcComparisonData = useMemo(() => {
    const points = [];
    // Simplified EITC calculation for demonstration
    // Baseline: 34% phase-in, 15.98% phase-out, max ~$4,427
    // Reform: 76.24% phase-in (34% + 42.24%), 20.98% phase-out (15.98% + 5%), max ~$9,927

    for (let income = 0; income <= 60000; income += 500) {
      // Baseline EITC (1 child)
      const baselinePhaseIn = 0.34;
      const baselineMax = 4427;
      const baselinePhaseOutStart = 21430;
      const baselinePhaseOut = 0.1598;

      let baselineEitc;
      if (income <= baselineMax / baselinePhaseIn) {
        baselineEitc = Math.min(income * baselinePhaseIn, baselineMax);
      } else if (income <= baselinePhaseOutStart) {
        baselineEitc = baselineMax;
      } else {
        baselineEitc = Math.max(0, baselineMax - (income - baselinePhaseOutStart) * baselinePhaseOut);
      }

      // Reform EITC (1 child under 4)
      const reformPhaseIn = 0.7624; // 34% + 42.24%
      const reformMax = 9927; // approximately 2.24x
      const reformPhaseOutStart = 21430;
      const reformPhaseOut = 0.2098; // 15.98% + 5%

      let reformEitc;
      if (income <= reformMax / reformPhaseIn) {
        reformEitc = Math.min(income * reformPhaseIn, reformMax);
      } else if (income <= reformPhaseOutStart) {
        reformEitc = reformMax;
      } else {
        reformEitc = Math.max(0, reformMax - (income - reformPhaseOutStart) * reformPhaseOut);
      }

      points.push({
        income,
        baseline: baselineEitc,
        reform: reformEitc,
      });
    }
    return points;
  }, []);

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
          (under age 4). The bill increases credit percentages and phaseout percentages
          to provide additional support during the early childhood years.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
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
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-gray-800 mb-2">Monthly payment option</h3>
            <p className="text-sm text-gray-600">
              The increased credit amount may be paid monthly rather than as
              an annual lump sum.
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-500">
          This reform is implemented in{' '}
          <a
            href="https://github.com/PolicyEngine/policyengine-us/pull/7914"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary-600 hover:underline"
          >
            policyengine-us PR #7914
          </a>
          . See{' '}
          <a
            href="https://www.law.cornell.edu/uscode/text/26/32"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary-600 hover:underline"
          >
            IRC Section 32
          </a>{' '}
          for the current EITC law.
        </p>
      </div>

      {/* EITC comparison chart */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-3">
          EITC by income: single parent with one child under 4 (2026)
        </h3>
        <p className="text-sm text-gray-600 mb-4">
          Comparison of baseline vs. reform EITC by employment income
        </p>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={eitcComparisonData} margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="income"
                tickFormatter={formatDollar}
                tick={{ fontSize: 12 }}
                domain={[0, 60000]}
              />
              <YAxis tickFormatter={formatDollar} tick={{ fontSize: 12 }} />
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
          EITC parameter changes for parents of young children
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-semibold text-gray-900">Scenario</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-900">Baseline max</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-900">Reform max</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-900">Multiplier</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-100">
                <td className="py-3 px-4 text-gray-700">1 child with young child</td>
                <td className="py-3 px-4 text-right text-gray-700">$4,427</td>
                <td className="py-3 px-4 text-right text-gray-700">$9,927</td>
                <td className="py-3 px-4 text-right font-semibold text-primary-600">2.24x</td>
              </tr>
              <tr className="border-b border-gray-100">
                <td className="py-3 px-4 text-gray-700">2 children with 2 young</td>
                <td className="py-3 px-4 text-right text-gray-700">$7,316</td>
                <td className="py-3 px-4 text-right text-gray-700">$18,316</td>
                <td className="py-3 px-4 text-right font-semibold text-primary-600">2.50x</td>
              </tr>
              <tr className="border-b border-gray-100">
                <td className="py-3 px-4 text-gray-700">3+ children with 3 young</td>
                <td className="py-3 px-4 text-right text-gray-700">$8,231</td>
                <td className="py-3 px-4 text-right text-gray-700">$24,736</td>
                <td className="py-3 px-4 text-right font-semibold text-primary-600">3.01x</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
