#version 330

in vec2 fragTexCoord;
in vec4 fragColor;
in vec3 fragNormal;
in vec3 fragPosition;

uniform sampler2D texture0;     // diffuse map (raylib default)
uniform vec4 colDiffuse;        // material tint (raylib default)

// --- Single spotlight, Blinn-Phong (stylized, not physically based) -----
uniform vec3 viewPos;           // camera position (set per-frame)
uniform vec3 lightPos;          // spotlight position, above the table
uniform vec3 lightDir;          // direction the cone points (downward)
uniform vec3 lightColor;        // warm key
uniform vec3 ambientColor;      // cool fill so shadowed areas stay readable
uniform float spotInner;        // cos(inner cone half-angle) — full intensity
uniform float spotOuter;        // cos(outer cone half-angle) — fades to 0
uniform float shininess;        // Blinn-Phong specular exponent
uniform float specStrength;     // specular highlight weight

out vec4 finalColor;

void main() {
    vec4 texelColor = texture(texture0, fragTexCoord);

    vec3 N = normalize(fragNormal);
    vec3 L = normalize(lightPos - fragPosition);     // toward the light
    vec3 V = normalize(viewPos - fragPosition);      // toward the camera
    vec3 H = normalize(L + V);                        // Blinn-Phong half vector

    // Spotlight cone: how aligned the fragment is with the cone axis.
    float cosDir = dot(normalize(fragPosition - lightPos), normalize(lightDir));
    float spot   = smoothstep(spotOuter, spotInner, cosDir);

    float diff = max(dot(N, L), 0.0);
    float spec = 0.0;
    if (diff > 0.0)
        spec = pow(max(dot(N, H), 0.0), shininess) * specStrength;

    vec3 lit = ambientColor + spot * lightColor * (diff + spec);

    vec3 col = texelColor.rgb * fragColor.rgb * colDiffuse.rgb * lit;
    finalColor = vec4(col, texelColor.a * colDiffuse.a * fragColor.a);
}
