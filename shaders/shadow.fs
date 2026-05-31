#version 330

// Flat shadow pass: the geometry is flattened onto the table plane by the
// projection matrix on the CPU side, so all we do here is paint it a single
// translucent dark colour (passed in via the material tint, colDiffuse).
in vec2 fragTexCoord;
in vec4 fragColor;

uniform vec4 colDiffuse;

out vec4 finalColor;

void main() {
    finalColor = colDiffuse;
}
