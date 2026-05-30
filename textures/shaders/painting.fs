#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform vec2 resolution;

out vec4 finalColor;

// ---------------------------------------------------------------------------
// Kuwahara filter — classic oil-painting post-process.
//
// Divides the neighbourhood around each pixel into 4 overlapping quadrants.
// For every quadrant it computes the mean colour and the colour variance.
// The quadrant with the LOWEST variance (smoothest region) wins: its mean
// becomes the output colour.  High-variance regions (edges) keep detail
// because one of their quadrants always straddles into the smooth side.
// The result looks like brushstroke-averaged paint.
// ---------------------------------------------------------------------------
void main() {
    vec2 texel  = 1.0 / resolution;
    const int R = 3;                         // kernel half-size; raise for thicker strokes
    float n     = float((R + 1) * (R + 1)); // samples per quadrant

    vec3 mean[4];
    vec3 sq[4];
    for (int k = 0; k < 4; k++) { mean[k] = vec3(0.0); sq[k] = vec3(0.0); }

    // Top-left quadrant  (i ∈ [-R,0], j ∈ [-R,0])
    for (int j = -R; j <= 0; j++)
        for (int i = -R; i <= 0; i++) {
            vec3 c = texture(texture0, fragTexCoord + vec2(float(i), float(j)) * texel).rgb;
            mean[0] += c;  sq[0] += c * c;
        }

    // Top-right quadrant (i ∈ [0,R],  j ∈ [-R,0])
    for (int j = -R; j <= 0; j++)
        for (int i = 0; i <= R; i++) {
            vec3 c = texture(texture0, fragTexCoord + vec2(float(i), float(j)) * texel).rgb;
            mean[1] += c;  sq[1] += c * c;
        }

    // Bottom-left quadrant  (i ∈ [-R,0], j ∈ [0,R])
    for (int j = 0; j <= R; j++)
        for (int i = -R; i <= 0; i++) {
            vec3 c = texture(texture0, fragTexCoord + vec2(float(i), float(j)) * texel).rgb;
            mean[2] += c;  sq[2] += c * c;
        }

    // Bottom-right quadrant (i ∈ [0,R],  j ∈ [0,R])
    for (int j = 0; j <= R; j++)
        for (int i = 0; i <= R; i++) {
            vec3 c = texture(texture0, fragTexCoord + vec2(float(i), float(j)) * texel).rgb;
            mean[3] += c;  sq[3] += c * c;
        }

    float min_var = 1e9;
    vec3  result  = vec3(0.0);

    for (int k = 0; k < 4; k++) {
        mean[k] /= n;
        // Var(X) = E[X²] - E[X]²  (component-wise, then summed for a scalar measure)
        vec3  variance = abs(sq[k] / n - mean[k] * mean[k]);
        float v        = variance.r + variance.g + variance.b;
        if (v < min_var) {
            min_var = v;
            result  = mean[k];
        }
    }

    // Slight saturation boost (+20 %) makes the painted look more vivid
    vec3 grey   = vec3(dot(result, vec3(0.299, 0.587, 0.114)));
    result      = mix(grey, result, 1.20);

    finalColor = vec4(result, 1.0) * fragColor;
}
