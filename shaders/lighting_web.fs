#version 100
precision mediump float;

varying vec2 fragTexCoord;
varying vec4 fragColor;
varying vec3 fragNormal;
varying vec3 fragPosition;

uniform sampler2D texture0;     // diffuse map (raylib default)
uniform vec4 colDiffuse;        // material tint (raylib default)

// --- Single spotlight, Blinn-Phong (GLSL ES 1.0) ------------------------
uniform vec3 viewPos;           // camera position (set per-frame)
uniform vec3 lightPos;          // spotlight position, above the table
uniform vec3 lightDir;          // direction the cone points (downward)
uniform vec3 lightColor;        // warm key
uniform vec3 ambientColor;      // cool fill
uniform float spotInner;        // cos(inner cone half-angle)
uniform float spotOuter;        // cos(outer cone half-angle)
uniform float shininess;        // Blinn-Phong specular exponent
uniform float specStrength;     // specular highlight weight

void main() {
    vec4 texelColor = texture2D(texture0, fragTexCoord);

    vec3 N = normalize(fragNormal);
    vec3 L = normalize(lightPos - fragPosition);
    vec3 V = normalize(viewPos - fragPosition);
    vec3 H = normalize(L + V);

    float cosDir = dot(normalize(fragPosition - lightPos), normalize(lightDir));
    float spot   = smoothstep(spotOuter, spotInner, cosDir);

    float diff = max(dot(N, L), 0.0);
    float spec = pow(max(dot(N, H), 0.0), shininess) * specStrength * step(0.0001, diff);

    vec3 lit = ambientColor + spot * lightColor * (diff + spec);

    vec3 col = texelColor.rgb * fragColor.rgb * colDiffuse.rgb * lit;
    gl_FragColor = vec4(col, texelColor.a * colDiffuse.a * fragColor.a);
}
