#version 330

// Input attributes from raylib
in vec2 fragTexCoord;
in vec4 fragColor;

// Input uniform values
uniform sampler2D texture0;
uniform vec4 colDiffuse;

// Custom uniform to animate the wave over time
uniform float seconds;

out vec4 finalColor;

void main() {
    // Calculate wave distortions for X and Y coordinates
    // Adjust the multipliers to make the effect faster/slower or more/less intense
    float waveX = sin(seconds * 3.0 + fragTexCoord.y * 20.0) * 0.005;
    float waveY = cos(seconds * 2.5 + fragTexCoord.x * 15.0) * 0.005;
    
    // Create distorted coordinates
    vec2 distortedTexCoord = vec2(fragTexCoord.x + waveX, fragTexCoord.y + waveY);
    
    // Sample the texture using our wavy coordinates
    vec4 texelColor = texture(texture0, distortedTexCoord) * colDiffuse * fragColor;
    
    // Optional: Add a subtle green/sickly color tint to enhance the nausea vibe
    texelColor.rgb *= vec3(0.9, 1.1, 0.9);
    
    finalColor = texelColor;
}
