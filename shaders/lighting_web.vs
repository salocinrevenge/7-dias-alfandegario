#version 100
precision mediump float;

// Vertex attributes (raylib default names)
attribute vec3 vertexPosition;
attribute vec2 vertexTexCoord;
attribute vec3 vertexNormal;
attribute vec4 vertexColor;

// Matrices auto-filled by raylib's DrawModel
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;

varying vec2 fragTexCoord;
varying vec4 fragColor;
varying vec3 fragNormal;
varying vec3 fragPosition;

void main() {
    fragTexCoord = vertexTexCoord;
    fragColor    = vertexColor;
    fragPosition = vec3(matModel * vec4(vertexPosition, 1.0));
    fragNormal   = normalize(vec3(matNormal * vec4(vertexNormal, 0.0)));
    gl_Position  = mvp * vec4(vertexPosition, 1.0);
}
