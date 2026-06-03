import * as THREE from "three";

/**
 * Dissolve shader that fragments a mesh using 3D simplex noise.
 * - progress: 0 = fully solid, 1 = fully dissolved
 * - edgeColor: bright glow color at the dissolve boundary
 * - edgeWidth: how wide the glow edge is
 * - baseColor: the clay color of the model
 */

// 3D Simplex noise GLSL (Ashima Arts)
const noiseGLSL = /* glsl */ `
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);

  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);

  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);

  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;

  i = mod289(i);
  vec4 p = permute(permute(permute(
    i.z + vec4(0.0, i1.z, i2.z, 1.0))
  + i.y + vec4(0.0, i1.y, i2.y, 1.0))
  + i.x + vec4(0.0, i1.x, i2.x, 1.0));

  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;

  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);

  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);

  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);

  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);

  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));

  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;

  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);

  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
  p0 *= norm.x;
  p1 *= norm.y;
  p2 *= norm.z;
  p3 *= norm.w;

  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}
`;

const vertexShader = /* glsl */ `
#include <skinning_pars_vertex>

varying vec3 vWorldPosition;
varying vec3 vLocalPosition;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  vUv = uv;
  vLocalPosition = position;

  #include <skinbase_vertex>

  // Transform position with skinning
  #ifdef USE_SKINNING
    vec4 skinVertex = bindMatrix * vec4(position, 1.0);
    vec4 skinned = vec4(0.0);
    skinned += boneMatX * skinVertex * skinWeight.x;
    skinned += boneMatY * skinVertex * skinWeight.y;
    skinned += boneMatZ * skinVertex * skinWeight.z;
    skinned += boneMatW * skinVertex * skinWeight.w;
    vec4 skinnedPos = bindMatrixInverse * skinned;

    // Skin normal
    mat4 skinMatrix2 = skinWeight.x * boneMatX
      + skinWeight.y * boneMatY
      + skinWeight.z * boneMatZ
      + skinWeight.w * boneMatW;
    vec3 skinnedNormal = (bindMatrixInverse * skinMatrix2 * bindMatrix * vec4(normal, 0.0)).xyz;
    vNormal = normalize(normalMatrix * skinnedNormal);

    vec4 worldPos = modelMatrix * skinnedPos;
  #else
    vNormal = normalize(normalMatrix * normal);
    vec4 worldPos = modelMatrix * vec4(position, 1.0);
  #endif

  vWorldPosition = worldPos.xyz;
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`;

const fragmentShader = /* glsl */ `
${noiseGLSL}

uniform float uProgress;
uniform float uEdgeWidth;
uniform vec3 uEdgeColor;
uniform vec3 uBaseColor;
uniform float uNoiseScale;

// Weight paint uniforms
uniform float uWeightProgress;
uniform vec3 uBonePositions[6];
uniform vec3 uBoneColors[6];

varying vec3 vWorldPosition;
varying vec3 vLocalPosition;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  // Multi-octave noise for organic dissolve pattern
  float noise = snoise(vWorldPosition * uNoiseScale) * 0.5 + 0.5;
  noise += snoise(vWorldPosition * uNoiseScale * 2.0) * 0.25;
  noise = clamp(noise / 1.25, 0.0, 1.0); // clamp to prevent negative values

  // Dissolve: discard fragments below threshold
  // Guard: never discard when progress is effectively 0
  float threshold = uProgress;
  if (threshold > 0.001 && noise < threshold) {
    discard;
  }

  // Basic lighting
  vec3 lightDir = normalize(vec3(0.5, 0.8, 0.5));
  float diff = max(dot(vNormal, lightDir), 0.0);
  float ambient = 0.35;
  
  // Weight Paint Calculation
  vec3 wpColor = vec3(0.0);
  float totalWeight = 0.0;
  for(int i=0; i<6; i++) {
    float dist = distance(vLocalPosition, uBonePositions[i]);
    // Smooth inverse square falloff
    float weight = 1.0 / (dist * dist * 100.0 + 0.1);
    wpColor += uBoneColors[i] * weight;
    totalWeight += weight;
  }
  wpColor /= totalWeight;
  // Boost saturation/brightness of weight paint
  wpColor = clamp(wpColor * 1.5, 0.0, 1.0);

  // Mix base color with weight paint color based on progress
  vec3 currentBaseColor = mix(uBaseColor, wpColor, uWeightProgress);
  
  vec3 color = currentBaseColor * (ambient + diff * 0.65);

  // Edge glow — bright colored edge at the dissolve boundary
  float edge = 1.0 - smoothstep(0.0, uEdgeWidth, noise - threshold);
  vec3 finalColor = mix(color, uEdgeColor, edge * step(0.001, uProgress));

  // Add slight emissive bloom at edge
  float edgeEmissive = edge * step(0.001, uProgress) * 1.5;

  gl_FragColor = vec4(finalColor + uEdgeColor * edgeEmissive * 0.3, 1.0);
}
`;

export interface DissolveUniforms {
	uProgress: { value: number };
	uEdgeWidth: { value: number };
	uEdgeColor: { value: THREE.Color };
	uBaseColor: { value: THREE.Color };
	uNoiseScale: { value: number };
	uWeightProgress: { value: number };
	uBonePositions: { value: THREE.Vector3[] };
	uBoneColors: { value: THREE.Color[] };
}

export function createDissolveMaterial(
	options?: Partial<{
		baseColor: string;
		edgeColor: string;
		edgeWidth: number;
		noiseScale: number;
	}>
): THREE.ShaderMaterial {
	const uniforms: DissolveUniforms = {
		uProgress: { value: 0 },
		uEdgeWidth: { value: options?.edgeWidth ?? 0.08 },
		uEdgeColor: {
			value: new THREE.Color(options?.edgeColor ?? "#00ffcc"),
		},
		uBaseColor: {
			value: new THREE.Color(options?.baseColor ?? "#c77d6a"),
		},
		uNoiseScale: { value: options?.noiseScale ?? 3.0 },
		uWeightProgress: { value: 0 },
		uBonePositions: { 
			value: Array(6).fill(null).map(() => new THREE.Vector3()) 
		},
		uBoneColors: { 
			value: Array(6).fill(null).map(() => new THREE.Color(0,0,0)) 
		},
	};

	return new THREE.ShaderMaterial({
		uniforms: uniforms as unknown as Record<string, THREE.IUniform>,
		vertexShader,
		fragmentShader,
		side: THREE.DoubleSide,
		transparent: false,
		skinning: true,
	} as any);
}
