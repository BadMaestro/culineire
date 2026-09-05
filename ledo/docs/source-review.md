# Source review - 2026-09-05

Supplied files are reference material, not execution authority. Original copies
remain unchanged under E:\LEDO DRIVE and the staged LEDO Project directories.

## Verified for the content release

- `Fleet 1.pdf`, page 1: rendered and inspected. NIO EL6 2025 / Standard SUV /
  4 passengers / 4 large suitcases. NIO ES8 2023 / Premium SUV / 6 passengers
  and 6 hand luggage; alternatively 4 passengers, 4 large cases and 2 hand bags.
  XPENG X9 2026 / Luxury MPV / 6 passengers and 6 hand luggage; alternatively
  4 passengers, 4 large cases and 4 hand bags. One vehicle per listed model.
- `4_5807659210057459813.pdf`, pages 1-4: company identity, public contact
  phone/email/address, 12-hour recommended lead time, child seats by request
  with age/weight, and pets only by prior arrangement. These supply the footer
  and three customer FAQ entries. This PDF contains the completed questionnaire.
- `LedoDriveFAQ.docx` is the unfilled questionnaire, not a second set of answers.

## Unresolved; do not activate fares or payment processing

- NOK rate card: 30 minutes free waiting. EUR card: 60 minutes. Completed
  questionnaire pages 3 and 5 say 30 minutes. Asked owner to resolve the conflict.
- NOK OSL-TRF Luxury night price is 8200, although the stated +20% on 6900
  would be 8280. Do not silently correct or recalculate the supplied figure.
- Cards define 7 route pairs, three vehicle classes, both directions,
  day/night/weekend/holiday bands, per-km and waiting rates. Existing MVP quote
  logic does not yet model those dimensions and must not be seeded blindly.
- Online deposits, payment holds, receipts, cancellation fees, no-show handling
  and company invoicing are requirements, not implemented functionality.
- Questionnaire requests a separate Julebord service and corporate portal.
  Both remain planned, not represented as operational.
- No actual fleet photographs supplied. Do not present generated cars as photos
  of this fleet. Keep cards factual until approved imagery is available.

## Release gate - 2.5.1819

Scope: four-language fleet cards, sourced contact/FAQ content and fixing the
header overlap observed on the actual production page at narrow width.
Header stays in document flow so wrapped navigation cannot cover the hero.
No production database, access flag, payment or fare changes.

Constitution 2.12.0 sections 8 and 17 re-read; Bolt; current main/server base
`a1bdbfc017d4ea1992b6f710d0f1bea76ce9595a`; index reviewed; PostgreSQL tests,
image weight and diff checks required. Collectstatic/restart required. Rollback
by reverting this content release and deploying that exact reviewed commit.
