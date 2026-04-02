import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PolicyOverview from '../components/PolicyOverview';

// Mock ResizeObserver for Recharts
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

describe('PolicyOverview', () => {
  it('renders without errors', () => {
    render(<PolicyOverview />);
    expect(screen.getByText('Working Parents Tax Relief Act')).toBeInTheDocument();
  });

  it('displays the four policy provision cards', () => {
    render(<PolicyOverview />);
    expect(screen.getByText('Credit boost (1 child)')).toBeInTheDocument();
    expect(screen.getByText('Credit boost (2+ children)')).toBeInTheDocument();
    expect(screen.getByText('Phaseout adjustment')).toBeInTheDocument();
    expect(screen.getByText('Monthly payment option')).toBeInTheDocument();
  });

  it('displays the EITC parameters table', () => {
    render(<PolicyOverview />);
    expect(screen.getByText('EITC parameter changes for parents of young children')).toBeInTheDocument();
    expect(screen.getByText('1 child with young child')).toBeInTheDocument();
    expect(screen.getByText('2 children with 2 young')).toBeInTheDocument();
    expect(screen.getByText('3+ children with 3 young')).toBeInTheDocument();
  });

  it('shows sources links', () => {
    render(<PolicyOverview />);
    expect(screen.getByText('policyengine-us PR #7914')).toBeInTheDocument();
    expect(screen.getByText('IRC Section 32')).toBeInTheDocument();
  });
});
