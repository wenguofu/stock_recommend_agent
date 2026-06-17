## ADDED Requirements

### Requirement: Shared realtime quote hook
The system SHALL expose a `useRealtimeQuote(code)` React hook that wraps the
`/api/sina/realtime/{code}` endpoint through a single TanStack Query subscription,
keyed on `['realtime', code]`.

#### Scenario: Multiple consumers share one fetch
- **WHEN** two or more components call `useRealtimeQuote('000001')` during the same
  render cycle
- **THEN** the underlying fetcher SHALL be invoked exactly once per refetch tick for
  that code

#### Scenario: Empty code short-circuits the fetch
- **WHEN** a caller invokes `useRealtimeQuote('')` or `useRealtimeQuote(undefined)`
- **THEN** the hook SHALL return `enabled: false` and SHALL NOT invoke the fetcher

#### Scenario: Trading-hours-aware refetch interval
- **WHEN** the hook is rendered during A-share trading hours (weekday 09:30-11:30 or
  13:00-15:00 local time)
- **THEN** the hook SHALL use a 5000 ms refetch interval
- **WHEN** the hook is rendered outside trading hours
- **THEN** the hook SHALL use a 60000 ms refetch interval

### Requirement: Watchlist cells consume the shared hook
The watchlist table (`Watchlist.tsx`) SHALL render price, change, and PnL cells by
calling `useRealtimeQuote(code)` instead of issuing three independent
`useQuery({ queryKey: ['realtime', code] })` subscriptions.

#### Scenario: Row consumes single shared quote
- **WHEN** a watchlist row for code `000001` renders its price cell, change cell, and
  PnL cell simultaneously
- **THEN** the system SHALL issue exactly one HTTP request to
  `/api/sina/realtime/000001` per refetch interval, regardless of how many cells in
  that row observe the data