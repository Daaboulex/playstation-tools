{
  lib,
  fetchurl,
  buildLinux,
  patchSetKernel,
  ...
}@args:
let
  release = lib.removeSuffix ".0" patchSetKernel;
  hashes = lib.importJSON ./kernel.json;
  hash =
    hashes.${release}
      or (throw "kernel.json has no hash for linux ${release}, the kernel the PS5 patch set targets; run nix run .#after-lock-update in playstation-tools");
in
buildLinux (
  removeAttrs args [ "patchSetKernel" ]
  // {
    version = release;
    modDirVersion = patchSetKernel;
    src = fetchurl {
      url = "mirror://kernel/linux/kernel/v${lib.versions.major release}.x/linux-${release}.tar.xz";
      inherit hash;
    };
    extraMeta.branch = lib.versions.majorMinor release;
  }
)
