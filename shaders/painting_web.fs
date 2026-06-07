#version 100
// highp matters here: the Kuwahara variance test (sq/n - mean*mean) cancels two
// large nearly-equal sums, so mediump rounding visibly changes which quadrant
// "wins" and makes the painted look differ from desktop. highp keeps it stable;
// fall back to mediump only where highp fragments aren't available.
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif

varying vec2 fragTexCoord;
varying vec4 fragColor;

uniform sampler2D texture0;
uniform vec2 resolution;

// ---------------------------------------------------------------------------
// Kuwahara filter — WebGL / GLSL ES 1.0 version.
//
// GLSL ES 1.0 (WebGL 1) restrictions vs desktop GLSL 3.3:
//   • No #version directive (or use #version 100)
//   • No 'out' variables — write to gl_FragColor
//   • 'in/out' replaced by 'varying' for varyings
//   • texture() → texture2D()
//   • Loop bounds MUST be compile-time constants (no const int used as bound)
//   • No array initialisation with dynamic indices in some drivers —
//     we unroll the 4-quadrant loop manually to be safe
// ---------------------------------------------------------------------------
void main() {
    vec2 texel = 1.0 / resolution;

    // Kernel half-size. Keep as a literal so GLSL ES loop-bound rules are met.
    // Raise to 6 for thicker strokes (costs 4*(2*R+1)^2 samples).
    const float R = 3.0;
    float n = (R + 1.0) * (R + 1.0);

    vec3 mean0 = vec3(0.0); vec3 sq0 = vec3(0.0);
    vec3 mean1 = vec3(0.0); vec3 sq1 = vec3(0.0);
    vec3 mean2 = vec3(0.0); vec3 sq2 = vec3(0.0);
    vec3 mean3 = vec3(0.0); vec3 sq3 = vec3(0.0);

    // Unrolled manually; GLSL ES 1.0 requires loop bounds to be
    // constant integral expressions — float loop vars avoid that restriction.
    for (float j = -R; j <= 0.0; j += 1.0) {
        for (float i = -R; i <= 0.0; i += 1.0) {
            vec3 c = texture2D(texture0, fragTexCoord + vec2(i, j) * texel).rgb;
            mean0 += c;  sq0 += c * c;
        }
        for (float i = 0.0; i <= R; i += 1.0) {
            vec3 c = texture2D(texture0, fragTexCoord + vec2(i, j) * texel).rgb;
            mean1 += c;  sq1 += c * c;
        }
    }
    for (float j = 0.0; j <= R; j += 1.0) {
        for (float i = -R; i <= 0.0; i += 1.0) {
            vec3 c = texture2D(texture0, fragTexCoord + vec2(i, j) * texel).rgb;
            mean2 += c;  sq2 += c * c;
        }
        for (float i = 0.0; i <= R; i += 1.0) {
            vec3 c = texture2D(texture0, fragTexCoord + vec2(i, j) * texel).rgb;
            mean3 += c;  sq3 += c * c;
        }
    }

    mean0 /= n; mean1 /= n; mean2 /= n; mean3 /= n;

    vec3 var0 = abs(sq0 / n - mean0 * mean0);
    vec3 var1 = abs(sq1 / n - mean1 * mean1);
    vec3 var2 = abs(sq2 / n - mean2 * mean2);
    vec3 var3 = abs(sq3 / n - mean3 * mean3);

    float v0 = var0.r + var0.g + var0.b;
    float v1 = var1.r + var1.g + var1.b;
    float v2 = var2.r + var2.g + var2.b;
    float v3 = var3.r + var3.g + var3.b;

    // Pick the quadrant with the lowest colour variance
    vec3 result = mean0;
    float minv  = v0;
    if (v1 < minv) { minv = v1; result = mean1; }
    if (v2 < minv) { minv = v2; result = mean2; }
    if (v3 < minv) {            result = mean3; }

    // Slight saturation boost (+20 %) for a more vivid painted look
    vec3 grey = vec3(dot(result, vec3(0.299, 0.587, 0.114)));
    result     = mix(grey, result, 1.20);

    gl_FragColor = vec4(result, 1.0) * fragColor;
}
