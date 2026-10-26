{
  meta = {
    reason = "LibOrbisPkg sizes the PlayGo chunk hash table before counting the entry table and the hash table itself into the 512 KiB body alignment, so pkg_build fails with 'Playgo Chunk hash file was not allocated enough space' when a package body ends just past a boundary (LibOrbisPkg issues 64 and 88); the trigger dump's 0x7A500-byte pic1.png sits in the middle of the failing window, 0x7A400 to 0x7A600, measured 2026-10-26 with pkgtool 0.3-unstable-2025-11-13";
    added = "2026-10-26";
    upstream = "https://github.com/maxton/LibOrbisPkg/issues/88";
  };
  dropWhenBuilds = pkgs: pkgs.callPackage ../fixtures/playgo-trigger.nix { };
  overlay = _final: prev: {
    liborbispkg-pkgtool = prev.liborbispkg-pkgtool.overrideAttrs (old: {
      patches = (old.patches or [ ]) ++ [ ../patches/liborbispkg-chunk-sha-size.patch ];
    });
  };
}
