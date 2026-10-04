{
  description = "UpstreamRadar polyglot development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          python313
          rustc cargo
          go
          nodejs_22
          cmake gcc gfortran
          jdk17
          ruby php perl
          R
          julia
          sqlite
        ];

        shellHook = ''
          export PYTHONUTF8=1
          echo "UpstreamRadar polyglot shell ready"
        '';
      };
    };
}
