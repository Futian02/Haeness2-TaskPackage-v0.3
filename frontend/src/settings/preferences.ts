export type ThemePreference = "light" | "dark" | "system";
export type DensityPreference = "comfortable" | "compact";
export type PersonalityPreference = "professional" | "natural" | "companion" | "concise";

export type UserPreferences = {
  fontScale: 90 | 100 | 110;
  density: DensityPreference;
  theme: ThemePreference;
  autoExpandTrace: boolean;
  personality: PersonalityPreference;
  customInstructions: string;
};

export const DEFAULT_PREFERENCES: UserPreferences = {
  fontScale: 100,
  density: "comfortable",
  theme: "system",
  autoExpandTrace: true,
  personality: "professional",
  customInstructions: "",
};

export const PREFERENCES_KEY = "aetheris-preferences-v1";

export function readPreferences(): UserPreferences {
  try {
    const parsed = JSON.parse(localStorage.getItem(PREFERENCES_KEY) || "null");
    if (!parsed || typeof parsed !== "object") return DEFAULT_PREFERENCES;
    return {
      ...DEFAULT_PREFERENCES,
      ...parsed,
      fontScale: [90, 100, 110].includes(Number(parsed.fontScale)) ? Number(parsed.fontScale) : 100,
      density: parsed.density === "compact" ? "compact" : "comfortable",
      theme: ["light", "dark", "system"].includes(parsed.theme) ? parsed.theme : "system",
      customInstructions: typeof parsed.customInstructions === "string" ? parsed.customInstructions.slice(0, 500) : "",
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function writePreferences(preferences: UserPreferences) {
  localStorage.setItem(PREFERENCES_KEY, JSON.stringify(preferences));
}
