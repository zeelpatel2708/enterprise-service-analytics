# Calgary 311 – Insights Fact Sheet (real data)

_Generated 2026-10-22 from `data/calgary/sql_output/`. Window 2024-01-01 – 2026-09-30._

> These numbers are computed automatically. Your job as the analyst: confirm each one in Power BI, dig into the *why*, and write the final story in your own words.

## 1. Scale

**1,384,094** service requests in the window.

| Year | requests | closed_requests | same_day_closure_rate | avg_resolution_days | within_benchmark_rate |
|---|---|---|---|---|---|
| 2024 | 512,640 | 500,724 | 19.5% | 18.0 | 83.0% |
| 2025 | 485,719 | 474,634 | 19.3% | 14.5 | 82.6% |
| 2026 | 385,735 | 357,472 | 20.7% | 7.6 | 87.3% |

_2026 covers January–September only. 2024 is the benchmark year, so its within-benchmark rate is ~80% by definition._

## 2. What people ask for

| rank_no | ServiceName | requests | share_of_total | cumulative_share | yoy_jan_sep |
|---|---|---|---|---|---|
| 1 | WRS - Cart Management | 78,299 | 5.7% | 5.7% | -4.2% |
| 2 | AT - Property Tax Account Inquiry | 50,648 | 3.7% | 9.3% | -64.3% |
| 3 | Parks - Tree Concern - GIS | 42,413 | 3.1% | 12.4% | -11.5% |
| 4 | Corporate - Graffiti Concerns | 33,379 | 2.4% | 14.8% | 24.9% |
| 5 | Bylaw - Snow and Ice on Sidewalk | 31,965 | 2.3% | 17.1% | 24.1% |
| 6 | Bylaw - Long Grass - Weeds Infraction | 31,718 | 2.3% | 19.4% | -15.7% |
| 7 | WRS - Waste - Residential | 29,261 | 2.1% | 21.5% | 10.8% |
| 8 | WRS - Recycling - Blue Cart | 29,013 | 2.1% | 23.6% | 12.3% |
| 9 | Roads - Pothole Maintenance | 26,518 | 1.9% | 25.5% | 50.7% |
| 10 | WRS - Compost - Green Cart | 25,634 | 1.8% | 27.4% | -6.2% |
| 11 | Bylaw - Material on Public Property | 25,289 | 1.8% | 29.2% | 11.8% |
| 12 | WRS - New Service - Carts | 23,607 | 1.7% | 30.9% | -9.3% |
| 13 | Corporate - Encampment Concerns | 22,509 | 1.6% | 32.5% | -18.6% |
| 14 | Roads - Debris on Street/Sidewalk/Boulevard | 19,099 | 1.4% | 33.9% | 2.0% |
| 15 | Roads - Snow and Ice Control | 19,013 | 1.4% | 35.3% | 65.7% |

The top 15 service types account for **35.3%** of all requests.

_Prompt: which of these are seasonal (waste, snow, parks) and which are steady (bylaw, roads)?_

## 3. Fastest-growing services (Jan–Sep 2026 vs Jan–Sep 2025)

| ServiceName | v2025 | v2026 | growth_pct |
|---|---|---|---|
| AT - Assessed Value | 1,542 | 7,294 | 373.0% |
| Roads - Pathway Snow and Ice Concerns | 516 | 1,634 | 216.7% |
| Parks - Natural Area Maintenance - GIS | 566 | 1,367 | 141.5% |
| Parks - PlayBins | 318 | 582 | 83.0% |
| WATS - Construction Inquiry - MAX | 598 | 1,080 | 80.6% |
| Roads - Snow and Ice Control | 2,285 | 3,786 | 65.7% |
| DBBS - SDI - New Subdivision Parks Inspection | 339 | 544 | 60.5% |
| Roads - Pothole Maintenance | 5,229 | 7,881 | 50.7% |
| Roads - Streetlight Damage | 416 | 619 | 48.8% |
| Bylaw - Disturbance and Behavioural Concerns | 2,694 | 3,911 | 45.2% |

_Prompt: is the growth real demand, a new reporting channel, or a re-categorisation of an old service type? Check the monthly trend for a step change._

## 4. Slowest services (median days to close, ≥ 500 closed)

| ServiceName | closed_requests | median_days | p90_days |
|---|---|---|---|
| Roads - NEW Signal, Left Turn or Pedestrian Light Request | 2,098 | 318 | 529 |
| Roads - E-Scooter | 516 | 114 | 461 |
| Active Living Program Application | 2,455 | 77 | 366 |
| WATS - Service and Main Valve Issues | 6,138 | 76 | 217 |
| Roads - Signs - Missing - Damaged | 13,872 | 75 | 364 |
| Roads - Pavement Markings - Missing or Faded | 925 | 75 | 155 |
| CFD - Incident Report Request | 912 | 55 | 121 |
| CFD - Life Safety Systems Inspection - FHB | 1,161 | 45 | 184 |
| WATS - Tap Water Sampling Program | 546 | 42 | 183 |
| WATS - Drainage Bylaw | 1,051 | 41 | 121 |

## 5. Getting faster or slower? (share closed within the 2024 benchmark)

