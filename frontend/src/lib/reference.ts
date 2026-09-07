/**
 * Product vocabulary: cities and livelihoods an applicant can be recorded as.
 *
 * Mirrors `backend/app/reference.py`. The two are kept in sync by
 * `backend/tests/test_reference_sync.py`, which fails if they drift.
 *
 * Duplicated rather than fetched from the API on purpose: NEXT_PUBLIC_DEMO_MODE
 * exists so the app still renders when the backend is asleep, and the apply form
 * must keep working in that state.
 */

export const CITIES = [
  "Karachi",
  "Lahore",
  "Islamabad",
  "Faisalabad",
  "Rawalpindi",
  "Multan",
  "Peshawar",
  "Hyderabad",
  "Gujranwala",
  "Sialkot",
  "Quetta",
  "Sargodha",
  "Bahawalpur",
  "Sukkur",
  "Larkana",
  "Abbottabad",
  "Mardan",
  "Muzaffarabad",
] as const;

/** [value, human-readable label] — value is what the API stores. */
export const ARCHETYPES: readonly (readonly [string, string])[] = [
  ["kiryana_merchant", "Kiryana / grocery merchant"],
  ["daily_wage_worker", "Daily-wage worker"],
  ["home_based_producer", "Home-based producer"],
  ["ride_hailing_driver", "Ride-hailing driver"],
  ["small_farmer", "Small farmer"],
  ["street_vendor", "Street vendor / thela"],
];

const LABELS = new Map(ARCHETYPES);

/** Human-readable livelihood, falling back to de-slugified text. */
export function archetypeLabel(value: string): string {
  const known = LABELS.get(value);
  if (known) return known;
  const words = value.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
