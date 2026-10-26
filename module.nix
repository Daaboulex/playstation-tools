{ ps5-linux-patches, patchSetKernel }:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.ps5-linux.kernel;

  ps5Config = with lib.kernel; {
    X86_EXTENDED_PLATFORM = yes;
    X86_PS5 = yes;
    AHCI_SALINA = module;
    MTS = module;
    IOMMU_DEFAULT_PASSTHROUGH = yes;
    EXTRA_FIRMWARE = freeform "amdgpu/ps5_vcn.bin";
    EXTRA_FIRMWARE_DIR = freeform "${ps5-linux-patches}/firmware";
  };

  configLine =
    name: value:
    if value ? tristate then
      "CONFIG_${name}=${value.tristate}"
    else
      "CONFIG_${name}=\"${value.freeform}\"";

  configGuard =
    pkgs.runCommand "ps5-kernel-config"
      {
        configfile = config.boot.kernelPackages.kernel.configfile;
        wanted = pkgs.writeText "ps5-kernel-config-wanted" (
          lib.concatLines (lib.mapAttrsToList configLine ps5Config)
        );
      }
      ''
        missing=0
        while IFS= read -r line; do
          if ! grep -qxF "$line" "$configfile"; then
            echo "the kernel config lacks $line"
            missing=1
          fi
        done < "$wanted"
        if [ "$missing" -ne 0 ]; then
          echo "the PS5 patch set's options did not survive this kernel's config generation"
          exit 1
        fi
        touch "$out"
      '';
in
{
  options.ps5-linux.kernel.enable = lib.mkEnableOption ''
    the PS5 Linux patch set (ps5-linux-patches) with the options and the
    built-in VCN firmware it needs. By default the kernel is the kernel.org
    release the patch set targets; a configuration that sets
    `boot.kernelPackages` itself, such as to a CachyOS kernel, gets the patch
    set on that kernel instead, which builds once the patch set applies to it
  '';

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = pkgs.stdenv.hostPlatform.isx86_64;
        message = "ps5-linux.kernel: the PS5 patch set is for x86_64 only";
      }
    ];
    boot.kernelPackages = lib.mkDefault (
      pkgs.linuxPackagesFor (
        pkgs.callPackage ./kernel.nix {
          inherit patchSetKernel;
          kernelPatches = [
            pkgs.kernelPatches.bridge_stp_helper
            pkgs.kernelPatches.request_key_helper
          ];
        }
      )
    );
    boot.kernelPatches = [
      {
        name = "ps5";
        patch = "${ps5-linux-patches}/linux.patch";
        structuredExtraConfig = ps5Config;
      }
    ];
    system.checks = [ configGuard ];
  };
}
