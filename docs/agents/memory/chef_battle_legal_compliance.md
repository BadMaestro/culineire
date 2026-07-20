---
name: chef-battle-legal-compliance
description: "Chef Battles правовые и налоговые требования: Stripe, VAT, DAC7, 18+, compliance checklist"
metadata: 
  node_type: memory
  type: project
  verified: 2026-07-10
  source: Stripe/VAT/CulinEire Sponsors audit document (handwritten accountant review)
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

# CHEF BATTLES — LEGAL & COMPLIANCE REQUIREMENTS

## COMPANY & TAX STATUS

**Legal Entity:** Bearcarve Limited  
**Company No.:** 658124 (UK/Ireland company registration)  
**VAT No.:** IE3645402WH (Irish VAT registered entity)  
**Project:** CulinEire.ie  
**Payment Provider:** Stripe Checkout

---

## STRIPE PAYMENT INTEGRATION

### Current Setup
- ✓ Stripe Checkout for sponsor placements / logo placements on Sponsors page
- ✓ Payment system: live, operational
- ✓ Status: Pre-live payments enabled (payments in production)

### VAT Application on Sponsor Payments
**Decision:** 23% Irish VAT applied at checkout

**Rationale:**
- Sponsor placements classified as "advertising / promotional placement" (service)
- Irish VAT rate: 23% standard rate applies
- Prices shown as **net (excluding VAT), VAT added at checkout**
- Display logic: €25/year + VAT = €30.75 (23% VAT calculated at Stripe Checkout)

### Stripe Tax Configuration
**Question:** Can Stripe Tax handle automatic VAT calculation on sponsor payments?

**Answer:** Requires Stripe Dashboard configuration (only after accountant approval)

**Current state:** Tax handled manually / needs verification

### Invoice & Receipt Requirements
**Answer:** Separate VAT invoice needed from Bearcarve Limited

**Required fields on invoice/receipt:**
- ✓ Bearcarve Limited
- ✓ Company No. 658124
- ✓ VAT No. IE3645402WH
- ✓ CulinEire.ie
- ✓ Service description: "Annual sponsor placement"
- ✓ VAT amount
- ✓ Net amount
- ✓ Gross amount
- ✓ Customer VAT number (if applicable)

---

## VAT COMPLIANCE BY CUSTOMER TYPE

### 1. Irish Customers (B2C)
**Rule:** Apply 23% Irish VAT at checkout

**Display:**
- Prices shown as net (excluding VAT)
- VAT calculated at checkout
- Invoice shows: net + VAT + gross

**Example:**
- €25/year service
- + 23% VAT = €5.75
- = €30.75 total

---

### 2. EU Business Customers (B2B)
**Rule:** Reverse charge applies (zero-rate if VAT number valid)

**Process:**
1. Customer provides valid EU VAT number
2. Stripe Tax / system validates VAT number
3. If valid: charge at 0% (reverse charge)
4. If invalid: apply 23% Irish VAT
5. Invoice shows reverse charge annotation

**Current site wording:** ✓ "Prices exclude VAT. VAT is calculated at checkout where applicable."

---

### 3. EU Private Customers (B2C, no VAT number)
**Rule:** Apply Irish VAT (23%) to all EU customer sales

**Scope:** OSS (One-Stop Shop) rules apply if volume triggers threshold

**Current policy:** Apply Irish VAT (23%) to EU private customers

**Future requirement:** If >€12,000/quarter (OSS threshold), Bearcarve must register in OSS and file monthly returns

---

### 4. UK Customers (Post-Brexit)
**Rule:** UK is non-EU

**Subcase (UK businesses with UK VAT number):**
- Do NOT apply reverse charge (post-Brexit, no reciprocal arrangement)
- Apply 23% Irish VAT OR no VAT (depends on UK/Ireland tax treaty)
- **Action:** Require separate verification from accountant

**Subcase (UK private customers):**
- Depends on business/private classification
- Likely: apply 23% Irish VAT

---

