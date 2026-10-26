{
  lib,
  writers,
  python3Packages,
  liborbispkg-pkgtool,
}:
lib.addMetaAttrs
  {
    description = "Command-line tool for jailbroken PS4 and PS5 consoles: status, payload updates, game folders, fake packages, saves, Y2JB and avatars";
    homepage = "https://github.com/Daaboulex/playstation-tools";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
    maintainers = [
      {
        name = "Daaboulex";
        github = "Daaboulex";
        githubId = 39669593;
      }
    ];
  }
  (
    writers.writePython3Bin "pst" {
      libraries = [ python3Packages.pillow ];
      doCheck = false;
      makeWrapperArgs = [
        "--prefix"
        "PATH"
        ":"
        (lib.makeBinPath [ liborbispkg-pkgtool ])
      ];
    } (builtins.readFile ./pst.py)
  )
