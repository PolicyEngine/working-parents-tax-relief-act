'use client';

import { useState, useEffect } from 'react';
import USDistrictChoroplethMap from './DynamicDistrictMap';
import MapTypeToggle from './MapTypeToggle';
import ChartWatermark from './ChartWatermark';

interface DistrictData {
  district: string;
  average_household_income_change: number;
  relative_household_income_change: number;
  state: string;
  year: number;
}

interface Props {
  year?: number;
}

export default function CongressionalDistrictImpact({ year = 2026 }: Props) {
  const [data, setData] = useState<DistrictData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mapType, setMapType] = useState<'geographic' | 'hex'>('geographic');
  const [metric, setMetric] = useState<'absolute' | 'relative'>('absolute');

  useEffect(() => {
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH !== undefined
      ? process.env.NEXT_PUBLIC_BASE_PATH
      : '/us/working-parents-tax-relief-act';

    fetch(`${basePath}/data/congressional_districts.csv`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load district data');
        return res.text();
      })
      .then((text) => {
        const lines = text.trim().split('\n');
        const headers = lines[0].split(',');
        const rows = lines.slice(1).map((line) => {
          const values = line.split(',');
          const row: Record<string, string | number> = {};
          headers.forEach((h, i) => {
            const val = values[i];
            row[h] = isNaN(Number(val)) ? val : Number(val);
          });
          return row as unknown as DistrictData;
        });
        // Filter by year if needed
        const filtered = rows.filter((r) => r.year === year);
        setData(filtered.length > 0 ? filtered : rows);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [year]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
          <p className="mt-4 text-gray-600">Loading district data...</p>
        </div>
      </div>
    );
  }

  if (error || data.length === 0) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <h2 className="text-yellow-800 font-semibold mb-2">
          Congressional district data not yet available
        </h2>
        <p className="text-yellow-700">
          {error || 'District-level impact data has not been generated yet.'}
        </p>
        <p className="text-yellow-700 mt-2">
          Run: <code className="bg-yellow-100 px-2 py-1 rounded">modal run scripts/modal_district_pipeline.py</code>
        </p>
      </div>
    );
  }

  // Calculate summary stats
  const avgChange = data.reduce((sum, d) => sum + d.average_household_income_change, 0) / data.length;
  const minChange = Math.min(...data.map((d) => d.average_household_income_change));
  const maxChange = Math.max(...data.map((d) => d.average_household_income_change));

  // Top 5 districts by absolute change
  const topDistricts = [...data]
    .sort((a, b) => b.average_household_income_change - a.average_household_income_change)
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Congressional District Impacts ({year})
        </h2>
        <p className="text-gray-600">
          Average household income change by congressional district under the Working Parents Tax Relief Act.
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <MapTypeToggle mapType={mapType} onChange={setMapType} />

        <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
          <button
            onClick={() => setMetric('absolute')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              metric === 'absolute'
                ? 'bg-white text-primary-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Absolute ($)
          </button>
          <button
            onClick={() => setMetric('relative')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              metric === 'relative'
                ? 'bg-white text-primary-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Relative (%)
          </button>
        </div>
      </div>

      {/* Map */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <USDistrictChoroplethMap
          data={data}
          mapType={mapType}
          metric={metric}
          height={500}
        />
        <ChartWatermark />
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Average change</h3>
          <p className="text-2xl font-bold text-gray-900">
            ${avgChange.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Minimum change</h3>
          <p className="text-2xl font-bold text-gray-900">
            ${minChange.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Maximum change</h3>
          <p className="text-2xl font-bold text-gray-900">
            ${maxChange.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </p>
        </div>
      </div>

      {/* Top districts table */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-3">
          Top 5 districts by income change
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-semibold text-gray-900">District</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-900">Average change</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-900">Relative change</th>
              </tr>
            </thead>
            <tbody>
              {topDistricts.map((d) => (
                <tr key={d.district} className="border-b border-gray-100">
                  <td className="py-3 px-4 text-gray-700 font-medium">{d.district}</td>
                  <td className="py-3 px-4 text-right text-gray-700">
                    ${d.average_household_income_change.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </td>
                  <td className="py-3 px-4 text-right text-gray-700">
                    {(d.relative_household_income_change * 100).toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
