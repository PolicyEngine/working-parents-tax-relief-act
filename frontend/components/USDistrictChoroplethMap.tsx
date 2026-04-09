'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
} from 'react-simple-maps';
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

// PolicyEngine app-v2 diverging color scale: gray (negative) -> light gray (zero) -> teal (positive)
// From @policyengine/ui-kit design tokens
const DIVERGING_COLORS = [
  '#475569', // gray-600 (most negative)
  '#94A3B8', // gray-400
  '#E2E8F0', // gray-200 (neutral/zero)
  '#81E6D9', // teal-200
  '#319795', // teal-500 (most positive)
];

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
  const [zoom, setZoom] = useState(1);
  const [center, setCenter] = useState<[number, number]>([-96, 38]);

  const handleZoomIn = useCallback(() => {
    setZoom((prev) => Math.min(prev * 1.5, 8));
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoom((prev) => Math.max(prev / 1.5, 1));
  }, []);

  const handleReset = useCallback(() => {
    setZoom(1);
    setCenter([-96, 38]);
  }, []);

  const handleMoveEnd = useCallback((position: { coordinates: [number, number]; zoom: number }) => {
    setCenter(position.coordinates);
    setZoom(position.zoom);
  }, []);

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

  // Calculate color range (min/max centered at zero)
  const colorRange = useMemo(() => {
    if (data.length === 0) return { min: 0, max: 0 };

    const values = data.map((d) =>
      metric === 'absolute'
        ? d.average_household_income_change
        : d.relative_household_income_change
    );

    const maxAbs = Math.max(...values.map(Math.abs));
    return { min: -maxAbs, max: maxAbs };
  }, [data, metric]);

  // Interpolate color from the 5-stop diverging scale
  const interpolateColor = useCallback((value: number, min: number, max: number): string => {
    if (min >= max) return DIVERGING_COLORS[2]; // neutral

    // Normalize to [0, 1]
    const t = Math.max(0, Math.min(1, (value - min) / (max - min)));

    // Map to position across 4 segments (5 colors)
    const segments = DIVERGING_COLORS.length - 1;
    const segPos = t * segments;
    const segIndex = Math.min(Math.floor(segPos), segments - 1);
    const segT = segPos - segIndex;

    // Parse hex colors
    const parseHex = (color: string) => ({
      r: parseInt(color.slice(1, 3), 16),
      g: parseInt(color.slice(3, 5), 16),
      b: parseInt(color.slice(5, 7), 16),
    });

    const c0 = parseHex(DIVERGING_COLORS[segIndex]);
    const c1 = parseHex(DIVERGING_COLORS[segIndex + 1]);

    // Interpolate
    const r = Math.round(c0.r + (c1.r - c0.r) * segT);
    const g = Math.round(c0.g + (c1.g - c0.g) * segT);
    const b = Math.round(c0.b + (c1.b - c0.b) * segT);

    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  }, []);

  // Get color for a district
  const getColor = useCallback((districtId: string) => {
    const districtData = dataLookup.get(districtId);
    if (!districtData) return '#e5e7eb'; // gray-200 for missing data

    const value =
      metric === 'absolute'
        ? districtData.average_household_income_change
        : districtData.relative_household_income_change;

    return interpolateColor(value, colorRange.min, colorRange.max);
  }, [dataLookup, metric, interpolateColor, colorRange]);

  // Get value for tooltip
  const getValue = (districtId: string) => {
    const districtData = dataLookup.get(districtId);
    if (!districtData) return null;

    return metric === 'absolute'
      ? districtData.average_household_income_change
      : districtData.relative_household_income_change;
  };

  if (!geoData || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-gray-50 rounded-lg"
        style={{ height }}
      >
        <p className="text-gray-500">Loading map...</p>
      </div>
    );
  }

  // Calculate legend values (actual min/max, not symmetrical)
  const values = data.map((d) =>
    metric === 'absolute'
      ? d.average_household_income_change
      : d.relative_household_income_change
  );
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);

  // Hex map uses geoMercator to avoid clipping issues with geoAlbersUsa
  // Geographic map uses standard geoAlbersUsa projection
  const projection = mapType === 'hex' ? 'geoMercator' : 'geoAlbersUsa';
  const projectionScale = mapType === 'hex' ? 550 : 1000;
  const projectionCenter: [number, number] = [-98, 38];

  return (
    <div className="relative">
      {/* Zoom controls */}
      <div className="absolute top-2 right-2 z-10 flex flex-col gap-1">
        <button
          onClick={handleZoomIn}
          className="w-8 h-8 bg-white border border-gray-300 rounded shadow-sm hover:bg-gray-50 flex items-center justify-center text-gray-700 font-bold"
          title="Zoom in"
        >
          +
        </button>
        <button
          onClick={handleZoomOut}
          className="w-8 h-8 bg-white border border-gray-300 rounded shadow-sm hover:bg-gray-50 flex items-center justify-center text-gray-700 font-bold"
          title="Zoom out"
        >
          −
        </button>
        <button
          onClick={handleReset}
          className="w-8 h-8 bg-white border border-gray-300 rounded shadow-sm hover:bg-gray-50 flex items-center justify-center text-gray-700 text-xs"
          title="Reset view"
        >
          ↺
        </button>
      </div>

      <ComposableMap
        projection={projection}
        projectionConfig={{
          scale: projectionScale,
          center: projectionCenter,
        }}
        style={{ width: '100%', height }}
      >
        <ZoomableGroup
          zoom={zoom}
          center={center}
          onMoveEnd={handleMoveEnd}
          minZoom={1}
          maxZoom={8}
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
        </ZoomableGroup>
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
            background: `linear-gradient(to right, ${DIVERGING_COLORS.join(', ')})`,
          }}
        />
        <span className="text-sm text-gray-600">
          {metric === 'absolute' ? formatCurrency(maxValue) : formatPercent(maxValue)}
        </span>
      </div>
    </div>
  );
}
