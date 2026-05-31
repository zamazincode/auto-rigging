/**
 * Landing page scroll animation configuration.
 *
 * Each section defines START and END values for model and camera.
 * During scroll, values are linearly interpolated between start → end.
 *
 * Breakpoints: "mobile" (<768px), "tablet" (768-1024px), "desktop" (>1024px)
 *
 * Properties:
 *   posX, posY, posZ  — model position
 *   rotY              — model Y rotation (radians)
 *   scale             — model scale multiplier
 *   camX, camY, camZ  — camera position
 *   floatIntensity    — floating animation strength (0-1)
 *
 * Layout guide (desktop):
 *   Left-aligned text sections  → model on right  (posX ≈ 1.5 to 2.5)
 *   Right-aligned text sections → model on left   (posX ≈ -1.5 to -2.5)
 */

export interface SectionAnimValues {
	posX: number;
	posY: number;
	posZ: number;
	rotY: number;
	scale: number;
	camX: number;
	camY: number;
	camZ: number;
	floatIntensity: number;
}

export interface SectionAnimConfig {
	start: SectionAnimValues;
	end: SectionAnimValues;
}

type Breakpoint = "mobile" | "tablet" | "desktop";

type SectionId =
	| "hero"
	| "upload"
	| "render"
	| "classify"
	| "template"
	| "fitting"
	| "weighting"
	| "download";

const BASE: SectionAnimValues = {
	posX: 0,
	posY: 0,
	posZ: 0,
	rotY: 0,
	scale: 1,
	camX: 3.5,
	camY: 1.4,
	camZ: 5,
	floatIntensity: 1,
};

function section(
	start: Partial<SectionAnimValues>,
	end: Partial<SectionAnimValues>,
): SectionAnimConfig {
	return {
		start: { ...BASE, ...start },
		end: { ...BASE, ...end },
	};
}

// ===== DESKTOP (>1024px) =====
// Text left → model right (posX positive)
// Text right → model left (posX negative)
const DESKTOP: Record<SectionId, SectionAnimConfig> = {
	// Hero: text left, model right
	hero: section(
		{ posX: 2.0, rotY: -0.3, camX: 3.5, camY: 1.4, camZ: 5 },
		{ posX: 2.0, rotY: -0.3, camX: 3.5, camY: 1.4, camZ: 5 },
	),
	// Upload (text left) → model right
	upload: section(
		{ posX: 2.0, rotY: -0.3, camX: 3.5, camY: 1.4, camZ: 5 },
		{ posX: 2.0, rotY: 0, camX: 3.5, camY: 1.4, camZ: 5 },
	),
	// Render (text right) → model left
	render: section(
		{ posX: 2.0, rotY: Math.PI / 4, camX: 3.5, camY: 1.4, camZ: 5 },
		{
			posX: -2.5,
			rotY: Math.PI / 4 + Math.PI * 2,
			camX: -2.0,
			camY: 1.5,
			camZ: 5,
		},
	),
	// Classify (text left) → model right — dissolve happens here
	classify: section(
		{ posX: -1.8, rotY: 0.2 + Math.PI * 2, camX: -2.0, camY: 1.5, camZ: 5 },
		{
			posX: 2.0,
			rotY: 0.2 + Math.PI * 2 + 0.8,
			camX: 3.5,
			camY: 1.4,
			camZ: 4.5,
		},
	),
	// Template (text right) → model left
	template: section(
		{
			posX: 2.0,
			rotY: 0.2 + Math.PI * 2 + 0.8,
			camX: 3.5,
			camY: 1.4,
			camZ: 4.5,
		},
		{
			posX: -1.8,
			rotY: 0.2 + Math.PI * 2 + 1.5,
			camX: -2.0,
			camY: 1.4,
			camZ: 5,
		},
	),
	// Fitting (text left) → model right
	fitting: section(
		{
			posX: -1.8,
			rotY: 0.2 + Math.PI * 2 + 1.5,
			camX: -2.0,
			camY: 1.4,
			camZ: 5,
		},
		{
			posX: 2.0,
			rotY: 0.2 + Math.PI * 2 + 2.5,
			camX: 3.5,
			camY: 1.3,
			camZ: 4.5,
		},
	),
	// Weighting (text right) → model left
	weighting: section(
		{
			posX: 2.0,
			rotY: 0.2 + Math.PI * 2 + 2.5,
			camX: 3.5,
			camY: 1.3,
			camZ: 4.5,
		},
		{
			posX: -1.8,
			rotY: 0.2 + Math.PI * 2 + 3.3,
			camX: -2.0,
			camY: 1.5,
			camZ: 5,
		},
	),
	// Download (text left) → model right — skeleton here
	download: section(
		{
			posX: -1.8,
			rotY: 0.2 + Math.PI * 2 + 3.3,
			camX: -2.0,
			camY: 1.5,
			camZ: 5,
		},
		{
			posX: 2.0,
			rotY: 0.2 + Math.PI * 2 + 4.0,
			camX: 3.5,
			camY: 1.4,
			camZ: 5,
		},
	),
};

