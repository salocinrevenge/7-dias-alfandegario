{
  description = "A development environment for GLFW and X11 apps";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, utils }:
    utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        
        # Define the exact libraries GLFW needs to dynamically load at runtime
        runtimeLibs = with pkgs; [
          xorg.libX11
          xorg.libXrandr
          xorg.libXinerama
          xorg.libXcursor
          xorg.libXi
          libglvnd      # OpenGL / GLX support
          libGL         # Mesa GL
        ];
      in
      {
        devShells.default = pkgs.mkShell {
          # Tools and packages available during development
          buildInputs = with pkgs; [
            glfw
            pkg-config  # Essential for C/C++ or Go finding GLFW headers
          ] ++ runtimeLibs;

          # Setting LD_LIBRARY_PATH is what fixes the Xlib loading error
          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath runtimeLibs}:$LD_LIBRARY_PATH"
            echo "⚡ GLFW development environment loaded! ⚡"
          '';
        };
      });
}
