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
    ps5-linux-patches = {
      url = "github:ps5-linux/ps5-linux-patches";
      flake = false;
    };
  };

  outputs =
    inputs@{ flake-parts, self, ... }:
    let
      inherit (inputs.nixpkgs) lib;
      patchSetHeaders = lib.filter (match: match != null) (
        map (builtins.match "# Linux/x86 ([0-9]+\\.[0-9]+\\.[0-9]+) Kernel Configuration") (
          lib.splitString "\n" (builtins.readFile "${inputs.ps5-linux-patches}/.config")
        )
      );
      patchSetKernel =
        if patchSetHeaders == [ ] then
          throw "ps5-linux-patches: its .config names no Linux/x86 kernel version"
        else
          builtins.head (builtins.head patchSetHeaders);
    in
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

      flake.nixosModules.default = import ./module.nix {
        inherit (inputs) ps5-linux-patches;
        inherit patchSetKernel;
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

          checks = {
            pst = pkgs.runCommand "pst-check" { } ''
              cp ${./pst.py} pst.py
              cp ${./check.py} check.py
              cp -r ${./fixtures} fixtures
              ${python}/bin/python3 check.py
              touch "$out"
            '';
            fpkg-playgo-boundary = pkgs.callPackage ./fixtures/playgo-trigger.nix { };
          }
          // lib.optionalAttrs (system == "x86_64-linux") (
            let
              ps5Kernel = {
                ps5-linux.kernel.enable = true;
              };
              ps5System = lib.nixosSystem {
                inherit system;
                modules = [
                  self.nixosModules.default
                  ps5Kernel
                  {
                    boot.isContainer = true;
                    system.stateVersion = lib.trivial.release;
                  }
                ];
              };
            in
            {
              module-eval-nixos = inputs.std.lib.nixosModuleCheck {
                inherit (inputs) nixpkgs;
                inherit system;
                module = self.nixosModules.default;
                config = ps5Kernel;
              };
              ps5-kernel-config = lib.findFirst (
                check: check.name == "ps5-kernel-config"
              ) (throw "the module added no ps5-kernel-config check") ps5System.config.system.checks;
            }
          );

          apps.after-lock-update = {
            type = "app";
            program = lib.getExe (
              pkgs.writeShellApplication {
                name = "after-lock-update";
                runtimeInputs = [
                  pkgs.jq
                  pkgs.curl
                  pkgs.openssl
                  pkgs.coreutils
                ];
                runtimeEnv.PATCH_SET_KERNEL = patchSetKernel;
                text = builtins.readFile ./scripts/sync-kernel-pin.sh;
              }
            );
            meta.description = "Point kernel.json at the kernel.org release the PS5 patch set targets";
          };

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
