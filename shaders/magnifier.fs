#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform vec4 colDiffuse;
uniform vec2 resolution;

// --- Magnifying-glass lens (RMB) ---------------------------------------
// Applied to the whole render texture at blit time. lensZoom == 1.0 makes it
// a passthrough. Inside a circle of lensRadius around lensCenter (UV) the
// coordinates are pulled toward the centre, enlarging that region.
uniform vec2  lensCenter;
uniform float lensRadius;
uniform float lensZoom;

out vec4 finalColor;

void main() {
    vec2  uv  = fragTexCoord;
    float rim = 0.0;

    if (lensZoom > 1.001) {
        vec2  d      = uv - lensCenter;
        float aspect = resolution.x / resolution.y;
        float r      = length(vec2(d.x * aspect, d.y));   // circular on screen
        float m      = smoothstep(lensRadius, lensRadius * 0.88, r);
        rim = smoothstep(lensRadius * 0.90, lensRadius * 0.97, r)
              * (1.0 - smoothstep(lensRadius * 0.99, lensRadius * 1.04, r));
        uv = mix(uv, lensCenter + d / lensZoom, m);
    }

    vec4 c = texture(texture0, uv) * colDiffuse * fragColor;
    c.rgb *= (1.0 - 0.45 * rim);             // thin darkened glass rim
    finalColor = c;
}
