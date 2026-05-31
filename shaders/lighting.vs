#version 330

// Vertex attributes (raylib default names)
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec3 vertexNormal;
in vec4 vertexColor;

// Matrices auto-filled by raylib's DrawModel
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;

out vec2 fragTexCoord;
out vec4 fragColor;
out vec3 fragNormal;   // world-space normal
out vec3 fragPosition; // world-space position

void main() {
    fragTexCoord = vertexTexCoord;
    fragColor    = vertexColor;
    fragPosition = vec3(matModel * vec4(vertexPosition, 1.0));
    fragNormal   = normalize(vec3(matNormal * vec4(vertexNormal, 0.0)));
    gl_Position  = mvp * vec4(vertexPosition, 1.0);
}
