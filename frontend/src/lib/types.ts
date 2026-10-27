export type Severity = "info" | "low" | "medium" | "high";

export interface RedFlag {
  code: string;
  severity: Severity;
  title: string;
  detail: string;
}

export interface Components {
  deal: number | null;
  km: number | null;
  health: number | null;
  issues: number | null;
  seller: number | null;
}

export interface RdwSummary {
  found: boolean;
  apk_expiry: string | null;
  odometer_judgement: string | null;
  open_recall: boolean | null;
  is_import: boolean | null;
  taxi: boolean | null;
  towing_braked: number | null;
  range_km: number | null;
}

export interface Duplicate {
  id: number;
  source: string;
  source_label: string;
  url: string;
  price_eur: number | null;
}

export interface ListingCard {
  id: number;
  title: string;
  make: string | null;
  model: string | null;
  make_name: string | null;
  model_name: string | null;
  generation: string | null;
  generation_name: string | null;
  trim: string | null;
  kenteken: string | null;
  year: number | null;
  first_registration: string | null;
  mileage_km: number | null;
  price_eur: number | null;
  price_type: string;
  first_price_eur: number | null;
  price_drops: number;
  fuel: string | null;
  fuel_label: string | null;
  transmission: string | null;
  body: string | null;
  body_label: string | null;
  power_kw: number | null;
  power_pk: number | null;
  battery_kwh: number | null;
  colour: string | null;
  seller_type: string | null;
  seller_name: string | null;
  seller_bovag: boolean;
  warranty_months: number | null;
  postcode: string | null;
  city: string | null;
  lat: number | null;
  lon: number | null;
  distance_km: number | null;
  image_url: string | null;
  source: string;
  source_label: string;
  url: string;
  is_demo: boolean;
  status: string;
  first_seen_at: string;
  removed_at: string | null;
  days_online: number | null;
  predicted_price: number | null;
  predicted_low: number | null;
  predicted_high: number | null;
  valuation_confidence: "high" | "medium" | "low" | null;
  valuation_method: string | null;
  deal_score: number | null;
  deal_eur: number | null;
  km_effect_eur: number | null;
  expected_km: number | null;
  match: number | null;
  components: Components;
  km_ratio: number | null;
  issue_count: number;
  issue_cost: number;
  health_notes: string[];
  red_flags: RedFlag[];
  options: string[];
  option_labels: string[];
  duplicates: Duplicate[];
  rdw: RdwSummary | null;
  on_watchlist?: boolean;
  reasons?: string[];
  feed_score?: number;
}

export interface SearchFilters {
  q?: string;
  makes?: string[];
  models?: string[];
  generations?: string[];
  fuels?: string[];
  bodies?: string[];
  transmissions?: string[];
  price_min?: number | null;
  price_max?: number | null;
  km_min?: number | null;
  km_max?: number | null;
  year_min?: number | null;
  year_max?: number | null;
  kw_min?: number | null;
  kw_max?: number | null;
  seats_min?: number | null;
  colours?: string[];
  options?: string[];
  towing_min?: number | null;
  range_min?: number | null;
  max_distance_km?: number | null;
  seller_types?: string[];
  sources?: string[];
  bovag_only?: boolean;
  warranty_only?: boolean;
  hide_import?: boolean;
  hide_nap_issues?: boolean;
  hide_open_recall?: boolean;
  hide_high_flags?: boolean;
  hide_battery_lease?: boolean;
  min_deal_pct?: number | null;
}

export type Weights = Record<string, number>;

export interface ParetoPoint {
  id: number;
  price: number;
  km: number;
  year: number | null;
  title: string;
  match: number;
  deal_score: number | null;
  frontier: boolean;
}

export interface SearchResponse {
  total: number;
  page: number;
  page_size: number;
  items: ListingCard[];
  stats: {
    count: number;
    median_price: number | null;
    median_km: number | null;
    price_min: number | null;
    price_max: number | null;
    share_under_market: number | null;
    facets: Record<string, Record<string, number>>;
  };
  pareto: ParetoPoint[];
}

export interface CatalogModel {
  slug: string;
  name: string;
  segment: string;
  generations: { id: string; name: string; from: number; to: number | null }[];
}
export interface CatalogMake {
  slug: string;
  name: string;
  models: CatalogModel[];
}

export interface Profile {
  id: number;
  name: string;
  home_postcode: string | null;
  has_ntfy: boolean;
}

export interface Meta {
  catalog: CatalogMake[];
  fuels: Record<string, string>;
  bodies: Record<string, string>;
  transmissions: Record<string, string>;
  options: Record<string, string>;
  colours: string[];
  weights: Weights;
  weight_labels: Record<string, string>;
  sources: { name: string; label: string; enabled: boolean; verified: boolean }[];
  demo_mode: boolean;
  ai_enabled: boolean;
  ntfy_configured: boolean;
  home_postcode: string;
  profiles: Profile[];
  issue_coverage: { id: string; title: string; applies_to: { make: string; model?: string }[]; n_issues: number; reviewed: string }[];
  ready: boolean;
  startup_message: string;
}

