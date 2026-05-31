#version 100
precision mediump float;

// Nausea curse — wavy screen distortion with a sickly green tint (GLSL ES 1.0).
varying vec2 fragTexCoord;
varying vec4 fragColor;

uniform sampler2D texture0;
uniform vec4 colDiffuse;

// Animated over time by the CPU.
uniform float seconds;

void main() {
    float waveX = sin(seconds * 3.0 + fragTexCoord.y * 20.0) * 0.005;
    float waveY = cos(seconds * 2.5 + fragTexCoord.x * 15.0) * 0.005;

    vec2 distortedTexCoord = vec2(fragTexCoord.x + waveX, fragTexCoord.y + waveY);

    vec4 texelColor = texture2D(texture0, distortedTexCoord) * colDiffuse * fragColor;
    texelColor.rgb *= vec3(0.9, 1.1, 0.9);

    gl_FragColor = texelColor;
}
