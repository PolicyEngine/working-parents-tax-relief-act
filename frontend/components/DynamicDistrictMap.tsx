'use client';

import dynamic from 'next/dynamic';

// Dynamically import the map component with SSR disabled
// react-simple-maps uses browser APIs that don't work server-side
const USDistrictChoroplethMap = dynamic(
  () => import('./USDistrictChoroplethMap'),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center bg-gray-50 rounded-lg" style={{ height: 500 }}>
        <p className="text-gray-500">Loading map...</p>
      </div>
    ),
  }
);

export default USDistrictChoroplethMap;
