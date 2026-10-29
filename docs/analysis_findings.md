# Analysis Findings – Answer Key

> ⚠️ **Spoiler.** The dataset contains business stories that a good dashboard should surface. Try to find them yourself in Power BI first (Root Cause page, decomposition tree, key influencers). Then compare with this page. Being able to say *"I found this by…"* in an interview is worth far more than reading it here.

All figures: extract as of 30 Sep 2026, default seed. Reproduce with the queries in `sql/kpi_queries.sql` (outputs in `data/sql_output/`).

---

## Executive summary

Northline completed **74,395** jobs and invoiced **$52.7M** between January 2024 and September 2026 at a **54.0%** gross margin. Company SLA compliance is **91.5%** and average CSAT **4.06**, both broadly on target – but the averages hide three problems:

1. **Ottawa is in an SLA crisis.** Compliance fell from **93.0%** (Mar–Sep 2025) to **80.6%** (Mar–Sep 2026), and CSAT from 4.09 to 3.77. Cause: an emergency-repair surge hit just as two senior technicians left and a planned hiring wave was frozen.
2. **Poor first-time fix is costing ~$620K a year** in free warranty callbacks and is the second-biggest driver of low CSAT. Junior technicians cause repeat visits at **twice** the rate of senior technicians, especially on installations.
3. **Hamilton's installation margin fell from 53.5% to 41.3%** after October 2025: parts now cost ~44% more after a supplier change, but customers are still billed from the old parts price list.

A fourth, smaller pattern: tickets raised **Friday afternoon or Saturday** miss SLA far more often than the rest of the week.

---

## Finding 1 – Ottawa SLA collapse (capacity, not performance)

**What the dashboard shows**
- Ottawa SLA compliance: 92–95% through 2025 → 88.6% in Feb 2026 → **73.6% in Aug 2026**. Every other region stayed at 90–94%.
- Ottawa CSAT in Aug 2026: **3.46** vs target 4.0. Month-end backlog roughly doubled (14–25 open requests in 2025 → 25–35 in 2026).
- Ottawa revenue is *up* **16.9% YoY** (Jan–Sep) – the best of any region. Revenue alone would say Ottawa is the star region.

**Root cause (drill path: region → service type → month → technician capacity)**
- Emergency Repair requests in Ottawa rose **61% YoY** (Mar–Sep 2026 vs Mar–Sep 2025) vs **7%** in the other regions. Emergency work is Critical priority with an 8-hour SLA, and it pre-empts scheduled work.
- HR data: a **Senior** and an **Expert** technician left Ottawa in February 2026 and were not replaced. Every other region received a January 2026 hiring wave; Ottawa did not.
- Result: Ottawa's demand per active technician jumped from **~24** to **~30 requests a month** (other regions: 22–24). SLA misses spread across *all* service types (maintenance and inspections too), which is the signature of a capacity problem rather than a skills or process problem.

**Recommendation**
- Backfill the two senior roles and add 3 more technicians (≈ 480 monthly requests ÷ 24 per technician ≈ 20 technicians needed vs 15 today). Use contractors for emergency overflow until hires are productive.
- Re-negotiate or re-price the new emergency-heavy contract: it brings revenue but is eroding service for every other Ottawa customer.
- Add an early-warning KPI: **requests per active technician > 27** for two consecutive months.

**Interview line:** *"Revenue said Ottawa was our best region. SLA and CSAT said it was our worst. The decomposition tree showed the breaches weren't concentrated in one service type, which pointed me away from a skills problem and toward capacity – and the HR data confirmed two senior exits with no backfill."*

---

## Finding 2 – First-time fix and the cost of callbacks

**What the dashboard shows**
- Company first-time fix rate **89.1%**; repeat visit rate **10.7%** of jobs.
- Repeat jobs score **3.53** average CSAT vs **4.14** for first visits. Only missed SLA hurts CSAT more.
- **4,923** callbacks were free warranty work, costing **$1.71M** in labour and parts – about **$620K a year**, roughly 7% of direct cost.

**Root cause**
- Repeat-visit rate (1 − FTF) by skill: Junior **14.4%**, Intermediate 10.1%, Senior 7.3%, Expert 6.5%.
- Installations are worst: Junior first-time fix on installations is **79.8%** vs 91.2% for Experts.
- Juniors do the largest share of the work (37% of closed jobs), and that share is growing: 35% of measurable jobs in 2024 → 41% in 2026 after two junior-heavy hiring waves.