| ServiceCategory | y2024 | y2025 | y2026 | change_pts_2026_vs_2025 |
|---|---|---|---|---|
| 311 Contact Us | 82.1% | 99.8% | n/a | n/a |
| Customer Service & Communications | 82.5% | 88.2% | n/a | n/a |
| DBBS Inspection | 84.4% | n/a | n/a | n/a |
| GFL | 87.3% | 78.6% | 64.6% | -14.0% |
| After Hours Transit | 90.9% | 90.7% | 78.4% | -12.3% |
| Finance | 83.7% | 79.7% | 71.2% | -8.5% |
| UEP | 82.9% | 71.1% | 66.5% | -4.5% |
| PSD | 83.1% | 86.3% | 82.0% | -4.3% |
| HR | 83.1% | 80.5% | 76.3% | -4.2% |
| Facility Mgmt | 82.3% | 86.4% | 82.7% | -3.7% |
| VFH | 83.7% | 86.2% | 82.6% | -3.5% |
| Stewardship of City Owned Land | 84.9% | 77.4% | 74.6% | -2.8% |
| DBBS | 83.4% | 88.0% | 86.1% | -1.9% |
| CFD | 83.9% | 78.3% | 76.4% | -1.9% |
| Recreation | 84.7% | 77.6% | 75.9% | -1.7% |
| DBBS Concern | 83.0% | 84.1% | 83.2% | -0.9% |
| Community Safety | 81.1% | 84.1% | 83.3% | -0.9% |
| ACPL | 90.6% | 89.4% | 88.9% | -0.5% |
| CT | 84.0% | 73.1% | 72.6% | -0.5% |
| Corporate | 82.8% | 79.7% | 79.4% | -0.3% |
| Law | 82.9% | 83.3% | 83.3% | -0.0% |
| UD | 82.0% | 82.6% | 82.8% | 0.2% |
| WATS | 87.5% | 82.7% | 83.2% | 0.5% |
| CSC | 81.7% | 81.0% | 81.6% | 0.6% |
| RSP | 82.8% | 92.9% | 94.1% | 1.1% |
| Roads | 87.3% | 85.3% | 86.6% | 1.3% |
| Parks | 83.3% | 87.2% | 90.0% | 2.8% |
| AS | 85.4% | 89.6% | 92.8% | 3.2% |
| Bylaw | 82.2% | 79.8% | 84.2% | 4.4% |
| WRS | 83.5% | 84.9% | 89.5% | 4.6% |
| Business Safety | 84.0% | 82.8% | 89.7% | 7.0% |
| CT AC | 83.9% | 81.4% | 89.3% | 7.9% |
| Opinions on Business Units | 88.1% | 84.8% | 95.7% | 10.9% |
| Active Living Program Application | 100.0% | 87.2% | 100.0% | 12.8% |
| AT | 86.2% | 65.4% | 84.1% | 18.7% |
| CE | 81.4% | 60.4% | 87.1% | 26.8% |

Biggest decline: **GFL** (-14.0% pts). Biggest improvement: **DBBS Inspection** (n/a pts).

_Prompt: use the decomposition tree on the decline – is it one service, one agency, or one season?_

## 6. Channel shift

Digital share (app/web/email) of requests by year: 2024: 21.8%, 2025: 18.7%, 2026: 18.7%

## 7. Day of week

| DayOfWeek | requests | share | same_day_closure_rate |
|---|---|---|---|
| Monday | 223,411 | 16.1% | 18.7% |
| Tuesday | 255,593 | 18.5% | 20.2% |
| Wednesday | 245,396 | 17.7% | 20.8% |
| Thursday | 239,631 | 17.3% | 21.4% |
| Friday | 213,834 | 15.4% | 20.3% |
| Saturday | 108,141 | 7.8% | 16.5% |
| Sunday | 98,088 | 7.1% | 16.9% |

## 8. Seasonality – peak month per category (2024–2025 average)

| ServiceCategory | MonthNumber | seasonality_index |
|---|---|---|
| AT | 6 | 1.90× |
| Bylaw | 7 | 1.61× |
| Corporate | 8 | 1.25× |
| DBBS Inspection | 4 | 1.28× |
| Parks | 6 | 1.95× |
| Roads | 5 | 1.24× |
| WATS | 7 | 1.40× |
| WRS | 5 | 1.29× |

## 9. Backlog

Open requests at month end: **9,288** (20240131) → **51,264** (20260930). Share older than 90 days at the latest snapshot: **65.5%**.

| Agency | open_requests | stale_over_365_days | stale_share |
|---|---|---|---|
| OS - Mobility | 25,901 | 11,348 | 43.8% |
| PICS - Customer Service and Communications | 8,366 | 8,365 | 100.0% |
| OS - Parks and Open Spaces | 2,245 | 558 | 24.9% |
| CS - Emergency Management and Community Safety | 7,175 | 529 | 7.4% |
| OS - Water Services | 2,030 | 173 | 8.5% |
| CS - Calgary Fire | 1,192 | 87 | 7.3% |
| OS - Calgary Transit | 1,756 | 76 | 4.3% |
| CS - Recreation and Social Programs | 547 | 66 | 12.1% |

_Prompt: are year-old open tickets real work, or tickets nobody closed in the system? That is a data-governance finding, not just an operations one._

## 10. Data-quality flags in the model

| flag | rows_flagged |
|---|---|
| Closure date imputed from updated_date | 0 |
| Re-opened (had closed_date, status open) | 3,573 |
| Closed as duplicate | 13,676 |
| Open > 365 days | 21,259 |
| Unknown community | 94,791 |

