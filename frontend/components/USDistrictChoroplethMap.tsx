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
  winners_share?: number;
  losers_share?: number;
  poverty_pct_change?: number;
  child_poverty_pct_change?: number;
  state?: string;
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

// State name lookup
const STATE_NAMES: Record<string, string> = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California',
  CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', DC: 'District of Columbia',
  FL: 'Florida', GA: 'Georgia', HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois',
  IN: 'Indiana', IA: 'Iowa', KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana',
  ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota',
  MS: 'Mississippi', MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada',
  NH: 'New Hampshire', NJ: 'New Jersey', NM: 'New Mexico', NY: 'New York',
  NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma', OR: 'Oregon',
  PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina', SD: 'South Dakota',
  TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont', VA: 'Virginia',
  WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
};

// Arrow icons for impact direction
const ArrowUpIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M7 17l9.2-9.2M17 17V7H7" />
  </svg>
);

const ArrowDownIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M17 7l-9.2 9.2M7 7v10h10" />
  </svg>
);

// Detail panel for selected district
function DistrictDetailPanel({
  district,
  onClose
}: {
  district: DistrictData;
  onClose: () => void;
}) {
  const avgChange = district.average_household_income_change;
  const isPositive = avgChange > 0;
  const isNeutral = avgChange === 0;
  const stateAbbr = district.district.split('-')[0];
  const districtNum = district.district.split('-')[1];
  const stateName = STATE_NAMES[stateAbbr] || stateAbbr;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-5 min-h-[280px]">
      {/* Header */}
      <div className="flex items-start justify-between mb-4 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <span
            className="inline-flex items-center justify-center w-10 h-10 rounded-lg text-white font-bold text-lg"
            style={{ backgroundColor: isPositive ? '#319795' : '#475569' }}
          >
            {districtNum}
          </span>
          <div>
            <h4 className="text-lg font-semibold text-gray-900">
              {stateName} District {parseInt(districtNum)}
            </h4>
            <p className="text-sm text-gray-500">{district.district}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 p-1"
          title="Close"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Main Impact Value */}
      <div className="flex items-center gap-2 mb-5">
        <span className={isNeutral ? 'text-gray-500' : (isPositive ? 'text-teal-600' : 'text-red-600')}>
          {!isNeutral && (isPositive ? <ArrowUpIcon /> : <ArrowDownIcon />)}
        </span>
        <span
          className={`text-3xl font-bold ${isNeutral ? 'text-gray-600' : (isPositive ? 'text-teal-700' : 'text-red-700')}`}
        >
          {isPositive ? '+' : ''}{formatCurrency(avgChange)}
        </span>
        <span className="text-base text-gray-500">
          average household impact
        </span>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3">
        {/* Winners / Losers */}
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
            Winners / Losers
          </p>
          <p className="text-base font-bold">
            <span className="text-teal-600">
              {district.winners_share !== undefined
                ? `${(district.winners_share * 100).toFixed(0)}%`
                : 'N/A'}
            </span>
            <span className="text-gray-400"> / </span>
            <span className="text-red-600">
              {district.losers_share !== undefined
                ? `${(district.losers_share * 100).toFixed(0)}%`
                : 'N/A'}
            </span>
          </p>
        </div>

        {/* Poverty Change */}
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
            Poverty
          </p>
          <p
            className={`text-base font-bold ${
              district.poverty_pct_change === undefined || district.poverty_pct_change === 0
                ? 'text-gray-500'
                : district.poverty_pct_change < 0
                  ? 'text-teal-600'
                  : 'text-red-600'
            }`}
          >
            {district.poverty_pct_change === undefined || district.poverty_pct_change === 0
              ? 'No change'
              : `${district.poverty_pct_change > 0 ? '+' : ''}${district.poverty_pct_change.toFixed(1)}%`}
          </p>
        </div>

        {/* Child Poverty Change */}
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
            Child Poverty
          </p>
          <p
            className={`text-base font-bold ${
              district.child_poverty_pct_change === undefined || district.child_poverty_pct_change === 0
                ? 'text-gray-500'
                : district.child_poverty_pct_change < 0
                  ? 'text-teal-600'
                  : 'text-red-600'
            }`}
          >
            {district.child_poverty_pct_change === undefined || district.child_poverty_pct_change === 0
              ? 'No change'
              : `${district.child_poverty_pct_change > 0 ? '+' : ''}${district.child_poverty_pct_change.toFixed(1)}%`}
          </p>
        </div>
      </div>
    </div>
  );
}

// Empty state when no district is selected
function SelectDistrictPrompt() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[280px] p-8 bg-gray-50 rounded-xl border border-dashed border-gray-300">
      <div className="w-12 h-12 rounded-full bg-teal-50 flex items-center justify-center mb-3">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#319795" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
        </svg>
      </div>
      <p className="text-gray-500 text-sm text-center">
        Click on a district to view detailed impact analysis
      </p>
    </div>
  );
}

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
  const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null);
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

  // Get selected district data
  const selectedDistrictData = useMemo(() => {
    if (!selectedDistrict) return null;
    return dataLookup.get(selectedDistrict) || null;
  }, [selectedDistrict, dataLookup]);

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

  // Handle district click
  const handleDistrictClick = useCallback((districtId: string) => {
    setSelectedDistrict(prev => prev === districtId ? null : districtId);
  }, []);

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
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Map Container */}
      <div className="lg:col-span-2 relative">
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
                  const isSelected = selectedDistrict === districtId;

                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      fill={getColor(districtId)}
                      stroke={isSelected ? '#0f766e' : '#fff'}
                      strokeWidth={isSelected ? 2 : 0.5}
                      style={{
                        default: { outline: 'none', cursor: 'pointer' },
                        hover: { outline: 'none', opacity: 0.8, cursor: 'pointer' },
                        pressed: { outline: 'none' },
                      }}
                      onClick={() => handleDistrictClick(districtId)}
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

      {/* Detail Panel */}
      <div className="lg:col-span-1">
        {selectedDistrictData ? (
          <DistrictDetailPanel
            district={selectedDistrictData}
            onClose={() => setSelectedDistrict(null)}
          />
        ) : (
          <SelectDistrictPrompt />
        )}
      </div>
    </div>
  );
}