**Recommendation**
- Pair juniors with a senior for their first installations, and add a post-install checklist.
- Lifting Junior FTF to the Intermediate level would avoid ~430 repeat visits a year – about **$120K** in warranty cost plus a measurable CSAT gain.

**Fairness caveat (Technician page):** don't rank individuals company-wide. Compare within region and skill level, with a minimum of 150 jobs – otherwise new hires and technicians who take the hardest jobs look worst.

---

## Finding 3 – Hamilton installation margin squeeze

**What the dashboard shows**
- Hamilton installation gross margin: **53.5%** (Jan 2024–Sep 2025) → **41.3%** (Oct 2025–Sep 2026). Other regions *improved* slightly over the same period (52.5% → 54.3%).
- Average parts cost per Hamilton installation: **$588 → $845** (+44%). In other regions it was flat (~$600 → ~$573).
- Hamilton revenue did **not** move with the cost: revenue per installation is unchanged, so Hamilton still looks fine on the revenue-vs-target page (101% of budget YTD). Only the margin view reveals the problem. Since October 2025 Hamilton has the lowest overall margin of the six regions (51.0% vs 54–56% elsewhere).

**Root cause** – a parts-supplier change in October 2025 raised Hamilton's purchase cost, but the Hamilton parts price list used for billing was never updated. The company has absorbed about **$120K** of extra parts cost in 12 months.

**Recommendation** – update the Hamilton parts price list now; renegotiate or re-tender the supplier contract. Add a **parts cost per job vs price-list** exception alert so a mismatch is caught within one month, not twelve.

**Interview line:** *"Revenue was on target, so nobody looked. I always pair revenue with margin, and a margin drop with no matching price change points at cost – the parts cost per job split by region made it obvious."*

---

## Finding 4 – The Friday-afternoon effect

- Non-critical tickets raised **Friday after 2 pm or on Saturday** meet SLA **83.7%** of the time vs **92.6%** for the rest of the week.
- They are 12% of non-critical jobs but **~24% of all SLA breaches**.
- Critical tickets are unaffected (on-call coverage works for emergencies only).

**Recommendation** – a small Saturday dispatch shift, or SLA clocks that pause outside contracted business hours (check customer contracts – this may be a definition problem rather than a service problem).

---

## Other answers to the business questions

| Question | Answer |
|---|---|
| Which service types take longest? | By median: Scheduled Maintenance (~55h) and Preventive Maintenance (~51h) – long SLAs (72–120h) and scheduled by appointment. Emergency Repair median ~6h. Use median, not mean: a few "waiting on parts" tickets take weeks. |
| Which customers generate the most revenue? | Revenue is concentrated: the top 20% of customers produce ~51% of revenue; Enterprise accounts are 11% of customers but 33% of revenue. ~49% of customers make up 80% of revenue. |
| Are repeat service calls increasing? | Slightly: repeat-visit rate 10.4% (2024) → 10.6% (2025) → 11.3% (2026 YTD). The work mix is shifting to junior technicians (35% → 41% of jobs), and Ottawa's overloaded team adds to it. |
| Is CSAT decreasing? | Company-wide only marginally (4.07 → 4.04). Ottawa accounts for almost all of the decline. |
| What drives month-over-month changes? | Strong seasonality: emergency repairs peak in Jan–Feb and Jul–Aug (heating and cooling failures); maintenance peaks in Apr–May and Sep–Oct; installations dip in Dec–Jan. Always compare to the same month last year before calling a trend. |
| Revenue vs budget | 2025 revenue $19.25M vs $19.46M target (98.9%). In 2026 (Jan–Aug, complete months) Mississauga (95.5%) and Kitchener-Waterloo (96.9%) trail target; Ottawa is ahead (105.7%) – but see Finding 1. |

---

## Data-quality findings worth mentioning

- 1.5% of service-request rows were removed or quarantined; every one is traceable in `data/quarantine/`.
- 160 invoices with negative costs were quarantined. This accounts for the 157 older "closed but not invoiced" jobs in the FSM↔Billing reconciliation – the reconciliation explains itself, which is exactly what you want to show.
- 317 closed jobs had no technician recorded. They were kept (mapped to *Unknown*) so revenue still reconciles; dropping them would understate revenue by ~$227K.
- September 2026 is provisional: invoices lag job closure by up to 10 days, so the latest month's revenue looks ~10–25% low. The model flags complete months (`DimDate[IsCompleteMonth]`) to stop leadership reacting to a false dip.