export interface Issue {
  id: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  severity_label: string;
  likelihood?: "low" | "medium" | "high";
  category?: string;
  summary?: string;
  symptoms?: string[];
  repair_cost_eur?: [number, number];
  fix?: { type: string; description?: string };
  verify?: string[];
  questions?: string[];
  test_drive?: string[];
  sources?: { title: string; url: string }[];
  years?: [number | null, number | null];
  certainty?: "zeker" | "waarschijnlijk" | "mogelijk";
  recall_status?: "open" | "hersteld" | null;
  expected_cost_eur?: number;
  ai?: boolean;
  file_id?: string;
}

export interface Vehicle {
  kenteken: string;
  found: boolean;
  is_demo: boolean;
  make: string | null;
  trade_name: string | null;
  first_admission: string | null;
  first_nl_registration: string | null;
  last_registration: string | null;
  apk_expiry: string | null;
  is_import: boolean | null;
  odometer_judgement: string | null;
  odometer_code: string | null;
  odometer_explanation: string | null;
  odometer_last_year: number | null;
  open_recall: boolean | null;
  taxi: boolean | null;
  export: boolean | null;
  insured: boolean | null;
  catalog_price: number | null;
  mass_empty: number | null;
  mass_ready: number | null;
  towing_braked: number | null;
  towing_unbraked: number | null;
  seats: number | null;
  colour: string | null;
  body: string | null;
  engine_cc: number | null;
  fuel: string | null;
  power_kw: number | null;
  co2_g_km: number | null;
  consumption_l_100km: number | null;
  consumption_kwh_100km: number | null;
  range_km: number | null;
  energy_label: string | null;
  emission_class: string | null;
  recalls: {
    referentiecode_rdw: string;
    status: string;
    open: boolean;
    omschrijving_defect?: string;
    titel?: string;
    gevolgen?: string;
    herstel?: string;
    publicatiedatum?: string;
    demo?: boolean;
  }[];
  apk_defects: { datum: string | null; code: string; omschrijving: string; aantal: number }[];
  fetched_at: string;
}

export interface Negotiation {
  asking: number;
  market: number;
  opening_bid: number;
  walk_away: number;
  expected_repairs: number;
  arguments: string[];
  tips: string[];
}

export interface EvInfo {
  warranty: { years?: number; km?: number; min_soh_pct?: number; note?: string };
  warranty_is_default: boolean;
  warranty_years_left: number | null;
  warranty_km_left: number | null;
  warranty_covered: boolean;
  range: { wltp: number; zomer: number; winter: number; snelweg_130: number } | null;
  heat_pump: boolean;
  battery_lease: boolean;
  battery_kwh: number | null;
  advice: string[];
}

export interface ModelOverview {
  title: string;
  summary: string | null;
  battery_warranty: EvInfo["warranty"] | null;
  general_checks: string[];
  issues: Issue[];
  source: string;
  has_model_specific: boolean;
  files: { id: string; title: string; summary: string; source: string }[];
}

export interface ListingDetail extends ListingCard {
  description: string;
  image_urls: string[];
  price_history: { date: string; price: number }[];
  vehicle: Vehicle | null;
  issues: Issue[];
  model_overview: ModelOverview | null;
  comparables: ListingCard[];
  depreciation: { year: number; value: number }[];
  negotiation: Negotiation | null;
  ev: EvInfo | null;
  watchlist: { id: number; status: string; notes: string } | null;
  feedback: number;
  valuation_metrics: Record<string, number>;
}

export interface Tco {
  inputs: Record<string, number | string | null>;
  consumption: {
    wltp_l_100km: number | null;
    wltp_kwh_100km: number | null;
    real_l_100km: number | null;
    real_kwh_100km: number | null;
    source: string;
  };
  mrb: { quarter: number | null; month: number | null; basis: string; exact_url: string; province: string | null; month_used: number };
  monthly: Record<string, number>;
  per_km: number | null;
  resale_value: number | null;
  years: number;
  notes: string[];
}

export interface SavedSearch {
  id: number;
  profile_id: number;
  name: string;
  filters: SearchFilters;
  weights: Weights;
  alert_mode: "instant" | "daily" | "off";
  min_match: number;
  price_drop_eur: number;
  price_drop_pct: number;
  created_at: string;
  last_run_at: string | null;
  alerts_total: number;
  current_matches?: number;
  total_results?: number;
  top?: ListingCard[];
}

export interface AlertItem {
  id: number;
  kind: "new" | "price_drop" | "back" | "sold";
  created_at: string;
  delivery: string;
  seen: boolean;
  match: number | null;
  price_eur: number | null;
  message: string;
  search: string | null;
  listing: ListingCard;
}

export interface WatchItem extends ListingCard {
  watch: {
    id: number;
    status: string;
    notes: string;
    price_at_add: number | null;
    added_at: string;
    updated_at: string;
    checklist_state: Record<string, boolean>;
    added_by: number | null;
  };
}