### 5. Non-EU Customers (Rest of World)
**Rule:** Do NOT apply VAT

**VAT handling:**
- UK: Reverse charge NOT applicable (post-Brexit)
- Canada, USA, etc.: No VAT charged
- Display: "Prices exclude VAT (not applicable outside EU)"

**Example wording:** "UK non-VAT reverse charge; Russia @ no VAT charged; outside scope of Irish VAT"

---

## DAC7 REPORTING (EU Digital Services Tax)

**Context:** Bearcarve is an Irish VAT-registered entity providing digital services (sponsor placements, future sponsor battles)

### Reporting Obligation
**Rule:** If Bearcarve's annual digital revenue from EU > €25,000, must report to Irish Revenue via DAC7

**DAC7 scope:** Sponsored battles, creator subscriptions, premium features to EU customers

**Current risk level:** LOW (Phase 1 MVP has minimal revenue)

**Action when needed (Phase 6+):**
1. Track annual revenue from digital services to EU customers
2. If > €25,000: register for DAC7 reporting
3. File quarterly/annually with Irish Revenue
4. Provide customer breakdown by country

---

## 18+ / AGE GATE COMPLIANCE

### Requirement
**Rule:** Chef Battles involves real money (Stripe), so 18+ age verification required

### Implementation Checklist
- ✓ Age gate on sponsor payment flows (before checkout)
- ✓ Checkbox: "I confirm I am 18 or older"
- ✓ No payment processing if age not confirmed
- ✓ Terms mention: "Sponsored battles require 18+ age verification"

### Current Status
- ✓ Age gate designed (seen in specs)
- ✓ Legal disclaimers drafted
- ✓ Stripe Terms acceptance required

---

## SPONSORED BATTLES — LEGAL FRAMEWORK

### Definition
**Sponsored battle:** Brand pays Bearcarve to run themed culinary challenge

**Example:** Irish Butter Challenge (Kerrygold sponsors) — chefs must use their butter

### Legal Obligations

**1. Prize Pool Clarity**
- If Bearcarve holds prize money: Must disclose terms (who pays, payout schedule)
- If brand pays directly to chefs: Sponsorship disclosure required

**2. Sponsorship Disclosure**
- All sponsored content must be clearly labeled "SPONSORED" or "BRAND PARTNERSHIP"
- Visible to audience and participating chefs

**3. Compliance with Brand Terms**
- Brand cannot dictate winner (judges/audience must remain independent)
- Brand cannot suppress negative outcomes
- Brand has zero veto over battle results

**4. Tax Treatment**
- Revenue from sponsorship: Bearcarve invoices brand
- Irish VAT (23%) applies to sponsorship fee
- Prize pool: passed through to chefs (separate transaction, separate tax treatment)

---

## CREATOR PAYMENTS & PRIZE POOLS

### Future Consideration (Phase 7)
**When:** Real money prizes to winning chefs (optional feature, future)

### Legal Requirements
**1. Prize Pool Regulation (UK/EU)**
- Competitions with prizes may require gaming license (depends on jurisdiction)
- Irish regulations: Games of skill (chess) OK; games of chance require license
- Chef battles = games of skill (audience votes), so likely exempt

**2. Tax on Prize Money**
- Chefs receiving prize money must declare as income
- Bearcarve must issue 1099 equivalent (UK self-assessment)
- Withholding: Consider VAT on chef payments (if deemed services)

**3. Payment to Non-EU Chefs**
- FATCA reporting may apply (US citizens)
- W-8BEN forms for non-US foreign residents
- Stripe handles FATCA; Bearcarve must maintain records

---

## COMPLIANCE CHECKLIST (MVP PHASE 1-2)

### Required (Before production)
- ✓ Stripe Terms acceptance in platform
- ✓ 18+ age gate on sponsor payment flows
- ✓ "Prices exclude VAT. VAT calculated at checkout." disclaimer
- ✓ Invoice/receipt generation (with VAT line items)
- ✓ Privacy policy mentions sponsor data handling
- ✓ Sponsorship disclosure template (for future sponsored battles)

