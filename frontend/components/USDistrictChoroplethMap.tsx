'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  ComposableMap,
  Geographies,
  Geography,
} from 'react-simple-maps';
import { scaleLinear } from 'd3-scale';

interface DistrictData {
  district: string;
  average_household_income_change: number;
  relative_household_income_change: number;
}

interface Props {
  data: DistrictData[];
  mapType: 'geographic' | 'hex';
  metric: 'absolute' | 'relative';
  height?: number;
}

// Diverging color scale: red (negative) -> gray (zero) -> teal (positive)
const NEGATIVE_COLOR = '#dc2626'; // red-600
const ZERO_COLOR = '#9ca3af'; // gray-400
const POSITIVE_COLOR = '#0d9488'; // teal-600

const formatCurrency = (value: number) => {
  if (Math.abs(value) >= 1000) {
    return `$${(value / 1000).toFixed(1)}k`;
  }
  return `$${value.toFixed(0)}`;
};

const formatPercent = (value: number) => {
  return `${(value * 100).toFixed(2)}%`;
};

export default function USDistrictChoroplethMap({
  data,
  mapType,
  metric,
  height = 500,
}: Props) {
  const [geoData, setGeoData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    district: string;
    value: number;
  } | null>(null);

  // Load GeoJSON based on map type
  useEffect(() => {
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH !== undefined
      ? process.env.NEXT_PUBLIC_BASE_PATH
      : '/us/working-parents-tax-relief-act';
    const filename = mapType === 'hex'
      ? 'congressional_districts_hex.geojson'
      : 'congressional_districts.geojson';

    fetch(`${basePath}/data/geojson/${filename}`)
      .then((res) => res.json())
      .then((data) => setGeoData(data))
      .catch((err) => console.error('Failed to load GeoJSON:', err));
  }, [mapType]);

  // Create lookup map for district data
  const dataLookup = useMemo(() => {
    const lookup = new Map<string, DistrictData>();
    data.forEach((d) => {
      // Normalize district ID
      let districtId = d.district;
      // Handle special cases
      if (districtId.endsWith('-00')) {
        districtId = districtId.replace('-00', '-01');
      }
      if (districtId === 'DC-98') {
        districtId = 'DC-01';
      }
      lookup.set(districtId, d);
    });
    return lookup;
  }, [data]);

  // Calculate color scale
  const colorScale = useMemo(() => {
    if (data.length === 0) return null;

    const values = data.map((d) =>
      metric === 'absolute'
        ? d.average_household_income_change
        : d.relative_household_income_change
    );

    const maxAbs = Math.max(...values.map(Math.abs));
    const domain = [-maxAbs, 0, maxAbs];

    return scaleLinear<string>()
      .domain(domain)
      .range([NEGATIVE_COLOR, ZERO_COLOR, POSITIVE_COLOR]);
  }, [data, metric]);

  // Get color for a district
  const getColor = (districtId: string) => {
    if (!colorScale) return ZERO_COLOR;

    const districtData = dataLookup.get(districtId);
    if (!districtData) return '#e5e7eb'; // gray-200 for missing data

    const value =
      metric === 'absolute'
        ? districtData.average_household_income_change
        : districtData.relative_household_income_change;

    return colorScale(value);
  };

  // Get value for tooltip
  const getValue = (districtId: string) => {
    const districtData = dataLookup.get(districtId);
    if (!districtData) return null;

    return metric === 'absolute'
      ? districtData.average_household_income_change
      : districtData.relative_household_income_change;
  };

  if (!geoData || !colorScale) {
    return (
      <div
        className="flex items-center justify-center bg-gray-50 rounded-lg"
        style={{ height }}
      >
        <p className="text-gray-500">Loading map...</p>
      </div>
    );
  }

  // Calculate legend values
  const values = data.map((d) =>
    metric === 'absolute'
      ? d.average_household_income_change
      : d.relative_household_income_change
  );
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);

  return (
    <div className="relative">
      <ComposableMap
        projection="geoAlbersUsa"
        projectionConfig={{
          scale: mapType === 'hex' ? 900 : 1000,
        }}
        style={{ width: '100%', height }}
      >
        <Geographies geography={geoData}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const districtId = geo.properties.DISTRICT_ID;
              const value = getValue(districtId);

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill={getColor(districtId)}
                  stroke="#fff"
                  strokeWidth={0.5}
                  style={{
                    default: { outline: 'none' },
                    hover: { outline: 'none', opacity: 0.8 },
                    pressed: { outline: 'none' },
                  }}
                  onMouseEnter={(evt) => {
                    if (value !== null) {
                      setTooltip({
                        x: evt.clientX,
                        y: evt.clientY,
                        district: districtId,
                        value,
                      });
                    }
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              );
            })
          }
        </Geographies>
      </ComposableMap>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 pointer-events-none"
          style={{
            left: tooltip.x + 10,
            top: tooltip.y + 10,
          }}
        >
          <p className="font-semibold text-gray-900">{tooltip.district}</p>
          <p className="text-gray-600">
            {metric === 'absolute'
              ? formatCurrency(tooltip.value)
              : formatPercent(tooltip.value)}
          </p>
        </div>
      )}

      {/* Color bar legend */}
      <div className="mt-4 flex items-center justify-center gap-2">
        <span className="text-sm text-gray-600">
          {metric === 'absolute' ? formatCurrency(minValue) : formatPercent(minValue)}
        </span>
        <div
          className="h-4 w-48 rounded"
          style={{
            background: `linear-gradient(to right, ${NEGATIVE_COLOR}, ${ZERO_COLOR}, ${POSITIVE_COLOR})`,
          }}
        />
        <span className="text-sm text-gray-600">
          {metric === 'absolute' ? formatCurrency(maxValue) : formatPercent(maxValue)}
        </span>
      </div>
    </div>
  );
}