// ===== TABLET (768-1024px) =====
const TABLET: Record<SectionId, SectionAnimConfig> = {
	hero: section(
		{ posX: 1.2, rotY: -0.2, camX: 3, camY: 1.4, camZ: 5.5 },
		{ posX: 1.2, rotY: -0.2, camX: 3, camY: 1.4, camZ: 5.5 },
	),
	upload: section(
		{ posX: 1.2, rotY: -0.2, camX: 3, camY: 1.4, camZ: 5.5 },
		{ posX: 1.2, rotY: 0.2, camX: 3, camY: 1.4, camZ: 5.5 },
	),
	render: section(
		{ posX: 1.2, rotY: 0.2, camX: 3, camY: 1.4, camZ: 5.5 },
		{
			posX: -1.2,
			rotY: 0.2 + Math.PI * 2,
			camX: -1.5,
			camY: 1.5,
			camZ: 5.5,
		},
	),
	classify: section(
		{
			posX: -1.2,
			rotY: 0.2 + Math.PI * 2,
			camX: -1.5,
			camY: 1.5,
			camZ: 5.5,
		},
		{
			posX: 1.2,
			rotY: 0.2 + Math.PI * 2 + 0.8,
			camX: 3,
			camY: 1.4,
			camZ: 5,
		},
	),
	template: section(
		{
			posX: 1.2,
			rotY: 0.2 + Math.PI * 2 + 0.8,
			camX: 3,
			camY: 1.4,
			camZ: 5,
		},
		{
			posX: -1.2,
			rotY: 0.2 + Math.PI * 2 + 1.5,
			camX: -1.5,
			camY: 1.4,
			camZ: 5.5,
		},
	),
	fitting: section(
		{
			posX: -1.2,
			rotY: 0.2 + Math.PI * 2 + 1.5,
			camX: -1.5,
			camY: 1.4,
			camZ: 5.5,
		},
		{
			posX: 1.2,
			rotY: 0.2 + Math.PI * 2 + 2.5,
			camX: 3,
			camY: 1.3,
			camZ: 5,
		},
	),
	weighting: section(
		{
			posX: 1.2,
			rotY: 0.2 + Math.PI * 2 + 2.5,
			camX: 3,
			camY: 1.3,
			camZ: 5,
		},
		{
			posX: -1.2,
			rotY: 0.2 + Math.PI * 2 + 3.3,
			camX: -1.5,
			camY: 1.5,
			camZ: 5.5,
		},
	),
	download: section(
		{
			posX: -1.2,
			rotY: 0.2 + Math.PI * 2 + 3.3,
			camX: -1.5,
			camY: 1.5,
			camZ: 5.5,
		},
		{
			posX: 1.2,
			rotY: 0.2 + Math.PI * 2 + 4.0,
			camX: 3,
			camY: 1.4,
			camZ: 5.5,
		},
	),
};

