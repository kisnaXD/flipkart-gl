"""Shared Tailwind config and styles for Stitch UI pages."""

TAILWIND_CONFIG = """
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "primary-fixed": "#d8e2ff",
        "inverse-primary": "#005ac2",
        "surface-container-high": "#272a31",
        "primary-fixed-dim": "#adc6ff",
        "surface-container-highest": "#32353c",
        "surface-variant": "#32353c",
        "on-primary": "#002e6a",
        "surface": "#10131a",
        "surface-container-low": "#191b23",
        "on-error": "#690005",
        "on-surface-variant": "#c2c6d6",
        "surface-bright": "#363941",
        "secondary": "#4cd7f6",
        "surface-tint": "#adc6ff",
        "surface-container": "#1d2027",
        "outline": "#8c909f",
        "outline-variant": "#424754",
        "tertiary": "#ffb786",
        "error": "#ffb4ab",
        "secondary-container": "#03b5d3",
        "primary-container": "#4d8eff",
        "primary": "#adc6ff",
        "on-surface": "#e1e2ec",
        "background": "#10131a",
        "surface-container-lowest": "#0b0e15",
        "ops-red": "#FF4444",
        "ops-amber": "#FFBB33",
        "ops-green": "#00C851",
        "ops-blue": "#33B5E5",
        "ops-pink": "#FF4081",
        "tier-critical": "#d8b4fe",
        "tier-high": "#fca5a5",
        "tier-medium": "#fcd34d",
        "tier-low": "#86efac",
      },
      borderRadius: { DEFAULT: "0.25rem", lg: "0.5rem", xl: "0.75rem", full: "9999px" },
      spacing: { gutter: "16px", "panel-padding": "20px", "container-margin": "24px", unit: "4px" },
      fontFamily: {
        "headline-md": ["Geist", "Inter", "sans-serif"],
        "body-sm": ["Geist", "Inter", "sans-serif"],
        "label-md": ["Geist", "Inter", "sans-serif"],
        "title-md": ["Geist", "Inter", "sans-serif"],
        "mono-data": ["Geist Mono", "ui-monospace", "monospace"],
        "body-lg": ["Geist", "Inter", "sans-serif"],
      },
      fontSize: {
        "headline-md": ["24px", { lineHeight: "32px", fontWeight: "600" }],
        "body-sm": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "label-md": ["12px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "500" }],
        "title-md": ["18px", { lineHeight: "28px", fontWeight: "500" }],
        "mono-data": ["14px", { lineHeight: "20px", fontWeight: "500" }],
        "body-lg": ["16px", { lineHeight: "24px", fontWeight: "400" }],
      },
    },
  },
};
"""

NAV_ROUTES = {
    "command": "/",
    "map": "/map",
    "scenarios": "/scenarios",
    "hotspots": "/hotspots",
    "analytics": "/analytics",
    "learning": "/learning",
}

TIER_COLORS = {
    "Critical": "#d8b4fe",
    "High": "#fca5a5",
    "Medium": "#fcd34d",
    "Low": "#86efac",
}

TIER_DOT = {
    "Critical": "bg-[#d8b4fe]",
    "High": "bg-[#fca5a5]",
    "Medium": "bg-tertiary",
    "Low": "bg-secondary",
}

SCENARIO_SHORT = [
    "Cricket Match",
    "ORR Metro",
    "Procession",
    "VIP Movement",
    "Flash Cluster",
]
