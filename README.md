# Airline Delay Analytics — Power BI

Independent analytics project using the public "2015 Flight Delays and Cancellations" dataset
(Kaggle / US DOT) to investigate airline punctuality performance.

The project goes beyond building dashboards: it includes a full data modeling pipeline in
Power Query and DAX, a data quality investigation that uncovered a hidden issue affecting
8.35% of the dataset, and a custom benchmark methodology to fairly compare airline performance.

## Key Contributions

- **Data quality investigation:** Identified a silent data quality issue affecting 8.35% of
  records (airport codes stored as internal DOT IDs instead of IATA codes for one full month),
  which skewed the headline KPI by ~11% without triggering any visible error. Built a verified
  two-step mapping solution using external BTS and OurAirports reference data, validated through
  four independent checks.
- **Data modeling:** Designed a star-schema data model in Power Query and DAX, with explicit
  typing, semantic null-handling, and documented design decisions for auditability.
- **Benchmark methodology:** Developed a mix-adjusted benchmark (DAX) to fairly compare airline
  delay performance by neutralizing differences in route and seasonal mix — surfacing cases
  where raw rankings masked true performance (e.g., an airline appearing top-3 by raw average
  actually ranked 9th once benchmarked against its specific route/seasonal mix).
- **Transparent limitations:** Documented known limitations (self-comparison bias, survivorship
  bias, single-year scope) rather than overstating conclusions.

## Repository Contents

| File | Description |
|---|---|
| `Airline_Delay_PowerBI_Dashboard.pbix` | The full Power BI file: data model, Power Query transformations, DAX measures, and report pages. |
| `Dashboard Overview.png` | Screenshot of the main dashboard page, showing key punctuality KPIs, the airline benchmark chart, intraday delay accumulation, and delay cause breakdown. |
| `EDA_flights_2015.ipynb` | Jupyter notebook with exploratory data analysis performed in Python prior to building the data model — initial profiling, distribution checks, and discovery of the data quality issue. |
| `construir_mapa.py` | Python script that builds and validates the airport code mapping table (internal DOT ID → IATA code) used to fix the data quality issue. Includes four independent validation checks before generating any output. |
| `Technical_Notes.pdf` | Detailed technical documentation covering data model design decisions, DAX logic, methodology, and known limitations. |

## Tools

Power BI · Power Query (M) · DAX · Python (data validation scripting)
