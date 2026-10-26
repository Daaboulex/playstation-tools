{
  description = "pst, a command-line tool for jailbroken PS4 and PS5 consoles: status, payload updates, game folders, fake packages, saves, Y2JB and avatars";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    git-hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    std = {
      url = "github:Daaboulex/nix-packaging-standard/release";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.git-hooks.follows = "git-hooks";
    };
  };

  outputs =
    inputs@{ flake-parts, self, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];

      imports = [ inputs.std.flakeModules.base ];

      flake.overlays =
        let
          glueOverlay = import ./overlay.nix;
          dir = ./overlays;
          names = if builtins.pathExists dir then builtins.attrNames (builtins.readDir dir) else [ ];
          fixOverlays = map (n: (import (dir + "/${n}")).overlay) (
            builtins.filter (n: inputs.nixpkgs.lib.hasSuffix ".nix" n) names
          );
        in
        {
          default = inputs.nixpkgs.lib.composeManyExtensions ([ glueOverlay ] ++ fixOverlays);
          probe = glueOverlay;
        };

      perSystem =
        { config, system, ... }:
        let
          pkgs = import inputs.nixpkgs {
            inherit system;
            overlays = [ self.overlays.default ];
          };
          python = pkgs.python3.withPackages (python: [ python.pillow ]);
        in
        {
          pre-commit.settings.hooks.trim-trailing-whitespace.excludes = [ "\\.patch$" ];

          packages.default = pkgs.playstation-tools;

          checks.pst = pkgs.runCommand "pst-check" { } ''
            cp ${./pst.py} pst.py
            cp ${./check.py} check.py
            cp -r ${./fixtures} fixtures
            ${python}/bin/python3 check.py
            touch "$out"
          '';
          checks.fpkg-playgo-boundary = pkgs.callPackage ./fixtures/playgo-trigger.nix { };

          devShells.default = pkgs.lib.mkForce (
            inputs.std.lib.mkDevShell { inherit pkgs config; } {
              packages = [
                pkgs.playstation-tools
                python
                pkgs.liborbispkg-pkgtool
                pkgs.jq
                pkgs.curl
              ];
              shellHook = ''
                export DOTNET_CLI_HOME="$DEVSHELL_STATE/dotnet"
              '';
            }
          );
        };
    };
}
