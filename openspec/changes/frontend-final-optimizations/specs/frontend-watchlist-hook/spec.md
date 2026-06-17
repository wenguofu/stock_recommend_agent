## ADDED Requirements

### Requirement: Shared paginated watchlist hook
The system SHALL expose a `useWatchlist(page, pageSize)` hook returning
`{ data, isLoading, isError, error, refetch }`, backed by a single TanStack Query
subscription keyed on `['watchlist', page, pageSize]`.

#### Scenario: Two pages share one fetch per page
- **WHEN** both `Home.tsx` and `Watchlist.tsx` render with the same `page` and `pageSize`
- **THEN** the underlying fetcher SHALL be invoked exactly once per page-state combo,
  regardless of how many pages observe it.

#### Scenario: Pagination changes refetch with new key
- **WHEN** the caller passes a different `page` or `pageSize`
- **THEN** the hook SHALL issue a new fetch keyed on the new tuple.