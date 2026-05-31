#version 100
precision mediump float;

// Flat shadow pass (GLSL ES 1.0). Geometry is pre-flattened onto the table
// plane on the CPU; we just paint the material tint colour.
varying vec2 fragTexCoord;
varying vec4 fragColor;

uniform vec4 colDiffuse;

void main() {
    gl_FragColor = colDiffuse;
}
