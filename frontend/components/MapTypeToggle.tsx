'use client';

interface Props {
  mapType: 'geographic' | 'hex';
  onChange: (type: 'geographic' | 'hex') => void;
}

export default function MapTypeToggle({ mapType, onChange }: Props) {
  return (
    <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
      <button
        onClick={() => onChange('geographic')}
        className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
          mapType === 'geographic'
            ? 'bg-white text-primary-600 shadow-sm'
            : 'text-gray-600 hover:text-gray-900'
        }`}
      >
        Geographic
      </button>
      <button
        onClick={() => onChange('hex')}
        className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
          mapType === 'hex'
            ? 'bg-white text-primary-600 shadow-sm'
            : 'text-gray-600 hover:text-gray-900'
        }`}
      >
        Hex grid
      </button>
    </div>
  );
}