// ===== MOBILE (<768px) =====
// Model centered (posX ≈ 0), camera further back
const MOBILE: Record<SectionId, SectionAnimConfig> = {
	hero: section(
		{ posX: 0, rotY: -0.2, camX: 2.5, camY: 1.6, camZ: 6, scale: 0.85 },
		{ posX: 0, rotY: -0.2, camX: 2.5, camY: 1.6, camZ: 6, scale: 0.85 },
	),
	upload: section(
		{ posX: 0, rotY: -0.2, camX: 2.5, camY: 1.6, camZ: 6, scale: 0.85 },
		{ posX: 0, rotY: 0.2, camX: 2.5, camY: 1.6, camZ: 6, scale: 0.85 },
	),
	render: section(
		{ posX: 0, rotY: 0.2, camX: 2.5, camY: 1.6, camZ: 6, scale: 0.85 },
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2,
			camX: 2.5,
			camY: 1.7,
			camZ: 6,
			scale: 0.85,
		},
	),
	classify: section(
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2,
			camX: 2.5,
			camY: 1.7,
			camZ: 6,
			scale: 0.85,
		},
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2 + 0.8,
			camX: 2.5,
			camY: 1.6,
			camZ: 5.5,
			scale: 0.85,
		},
	),
	template: section(
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2 + 0.8,
			camX: 2.5,
			camY: 1.6,
			camZ: 5.5,
			scale: 0.85,
		},
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2 + 1.5,
			camX: 2.5,
			camY: 1.6,
			camZ: 6,
			scale: 0.85,
		},
	),
	fitting: section(
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2 + 1.5,
			camX: 2.5,
			camY: 1.6,
			camZ: 6,
			scale: 0.85,
		},
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2 + 2.5,
			camX: 2.5,
			camY: 1.5,
			camZ: 5.5,
			scale: 0.85,
		},
	),
	weighting: section(
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2 + 2.5,
			camX: 2.5,
			camY: 1.5,
			camZ: 5.5,
			scale: 0.85,
		},
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2 + 3.3,
			camX: 2.5,
			camY: 1.7,
			camZ: 6,
			scale: 0.85,
		},
	),
	download: section(
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2 + 3.3,
			camX: 2.5,
			camY: 1.7,
			camZ: 6,
			scale: 0.85,
		},
		{
			posX: 0,
			rotY: 0.2 + Math.PI * 2 + 4.0,
			camX: 2.5,
			camY: 1.6,
			camZ: 6,
			scale: 0.85,
		},
	),
};

const BREAKPOINTS: Record<Breakpoint, Record<SectionId, SectionAnimConfig>> = {
	mobile: MOBILE,
	tablet: TABLET,
	desktop: DESKTOP,
};

export function getBreakpoint(): Breakpoint {
	if (typeof window === "undefined") return "desktop";
	const w = window.innerWidth;
	if (w < 768) return "mobile";
	if (w < 1024) return "tablet";
	return "desktop";
}

export function getConfig(): Record<SectionId, SectionAnimConfig> {
	return BREAKPOINTS[getBreakpoint()];
}

export function lerp(a: number, b: number, t: number): number {
	return a + (b - a) * t;
}

export function lerpValues(
	start: SectionAnimValues,
	end: SectionAnimValues,
	progress: number,
): SectionAnimValues {
	return {
		posX: lerp(start.posX, end.posX, progress),
		posY: lerp(start.posY, end.posY, progress),
		posZ: lerp(start.posZ, end.posZ, progress),
		rotY: lerp(start.rotY, end.rotY, progress),
		scale: lerp(start.scale, end.scale, progress),
		camX: lerp(start.camX, end.camX, progress),
		camY: lerp(start.camY, end.camY, progress),
		camZ: lerp(start.camZ, end.camZ, progress),
		floatIntensity: lerp(
			start.floatIntensity,
			end.floatIntensity,
			progress,
		),
	};
}

export const SECTION_IDS: SectionId[] = [
	"hero",
	"upload",
	"render",
	"classify",
	"template",
	"fitting",
	"weighting",
	"download",
];