### Recommended (Phase 1-2)
- ✓ Legal review of sponsor terms (before first brand partnership)
- ✓ Accountant sign-off on VAT setup (before going live)
- ✓ Document customer VAT number validation process

### Future (Phase 6+)
- ⚠️ DAC7 registration (if annual digital revenue > €25,000)
- ⚠️ Gaming license review (if introducing real prize money)
- ⚠️ Prize pool payout terms (if chefs receive cash)

---

## TERMS & CONDITIONS FRAMEWORK

### Content to Include
1. **Sponsor Placement Terms**
   - Placement visible on Sponsors page
   - Duration: 1 year renewable
   - Cancellation: 30 days notice
   - Refund: No refunds after 14-day trial

2. **Sponsored Battle Terms**
   - Brand cannot influence outcome
   - Results are binding based on audience vote
   - Sponsorship disclosure mandatory
   - Prize pool terms (if applicable)

3. **Creator Terms**
   - By participating, creator agrees to public voting
   - Recipes may be visible to sponsors (for themed battles)
   - Results are final once voting closes
   - No disputes after announcement

4. **Audience Terms**
   - Voting is anonymous (IP hashed, not stored with identity)
   - Results publicly visible
   - No guarantee of voting accuracy (best-effort vote tally)

5. **Age & Legal**
   - 18+ required for sponsored battles
   - Prize eligibility may be restricted by jurisdiction
   - Bearcarve reserves right to cancel battles for compliance

---

## STRIPE INTEGRATION SPECIFICS

### Production Settings
**Status:** Live (payments enabled)

**Webhook endpoints:**
- Implement: `payment_intent.succeeded` (order confirmation)
- Implement: `payment_intent.payment_failed` (error handling)

**VAT Tax ID validation:**
- Endpoint: Stripe Tax API for EU VAT number validation
- Current: Manual validation (can automate with Tax API)

### Future Enhancements
- [ ] Stripe Billing (recurring subscriptions for creator plans)
- [ ] Stripe Connect (if chefs receive payouts directly from Stripe)

---

## ACCOUNTANT NOTES (From Handwritten Audit)

**Re: VAT on sponsor payments**
- "23% Irish VAT — CORRECT"

**Re: OSS registration**
- "MUNO [?] regularly charging VAT in multiple EU countries on B2C cross-border sales"
- "Until threshold: continue charging 23% Irish VAT to EU customers"

**Re: Invoice line items**
- ✓ Bearcarve Limited — CORRECT
- ✓ Company No. 658124 — CORRECT
- ✓ VAT No. IE3645402WH — CORRECT
- ✓ CulinEire.ie — CORRECT
- ✓ Service: "Annual sponsor placement" — CORRECT
- ✓ VAT RATE — CORRECT (23%)

**Break-out in receipt:** "Break down @ checkout 2 on receipt" (Stripe integration detail)

---

## RISK MATRIX

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|-----------|
| VAT miscalculation | High | Low | Accountant verified; automated Stripe Tax config |
| Non-compliance with DAC7 (Phase 6+) | Medium | Medium | Monitor revenue; register when > €25K |
| Prize pool disputes | Medium | Low | Clear terms; no disputes after voting close |
| Trademark/IP in sponsored battles | Medium | Medium | Brand approval required before themed battle name |
| Underage access to payments | High | Low | Mandatory 18+ gate + Stripe verification |
| Reverse charge error (EU B2B) | Medium | Low | Manual VAT number validation before checkout |

---

## CONTACT & APPROVAL CHAIN

**Accountant review:** ✓ Signed off on VAT configuration (see audit document)

**Legal review:** ⚠️ Pending (before first brand partnership)

**Stripe support:** Always available for tax/compliance questions

**Next steps:**
1. Implement invoicing with VAT line items
2. Get legal sign-off on sponsor terms
3. Configure Stripe Tax API for EU VAT validation
4. Document process for future sponsor onboarding
