Independent analytics project using the public "2015 Flight Delays and Cancellations" dataset
(Kaggle / US DOT) to investigate airline punctuality performance.

Key contributions:
- Identified a silent data quality issue affecting 8.35% of records (airport codes stored as
  internal DOT IDs instead of IATA codes for one full month), which skewed the headline KPI by
  ~11% without triggering any visible error. Built a verified two-step mapping solution using
  external BTS and OurAirports reference data, validated through four independent checks.
- Designed a star-schema data model in Power Query and DAX, with explicit typing, semantic
  null-handling, and documented design decisions for auditability.
- Developed a mix-adjusted benchmark methodology (DAX) to fairly compare airline delay
  performance by neutralizing differences in route and seasonal mix — surfacing cases where raw
  rankings masked true performance (e.g., an airline appearing top-3 by raw average actually
  ranked 9th once benchmarked against its specific route/seasonal mix).
- Documented known limitations (self-comparison bias, survivorship bias, single-year scope)
  transparently rather than overstating conclusions.

Tools: Power BI, Power Query (M), DAX, Python (data validation scripting).
