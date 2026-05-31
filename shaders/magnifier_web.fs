precision mediump float;

varying vec2 fragTexCoord;
varying vec4 fragColor;

uniform sampler2D texture0;
uniform vec4 colDiffuse;
uniform vec2 resolution;

// --- Magnifying-glass lens (RMB), GLSL ES 1.0 --------------------------
// lensZoom == 1.0 is a passthrough.
uniform vec2  lensCenter;
uniform float lensRadius;
uniform float lensZoom;

void main() {
    vec2  uv  = fragTexCoord;
    float rim = 0.0;

    if (lensZoom > 1.001) {
        vec2  d      = uv - lensCenter;
        float aspect = resolution.x / resolution.y;
        float r      = length(vec2(d.x * aspect, d.y));
        float m      = smoothstep(lensRadius, lensRadius * 0.88, r);
        rim = smoothstep(lensRadius * 0.90, lensRadius * 0.97, r)
              * (1.0 - smoothstep(lensRadius * 0.99, lensRadius * 1.04, r));
        uv = mix(uv, lensCenter + d / lensZoom, m);
    }

    vec4 c = texture2D(texture0, uv) * colDiffuse * fragColor;
    c.rgb *= (1.0 - 0.45 * rim);
    gl_FragColor = c;
}
